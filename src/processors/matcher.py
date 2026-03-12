"""Job matching logic using Claude AI."""

import logging
from typing import Optional
from pathlib import Path

from pypdf import PdfReader

from ..scrapers.base import JobPosting
from ..services.claude_client import ClaudeClient
from ..config import SEARCH_CRITERIA, CANDIDATE_PROFILE, RESUME_PATH

logger = logging.getLogger(__name__)


class JobMatcher:
    """
    Matches jobs against candidate profile using AI and rule-based filtering.
    """

    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client
        self._resume_text: Optional[str] = None

    @property
    def resume_text(self) -> str:
        """Lazy load and cache resume text."""
        if self._resume_text is None:
            self._resume_text = self._extract_resume_text()
        return self._resume_text

    def _extract_resume_text(self) -> str:
        """Extract text from resume PDF."""
        try:
            resume_path = RESUME_PATH
            if not resume_path.exists():
                logger.warning(f"Resume not found at {resume_path}")
                return ""

            reader = PdfReader(resume_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""

            logger.info(f"Extracted {len(text)} chars from resume")
            return text

        except Exception as e:
            logger.error(f"Error extracting resume text: {e}")
            return ""

    def quick_filter(self, job: JobPosting) -> tuple[bool, str]:
        """
        Quick rule-based filtering before AI analysis.

        Returns:
            (passes_filter, reason)
        """
        title_lower = job.title.lower()
        desc_lower = job.description.lower() if job.description else ""
        combined = f"{title_lower} {desc_lower}"

        # Check excluded keywords
        for keyword in SEARCH_CRITERIA["exclude_keywords"]:
            if keyword.lower() in title_lower:
                return False, f"Title contains excluded keyword: {keyword}"

        # Check if title matches any target titles
        title_match = False
        for target_title in SEARCH_CRITERIA["titles"]:
            if target_title.lower() in title_lower:
                title_match = True
                break

        # Also check for finance-related keywords
        finance_keywords = ["finance", "fp&a", "fpa", "financial"]
        has_finance = any(kw in title_lower for kw in finance_keywords)

        if not title_match and not has_finance:
            return False, "Title doesn't match target roles"

        # Check salary if available
        min_salary = SEARCH_CRITERIA.get("min_salary", 0)
        if job.salary_max and job.salary_max < min_salary:
            return False, f"Salary below minimum (${job.salary_max:,} < ${min_salary:,})"

        # Check location
        location_lower = job.location.lower() if job.location else ""
        location_match = False
        for loc in SEARCH_CRITERIA["locations"]:
            if loc.lower() in location_lower:
                location_match = True
                break

        if not location_match and not job.is_remote:
            return False, f"Location mismatch: {job.location}"

        return True, "Passes quick filter"

    async def analyze_job(self, job: JobPosting) -> dict:
        """
        Full AI-powered job analysis.

        Returns:
            {
                "passes_quick_filter": bool,
                "quick_filter_reason": str,
                "ai_analysis": {
                    "score": 1-10,
                    "summary": str,
                    "pros": list,
                    "cons": list,
                    "recommendation": str,
                    "is_gtm_sales": bool
                },
                "final_recommendation": "apply" | "maybe" | "skip"
            }
        """
        result = {
            "passes_quick_filter": False,
            "quick_filter_reason": "",
            "ai_analysis": None,
            "final_recommendation": "skip",
        }

        # Quick filter first
        passes, reason = self.quick_filter(job)
        result["passes_quick_filter"] = passes
        result["quick_filter_reason"] = reason

        if not passes:
            return result

        # AI analysis for jobs that pass quick filter
        try:
            # Need description for good analysis
            description = job.description or f"{job.title} at {job.company}"

            ai_result = await self.claude.analyze_job_match(
                job_title=job.title,
                job_description=description,
                company=job.company,
                candidate_profile=CANDIDATE_PROFILE,
                search_criteria=SEARCH_CRITERIA,
            )

            result["ai_analysis"] = ai_result

            # Filter out GTM/Sales finance that slipped through
            if ai_result.get("is_gtm_sales"):
                result["final_recommendation"] = "skip"
                return result

            # Determine final recommendation based on score
            score = ai_result.get("score", 5)
            if score >= 7:
                result["final_recommendation"] = "apply"
            elif score >= 5:
                result["final_recommendation"] = "maybe"
            else:
                result["final_recommendation"] = "skip"

        except Exception as e:
            logger.error(f"Error in AI analysis for {job.title} at {job.company}: {e}")
            # Default to maybe if AI fails but passes quick filter
            result["final_recommendation"] = "maybe"

        return result

    async def batch_analyze(
        self,
        jobs: list[JobPosting],
        skip_ai_for_filtered: bool = True
    ) -> list[tuple[JobPosting, dict]]:
        """
        Analyze multiple jobs.

        Args:
            jobs: List of jobs to analyze
            skip_ai_for_filtered: Skip AI analysis for jobs that fail quick filter

        Returns:
            List of (job, analysis_result) tuples
        """
        results = []

        for job in jobs:
            logger.info(f"Analyzing: {job.title} at {job.company}")

            if skip_ai_for_filtered:
                passes, reason = self.quick_filter(job)
                if not passes:
                    results.append((job, {
                        "passes_quick_filter": False,
                        "quick_filter_reason": reason,
                        "ai_analysis": None,
                        "final_recommendation": "skip",
                    }))
                    continue

            analysis = await self.analyze_job(job)
            results.append((job, analysis))

        return results

    def rank_jobs(
        self,
        analyzed_jobs: list[tuple[JobPosting, dict]]
    ) -> list[tuple[JobPosting, dict]]:
        """
        Rank analyzed jobs by recommendation quality.

        Returns:
            Sorted list with best matches first
        """
        def sort_key(item):
            job, analysis = item
            rec = analysis.get("final_recommendation", "skip")
            rec_order = {"apply": 0, "maybe": 1, "skip": 2}

            ai = analysis.get("ai_analysis") or {}
            score = ai.get("score", 0)

            # Bonus for having salary info
            salary_bonus = 0.5 if job.salary_min else 0

            return (rec_order.get(rec, 2), -score - salary_bonus)

        return sorted(analyzed_jobs, key=sort_key)
