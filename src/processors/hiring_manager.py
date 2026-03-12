"""Hiring manager research using Claude AI."""

import logging
from typing import Optional

from ..scrapers.base import JobPosting
from ..services.claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class HiringManagerFinder:
    """
    Identifies potential hiring managers and stakeholders for job applications.
    """

    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client

    async def research(self, job: JobPosting) -> dict:
        """
        Research hiring managers for a job.

        Args:
            job: The job posting

        Returns:
            {
                "likely_hiring_manager": {
                    "title": str,
                    "reasoning": str,
                    "linkedin_search": str
                },
                "other_stakeholders": list,
                "outreach_tips": str,
                "linkedin_searches": list[str]  # Ready-to-use search URLs
            }
        """
        logger.info(f"Researching hiring managers for {job.title} at {job.company}")

        try:
            result = await self.claude.research_hiring_managers(
                company=job.company,
                job_title=job.title,
                company_description=job.company_description,
            )

            # Add LinkedIn search URLs
            result["linkedin_searches"] = self._build_linkedin_urls(
                job.company,
                result
            )

            return result

        except Exception as e:
            logger.error(f"Error researching hiring managers: {e}")
            return self._default_research(job)

    def _build_linkedin_urls(self, company: str, research: dict) -> list[str]:
        """Build ready-to-use LinkedIn search URLs."""
        urls = []

        # Main hiring manager search
        hm = research.get("likely_hiring_manager", {})
        if hm.get("linkedin_search"):
            query = hm["linkedin_search"]
            urls.append({
                "title": hm.get("title", "Hiring Manager"),
                "url": self._linkedin_search_url(query),
                "query": query,
            })

        # Other stakeholders
        for stakeholder in research.get("other_stakeholders", []):
            if stakeholder.get("linkedin_search"):
                urls.append({
                    "title": stakeholder.get("title", "Stakeholder"),
                    "url": self._linkedin_search_url(stakeholder["linkedin_search"]),
                    "query": stakeholder["linkedin_search"],
                })

        return urls

    def _linkedin_search_url(self, query: str) -> str:
        """Build LinkedIn people search URL."""
        from urllib.parse import quote_plus
        return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"

    def _default_research(self, job: JobPosting) -> dict:
        """Default hiring manager research if AI fails."""
        company = job.company

        return {
            "likely_hiring_manager": {
                "title": "VP Finance / Head of Finance",
                "reasoning": "Finance roles typically report to VP/Head of Finance at startups",
                "linkedin_search": f'"{company}" "Head of Finance" OR "VP Finance"',
            },
            "other_stakeholders": [
                {
                    "title": "CFO",
                    "linkedin_search": f'"{company}" CFO',
                },
                {
                    "title": "CEO / Founder",
                    "linkedin_search": f'"{company}" CEO OR founder',
                },
            ],
            "outreach_tips": (
                "Send a personalized LinkedIn connection request mentioning "
                "your interest in the specific role. Keep it brief and professional."
            ),
            "linkedin_searches": [
                {
                    "title": "VP Finance / Head of Finance",
                    "url": self._linkedin_search_url(f'"{company}" "Head of Finance" OR "VP Finance"'),
                    "query": f'"{company}" "Head of Finance" OR "VP Finance"',
                },
                {
                    "title": "CFO",
                    "url": self._linkedin_search_url(f'"{company}" CFO'),
                    "query": f'"{company}" CFO',
                },
            ],
        }

    async def research_batch(
        self,
        jobs: list[JobPosting]
    ) -> list[tuple[JobPosting, dict]]:
        """
        Research hiring managers for multiple jobs.

        Args:
            jobs: List of job postings

        Returns:
            List of (job, research_result) tuples
        """
        results = []

        for job in jobs:
            try:
                research = await self.research(job)
                results.append((job, research))
            except Exception as e:
                logger.error(f"Failed to research HMs for {job.company}: {e}")
                results.append((job, self._default_research(job)))

        return results

    def format_research_report(self, job: JobPosting, research: dict) -> str:
        """
        Format research into a readable report.

        Args:
            job: The job posting
            research: Research results

        Returns:
            Markdown formatted report
        """
        hm = research.get("likely_hiring_manager", {})
        stakeholders = research.get("other_stakeholders", [])
        tips = research.get("outreach_tips", "")
        searches = research.get("linkedin_searches", [])

        report = f"""# Hiring Manager Research
## {job.title} at {job.company}

### Likely Hiring Manager
- **Title:** {hm.get('title', 'Unknown')}
- **Reasoning:** {hm.get('reasoning', 'N/A')}

### Other Stakeholders
"""
        for s in stakeholders:
            report += f"- {s.get('title', 'Unknown')}\n"

        report += f"""
### LinkedIn Searches
"""
        for search in searches:
            report += f"- [{search.get('title')}]({search.get('url')})\n"

        report += f"""
### Outreach Tips
{tips}

---
Job URL: {job.url}
"""
        return report
