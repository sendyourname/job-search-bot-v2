"""Adzuna API client for job searching."""

import httpx
from typing import Optional
from datetime import datetime
import logging

from .base import BaseScraper, JobPosting, JobSource

logger = logging.getLogger(__name__)


class AdzunaScraper(BaseScraper):
    """
    Adzuna job search API client.

    Adzuna aggregates jobs from many sources and has a free API tier.
    Sign up at: https://developer.adzuna.com/
    """

    source = JobSource.ADZUNA
    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def __init__(self, app_id: str, app_key: str):
        self.app_id = app_id
        self.app_key = app_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def search(
        self,
        titles: list[str],
        locations: list[str],
        min_salary: int = 0,
        max_results: int = 50,
        **kwargs
    ) -> list[JobPosting]:
        """
        Search for jobs using Adzuna API.

        Args:
            titles: Job titles to search for
            locations: Locations (will use first one)
            min_salary: Minimum salary filter
            max_results: Maximum number of results

        Returns:
            List of JobPosting objects
        """
        jobs = []

        for title in titles:
            try:
                results = await self._search_single(
                    title=title,
                    location=locations[0] if locations else "New York",
                    min_salary=min_salary,
                    max_results=max_results // len(titles)
                )
                jobs.extend(results)
            except Exception as e:
                logger.error(f"Error searching Adzuna for '{title}': {e}")

        # Deduplicate by job ID
        seen_ids = set()
        unique_jobs = []
        for job in jobs:
            if job.id not in seen_ids:
                seen_ids.add(job.id)
                unique_jobs.append(job)

        return unique_jobs

    async def _search_single(
        self,
        title: str,
        location: str,
        min_salary: int = 0,
        max_results: int = 20
    ) -> list[JobPosting]:
        """Search for a single title."""
        # US jobs endpoint
        url = f"{self.BASE_URL}/us/search/1"

        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": title,
            "where": location,
            "results_per_page": max_results,
            "content-type": "application/json",
            "sort_by": "date",
        }

        if min_salary > 0:
            params["salary_min"] = min_salary

        response = await self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        jobs = []
        for result in data.get("results", []):
            job = self._parse_job(result)
            if job:
                jobs.append(job)

        logger.info(f"Adzuna: Found {len(jobs)} jobs for '{title}'")
        return jobs

    def _parse_job(self, data: dict) -> Optional[JobPosting]:
        """Parse Adzuna API result into JobPosting."""
        try:
            job_id = str(data.get("id", ""))
            if not job_id:
                return None

            # Parse salary
            salary_min = data.get("salary_min")
            salary_max = data.get("salary_max")

            # Parse date
            created = data.get("created")
            posted_date = None
            if created:
                try:
                    posted_date = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except:
                    pass

            # Check if remote
            location = data.get("location", {}).get("display_name", "")
            is_remote = "remote" in location.lower() or "remote" in data.get("title", "").lower()

            return JobPosting(
                id=self._generate_job_id(self.source, job_id),
                title=data.get("title", ""),
                company=data.get("company", {}).get("display_name", "Unknown"),
                url=data.get("redirect_url", ""),
                source=self.source,
                description=data.get("description", ""),
                location=location,
                salary_min=int(salary_min) if salary_min else None,
                salary_max=int(salary_max) if salary_max else None,
                posted_date=posted_date,
                is_remote=is_remote,
                raw_data=data,
            )
        except Exception as e:
            logger.error(f"Error parsing Adzuna job: {e}")
            return None

    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        """
        Get detailed job information.
        Note: Adzuna redirects to the original source, so we can't get more details easily.
        """
        return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
