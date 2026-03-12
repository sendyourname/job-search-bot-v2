"""Base scraper interface for job sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class JobSource(Enum):
    """Job source platforms."""
    LINKEDIN = "linkedin"
    WELLFOUND = "wellfound"
    ADZUNA = "adzuna"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"


@dataclass
class JobPosting:
    """Represents a job posting."""

    # Required fields
    id: str
    title: str
    company: str
    url: str
    source: JobSource

    # Optional fields
    description: str = ""
    location: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_text: str = ""
    posted_date: Optional[datetime] = None
    company_size: Optional[str] = None
    company_stage: Optional[str] = None  # e.g., "Series A", "Series B"
    company_industry: Optional[str] = None
    company_description: str = ""
    company_url: str = ""
    is_remote: bool = False

    # Metadata
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    raw_data: dict = field(default_factory=dict)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, JobPosting):
            return self.id == other.id
        return False

    @property
    def salary_display(self) -> str:
        """Human-readable salary range."""
        if self.salary_text:
            return self.salary_text
        if self.salary_min and self.salary_max:
            return f"${self.salary_min:,} - ${self.salary_max:,}"
        if self.salary_min:
            return f"${self.salary_min:,}+"
        if self.salary_max:
            return f"Up to ${self.salary_max:,}"
        return "Not disclosed"


class BaseScraper(ABC):
    """Abstract base class for job scrapers."""

    source: JobSource

    @abstractmethod
    async def search(
        self,
        titles: list[str],
        locations: list[str],
        **kwargs
    ) -> list[JobPosting]:
        """
        Search for jobs matching the given criteria.

        Args:
            titles: List of job titles to search for
            locations: List of locations to search in
            **kwargs: Additional scraper-specific parameters

        Returns:
            List of JobPosting objects
        """
        pass

    @abstractmethod
    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        """
        Get detailed information about a specific job.

        Args:
            job_url: URL of the job posting

        Returns:
            JobPosting with full details, or None if not found
        """
        pass

    async def close(self):
        """Clean up resources. Override if needed."""
        pass

    def _generate_job_id(self, source: JobSource, unique_key: str) -> str:
        """Generate a unique job ID."""
        return f"{source.value}:{unique_key}"
