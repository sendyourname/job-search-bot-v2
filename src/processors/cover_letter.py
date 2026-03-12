"""Cover letter generation using Claude AI."""

import logging
from typing import Optional
from pathlib import Path

from pypdf import PdfReader

from ..scrapers.base import JobPosting
from ..services.claude_client import ClaudeClient
from ..config import CANDIDATE_PROFILE, RESUME_PATH

logger = logging.getLogger(__name__)


class CoverLetterGenerator:
    """
    Generates personalized cover letters using Claude AI.
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
                return self._fallback_resume_text()

            reader = PdfReader(resume_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""

            return text

        except Exception as e:
            logger.error(f"Error extracting resume text: {e}")
            return self._fallback_resume_text()

    def _fallback_resume_text(self) -> str:
        """Fallback resume summary if PDF extraction fails."""
        return f"""
{CANDIDATE_PROFILE['name']}

Experience:
- {CANDIDATE_PROFILE['current_role']} at {CANDIDATE_PROFILE['current_company']} ({CANDIDATE_PROFILE['current_team']})
- {CANDIDATE_PROFILE['years_experience']} years of finance experience
- Previously at Deloitte (Corporate Advisory)

Highlights:
{chr(10).join('- ' + h for h in CANDIDATE_PROFILE['highlights'])}

Skills: {', '.join(CANDIDATE_PROFILE['skills'])}

Education: {CANDIDATE_PROFILE['education']}
Credentials: {', '.join(CANDIDATE_PROFILE['credentials'])}
"""

    async def generate(
        self,
        job: JobPosting,
        job_analysis: Optional[dict] = None,
    ) -> str:
        """
        Generate a personalized cover letter for a job.

        Args:
            job: The job posting
            job_analysis: Optional analysis from JobMatcher

        Returns:
            Cover letter text (markdown formatted)
        """
        logger.info(f"Generating cover letter for {job.title} at {job.company}")

        try:
            cover_letter = await self.claude.generate_cover_letter(
                job_title=job.title,
                job_description=job.description or f"{job.title} position",
                company=job.company,
                company_description=job.company_description,
                candidate_profile=CANDIDATE_PROFILE,
                resume_text=self.resume_text,
            )

            return self._format_cover_letter(cover_letter, job)

        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            raise

    def _format_cover_letter(self, content: str, job: JobPosting) -> str:
        """Format cover letter with metadata header."""
        header = f"""---
Generated Cover Letter
Job: {job.title}
Company: {job.company}
URL: {job.url}
Generated for: {CANDIDATE_PROFILE['name']}
---

"""
        return header + content

    async def generate_batch(
        self,
        jobs_with_analysis: list[tuple[JobPosting, dict]],
        only_recommended: bool = True,
    ) -> list[tuple[JobPosting, str]]:
        """
        Generate cover letters for multiple jobs.

        Args:
            jobs_with_analysis: List of (job, analysis) tuples
            only_recommended: Only generate for "apply" or "maybe" recommendations

        Returns:
            List of (job, cover_letter) tuples
        """
        results = []

        for job, analysis in jobs_with_analysis:
            recommendation = analysis.get("final_recommendation", "skip")

            if only_recommended and recommendation == "skip":
                continue

            try:
                cover_letter = await self.generate(job, analysis)
                results.append((job, cover_letter))
            except Exception as e:
                logger.error(f"Failed to generate cover letter for {job.company}: {e}")

        return results
