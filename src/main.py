"""Main orchestrator for the job search bot."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .config import get_settings, SEARCH_CRITERIA, CANDIDATE_PROFILE
from .scrapers import LinkedInScraper, WellfoundScraper, AdzunaScraper
from .scrapers.base import JobPosting
from .processors import JobMatcher, CoverLetterGenerator, HiringManagerFinder
from .services import ClaudeClient, GoogleDriveService, Notifier
from .services.notifier import ConsoleNotifier
from .services.google_drive import LocalFileStorage
from .database import Database, Job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JobSearchBot:
    """
    Main job search bot orchestrator.

    Coordinates:
    1. Scraping jobs from multiple sources
    2. Filtering and analyzing matches
    3. Generating cover letters
    4. Researching hiring managers
    5. Uploading to Google Drive
    6. Sending notifications
    """

    def __init__(self, settings=None):
        """Initialize the bot with settings."""
        self.settings = settings or get_settings()
        self.db = Database(self.settings.database_url)

        # Initialize services
        self.claude = ClaudeClient(self.settings.anthropic_api_key)
        self.matcher = JobMatcher(self.claude)
        self.cover_letter_gen = CoverLetterGenerator(self.claude)
        self.hm_finder = HiringManagerFinder(self.claude)

        # Google Drive (may fail if not configured) with local fallback
        self.drive = None
        self.local_storage = LocalFileStorage("./output")
        try:
            self.drive = GoogleDriveService(
                self.settings.google_credentials_path,
                self.settings.google_drive_folder_id
            )
        except Exception as e:
            logger.warning(f"Google Drive not configured, using local storage: {e}")

        # Notifications
        try:
            self.notifier = Notifier(
                self.settings.pushover_user_key,
                self.settings.pushover_api_token
            )
        except:
            logger.warning("Pushover not configured, using console notifier")
            self.notifier = ConsoleNotifier()

        # Scrapers
        self.scrapers = []

        # Track rejected jobs for reporting
        self.rejected_jobs = []

    async def _init_scrapers(self):
        """Initialize scrapers based on available credentials."""
        # Always try LinkedIn and Wellfound (no API key needed)
        self.scrapers.append(LinkedInScraper(headless=True))
        self.scrapers.append(WellfoundScraper(headless=True))

        # Adzuna if configured
        if self.settings.adzuna_app_id and self.settings.adzuna_app_key:
            self.scrapers.append(AdzunaScraper(
                self.settings.adzuna_app_id,
                self.settings.adzuna_app_key
            ))

    async def scrape_jobs(self) -> list[JobPosting]:
        """Scrape jobs from all sources."""
        logger.info("Starting job scraping...")
        all_jobs = []

        for scraper in self.scrapers:
            try:
                logger.info(f"Scraping from {scraper.source.value}...")
                jobs = await scraper.search(
                    titles=SEARCH_CRITERIA.get("search_queries", SEARCH_CRITERIA["titles"]),
                    locations=SEARCH_CRITERIA["locations"],
                    min_salary=SEARCH_CRITERIA.get("min_salary", 0),
                    max_results=100,  # Get more jobs per source
                )
                all_jobs.extend(jobs)
                logger.info(f"Found {len(jobs)} jobs from {scraper.source.value}")
            except Exception as e:
                logger.error(f"Error scraping {scraper.source.value}: {e}")

        # Filter out already-seen jobs
        new_jobs = []
        for job in all_jobs:
            if not self.db.job_exists(job.id):
                new_jobs.append(job)

        logger.info(f"Total: {len(all_jobs)} jobs, {len(new_jobs)} new")
        return new_jobs

    async def process_jobs(self, jobs: list[JobPosting]) -> list[tuple[JobPosting, dict]]:
        """Analyze jobs and filter for matches."""
        logger.info(f"Analyzing {len(jobs)} jobs...")

        analyzed = await self.matcher.batch_analyze(jobs, skip_ai_for_filtered=True)
        ranked = self.matcher.rank_jobs(analyzed)

        # Track rejected jobs for reporting
        self.rejected_jobs = [
            (job, analysis) for job, analysis in ranked
            if analysis.get("final_recommendation") == "skip"
        ]

        # Log summary
        recommendations = {"apply": 0, "maybe": 0, "skip": 0}
        for job, analysis in ranked:
            rec = analysis.get("final_recommendation", "skip")
            recommendations[rec] = recommendations.get(rec, 0) + 1

        logger.info(f"Analysis complete: {recommendations}")
        return ranked

    async def generate_materials(
        self,
        analyzed_jobs: list[tuple[JobPosting, dict]]
    ) -> list[dict]:
        """Generate cover letters and research hiring managers for good matches."""
        results = []

        # Filter for apply/maybe recommendations
        good_matches = [
            (job, analysis) for job, analysis in analyzed_jobs
            if analysis.get("final_recommendation") in ["apply", "maybe"]
        ]

        logger.info(f"Generating materials for {len(good_matches)} matches...")

        for job, analysis in good_matches:
            try:
                # Get full job details if we only have basic info
                description = job.description
                if not description and hasattr(self.scrapers[0], 'get_job_details'):
                    details = await self.scrapers[0].get_job_details(job.url)
                    if details:
                        description = details.description
                        job.description = description

                # Generate cover letter
                cover_letter = await self.cover_letter_gen.generate(job, analysis)

                # Research hiring managers
                hm_research = await self.hm_finder.research(job)
                hm_report = self.hm_finder.format_research_report(job, hm_research)

                # Upload to Google Drive or save locally
                drive_result = None
                if self.drive:
                    try:
                        drive_result = self.drive.upload_job_package(
                            company=job.company,
                            job_title=job.title,
                            cover_letter=cover_letter,
                            hm_research=hm_report,
                            job_details=description or f"See job posting: {job.url}",
                            job_url=job.url,
                        )
                    except Exception as e:
                        logger.warning(f"Drive upload failed, saving locally: {e}")
                        drive_result = self.local_storage.upload_job_package(
                            company=job.company,
                            job_title=job.title,
                            cover_letter=cover_letter,
                            hm_research=hm_report,
                            job_details=description or f"See job posting: {job.url}",
                            job_url=job.url,
                        )
                else:
                    drive_result = self.local_storage.upload_job_package(
                        company=job.company,
                        job_title=job.title,
                        cover_letter=cover_letter,
                        hm_research=hm_report,
                        job_details=description or f"See job posting: {job.url}",
                        job_url=job.url,
                    )

                # Save to database
                job_data = {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "url": job.url,
                    "source": job.source.value,
                    "description": job.description,
                    "location": job.location,
                    "salary_min": job.salary_min,
                    "salary_max": job.salary_max,
                    "salary_text": job.salary_text,
                    "company_stage": job.company_stage or "",
                    "company_size": job.company_size or "",
                    "is_remote": job.is_remote,
                    "match_score": analysis.get("ai_analysis", {}).get("score"),
                    "recommendation": analysis.get("final_recommendation", ""),
                    "analysis_summary": analysis.get("ai_analysis", {}).get("summary", ""),
                    "cover_letter_generated": True,
                    "drive_folder_id": drive_result.get("folder_id", "") if drive_result else "",
                    "drive_folder_url": drive_result.get("folder_link", "") if drive_result else "",
                    "posted_date": job.posted_date,
                    "analyzed_at": datetime.now(timezone.utc),
                }
                self.db.add_job(job_data)

                results.append({
                    "job": job,
                    "analysis": analysis,
                    "cover_letter": cover_letter,
                    "hm_research": hm_research,
                    "drive_result": drive_result,
                })

            except Exception as e:
                logger.error(f"Error processing {job.company}: {e}")

        return results

    def generate_rejection_report(self) -> str:
        """Generate a report explaining why jobs were skipped."""
        if not self.rejected_jobs:
            return ""

        lines = ["# Rejected Jobs Report", "", f"Total skipped: {len(self.rejected_jobs)}", ""]

        # Group by rejection reason
        quick_filter_rejects = []
        ai_rejects = []

        for job, analysis in self.rejected_jobs:
            if not analysis.get("passes_quick_filter"):
                quick_filter_rejects.append((job, analysis.get("quick_filter_reason", "Unknown")))
            else:
                ai_analysis = analysis.get("ai_analysis", {})
                ai_rejects.append((job, ai_analysis))

        if quick_filter_rejects:
            lines.append("## Quick Filter Rejections")
            lines.append("")
            for job, reason in quick_filter_rejects[:20]:  # Limit to 20
                lines.append(f"- **{job.title}** at {job.company}")
                lines.append(f"  - Reason: {reason}")
                lines.append(f"  - URL: {job.url}")
                lines.append("")

        if ai_rejects:
            lines.append("## AI Analysis Rejections (Low Score)")
            lines.append("")
            for job, ai in ai_rejects[:20]:  # Limit to 20
                score = ai.get("score", "?")
                summary = ai.get("summary", "No summary")
                cons = ai.get("cons", [])
                lines.append(f"- **{job.title}** at {job.company} (Score: {score}/10)")
                lines.append(f"  - Summary: {summary}")
                if cons:
                    lines.append(f"  - Issues: {', '.join(cons[:3])}")
                lines.append(f"  - URL: {job.url}")
                lines.append("")

        return "\n".join(lines)

    def generate_daily_report(self, results: list[dict]) -> str:
        """Generate a detailed daily report with full scoring reasoning."""
        date_str = datetime.now().strftime('%Y-%m-%d')
        lines = [
            f"# Daily Job Search Report — {date_str}",
            "",
            f"**Total matches:** {len(results)}",
            f"**Rejected:** {len(self.rejected_jobs)}",
            "",
            "---",
            "",
        ]

        for i, r in enumerate(results, 1):
            job = r["job"]
            ai = r["analysis"].get("ai_analysis", {})
            score = ai.get("score", "?")
            summary = ai.get("summary", "")
            pros = ai.get("pros", [])
            cons = ai.get("cons", [])
            rec = r["analysis"].get("final_recommendation", "?")
            drive_result = r.get("drive_result", {})
            drive_link = drive_result.get("folder_link", "") if drive_result else ""

            lines.append(f"## {i}. {job.title} at {job.company}")
            lines.append("")
            lines.append(f"**Score:** {score}/10 | **Recommendation:** {rec}")
            lines.append(f"**Location:** {job.location or 'Not specified'}")
            if job.salary_text:
                lines.append(f"**Salary:** {job.salary_text}")
            lines.append(f"**Listing:** {job.url}")
            if drive_link:
                lines.append(f"**Cover Letter & HM Research:** {drive_link}")
            lines.append("")
            lines.append(f"**Summary:** {summary}")
            lines.append("")
            if pros:
                lines.append("**Pros:**")
                for pro in pros:
                    lines.append(f"- {pro}")
                lines.append("")
            if cons:
                lines.append("**Cons:**")
                for con in cons:
                    lines.append(f"- {con}")
                lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    async def send_notifications(self, results: list[dict], all_analyzed: list[tuple]) -> None:
        """Send notification about new matches with detailed reasoning."""
        # Generate rejection report and save it
        rejection_report = self.generate_rejection_report()
        if rejection_report:
            report_path = self.local_storage.output_dir / f"rejection_report_{datetime.now().strftime('%Y%m%d')}.md"
            report_path.write_text(rejection_report)
            logger.info(f"Saved rejection report to {report_path}")

            if self.drive:
                try:
                    self.drive.upload_text_file(
                        content=rejection_report,
                        filename=f"Rejection Report - {datetime.now().strftime('%Y-%m-%d')}.md",
                    )
                except:
                    pass

        # Filter to only jobs not previously notified
        new_results = []
        for r in results:
            job = r["job"]
            db_job = self.db.get_job(job.id)
            if db_job and db_job.notified_at:
                logger.info(f"Skipping already-notified job: {job.title} at {job.company}")
                continue
            new_results.append(r)

        if not new_results:
            total_scraped = len(all_analyzed) if all_analyzed else 0
            await self.notifier.send(
                title="📊 Job Search: No New Matches",
                message=f"Scraped {total_scraped} jobs today.\nNone were new matches.\n\nSee rejection report for details.",
                priority=-1,
            )
            return

        # Sort by score descending, take top 10
        new_results.sort(
            key=lambda r: r["analysis"].get("ai_analysis", {}).get("score", 0),
            reverse=True,
        )
        top_results = new_results[:10]

        # Upload detailed daily report to Google Drive
        daily_report = self.generate_daily_report(top_results)
        report_url = None
        if self.drive:
            try:
                report_file = self.drive.upload_text_file(
                    content=daily_report,
                    filename=f"Daily Report - {datetime.now().strftime('%Y-%m-%d')}.md",
                )
                report_url = report_file.get("webViewLink")
                logger.info(f"Uploaded daily report: {report_url}")
            except Exception as e:
                logger.warning(f"Failed to upload daily report: {e}")

        # Save locally too
        report_path = self.local_storage.output_dir / f"daily_report_{datetime.now().strftime('%Y%m%d')}.md"
        report_path.write_text(daily_report)

        # Get Drive folder URL as fallback
        drive_url = report_url
        if not drive_url and self.drive:
            drive_url = f"https://drive.google.com/drive/folders/{self.settings.google_drive_folder_id}"

        # Send summary notification with link to full report
        rejected_count = len(self.rejected_jobs)
        summary_msg = f"Scraped {len(all_analyzed)} jobs, {len(new_results)} new matches."
        if rejected_count > 0:
            summary_msg += f"\nSkipped {rejected_count} (see report)."
        summary_msg += f"\nTop {len(top_results)} below with full reasoning in report."

        await self.notifier.send(
            title=f"🎯 {len(new_results)} New Match{'es' if len(new_results) > 1 else ''}!",
            message=summary_msg,
            url=drive_url,
            url_title="View Full Report",
            priority=1 if len(new_results) >= 3 else 0,
        )

        # Send top jobs in batches of 3 (HTML links use more chars)
        batch_size = 3
        notified_ids = []
        for i in range(0, len(top_results), batch_size):
            batch = top_results[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(top_results) + batch_size - 1) // batch_size

            lines = []
            for r in batch:
                job = r["job"]
                ai = r["analysis"].get("ai_analysis", {})
                score = ai.get("score", "?")
                summary = ai.get("summary", "")
                pros = ai.get("pros", [])
                if len(summary) > 80:
                    summary = summary[:77] + "..."
                # Hyperlink title to job listing
                lines.append(f'<b>{job.company}</b>: <a href="{job.url}">{job.title}</a>')
                lines.append(f"{score}/10 — {summary}")
                if pros:
                    lines.append(f"✓ {pros[0]}")
                lines.append("")
                notified_ids.append(job.id)

            message = "\n".join(lines).strip()

            await self.notifier.send(
                title=f"Top Jobs ({batch_num}/{total_batches})",
                message=message,
                url=drive_url,
                url_title="Full Report",
                priority=0,
                html=True,
            )

        # Mark all notified jobs in the database
        if notified_ids:
            self.db.mark_notified(notified_ids)

    async def run(self) -> dict:
        """
        Run the complete job search pipeline.

        Returns:
            Summary statistics
        """
        logger.info("=" * 50)
        logger.info("Starting Job Search Bot")
        logger.info("=" * 50)

        try:
            # Initialize scrapers
            await self._init_scrapers()

            # Scrape jobs
            new_jobs = await self.scrape_jobs()

            if not new_jobs:
                logger.info("No new jobs found")
                await self.notifier.send(
                    title="📊 Job Search: No New Listings",
                    message="No new job postings found today.",
                    priority=-1,
                )
                return {"jobs_scraped": 0, "matches": 0, "materials_generated": 0}

            # Analyze jobs
            analyzed = await self.process_jobs(new_jobs)

            # Generate materials for good matches
            results = await self.generate_materials(analyzed)

            # Send notifications with detailed info
            await self.send_notifications(results, analyzed)

            # Summary
            summary = {
                "jobs_scraped": len(new_jobs),
                "matches": len([a for _, a in analyzed if a.get("final_recommendation") != "skip"]),
                "materials_generated": len(results),
                "rejected": len(self.rejected_jobs),
            }

            logger.info("=" * 50)
            logger.info(f"Complete! {summary}")
            logger.info("=" * 50)

            return summary

        finally:
            # Cleanup
            for scraper in self.scrapers:
                await scraper.close()
            await self.notifier.close()


async def main():
    """Entry point for the job search bot."""
    bot = JobSearchBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
