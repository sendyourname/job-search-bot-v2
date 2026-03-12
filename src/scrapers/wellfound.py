"""Wellfound (formerly AngelList Talent) scraper for startup jobs."""

import asyncio
import re
import logging
from typing import Optional
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, JobPosting, JobSource

logger = logging.getLogger(__name__)


class WellfoundScraper(BaseScraper):
    """
    Wellfound (AngelList) job scraper.

    Wellfound is excellent for startup jobs and includes funding stage info.
    """

    source = JobSource.WELLFOUND
    BASE_URL = "https://wellfound.com"

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.playwright = None

    async def _ensure_browser(self):
        """Initialize browser if not already done."""
        if self.browser is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            )

    async def search(
        self,
        titles: list[str],
        locations: list[str],
        max_results: int = 50,
        **kwargs
    ) -> list[JobPosting]:
        """
        Search Wellfound for startup jobs.

        Args:
            titles: Job titles to search for
            locations: Locations (e.g., ["New York", "Remote"])
            max_results: Maximum results to return

        Returns:
            List of JobPosting objects
        """
        await self._ensure_browser()
        jobs = []

        # Wellfound uses role-based searches
        finance_roles = [
            "finance",
            "financial-analyst",
            "fp-a",
            "strategic-finance",
        ]

        for role in finance_roles:
            try:
                results = await self._search_role(
                    role=role,
                    location="new-york" if "New York" in locations else None,
                    max_results=max_results // len(finance_roles),
                )
                jobs.extend(results)
                await asyncio.sleep(2)  # Rate limiting
            except Exception as e:
                logger.error(f"Error searching Wellfound for '{role}': {e}")

        # Deduplicate
        seen_ids = set()
        unique_jobs = []
        for job in jobs:
            if job.id not in seen_ids:
                seen_ids.add(job.id)
                unique_jobs.append(job)

        return unique_jobs

    async def _search_role(
        self,
        role: str,
        location: Optional[str] = None,
        max_results: int = 25,
    ) -> list[JobPosting]:
        """Search for a specific role."""
        page = await self.browser.new_page()

        try:
            # Build URL
            if location:
                url = f"{self.BASE_URL}/role/{role}/location/{location}"
            else:
                url = f"{self.BASE_URL}/role/{role}"

            logger.info(f"Wellfound: Searching {url}")
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Scroll to load more results
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)

            # Get job listings
            # Wellfound structure: job cards within startup cards
            job_cards = await page.query_selector_all("[data-test='StartupResult']")
            jobs = []

            for card in job_cards[:max_results]:
                try:
                    parsed_jobs = await self._parse_startup_card(card)
                    jobs.extend(parsed_jobs)
                except Exception as e:
                    logger.debug(f"Error parsing Wellfound card: {e}")

            logger.info(f"Wellfound: Found {len(jobs)} jobs for role '{role}'")
            return jobs

        except PlaywrightTimeout:
            logger.warning(f"Wellfound: Timeout searching for '{role}'")
            return []
        finally:
            await page.close()

    async def _parse_startup_card(self, card) -> list[JobPosting]:
        """Parse a Wellfound startup card (may contain multiple jobs)."""
        jobs = []

        try:
            # Get company info
            company_elem = await card.query_selector("a[data-test='StartupName']")
            company = await company_elem.inner_text() if company_elem else "Unknown"
            company_url = ""
            if company_elem:
                href = await company_elem.get_attribute("href")
                company_url = f"{self.BASE_URL}{href}" if href else ""

            # Get company stage/info
            stage_elem = await card.query_selector("[data-test='StartupFunding']")
            company_stage = await stage_elem.inner_text() if stage_elem else ""

            # Get company size
            size_elem = await card.query_selector("[data-test='StartupSize']")
            company_size = await size_elem.inner_text() if size_elem else ""

            # Get company description
            desc_elem = await card.query_selector("[data-test='StartupHighConcept']")
            company_description = await desc_elem.inner_text() if desc_elem else ""

            # Get job listings within this startup
            job_links = await card.query_selector_all("a[data-test='JobListingLink']")

            for job_link in job_links:
                try:
                    job_url = await job_link.get_attribute("href")
                    if job_url:
                        job_url = f"{self.BASE_URL}{job_url}" if job_url.startswith("/") else job_url

                    title_elem = await job_link.query_selector("[data-test='JobListingTitle']")
                    title = await title_elem.inner_text() if title_elem else ""

                    # Get salary
                    salary_elem = await job_link.query_selector("[data-test='JobListingComp']")
                    salary_text = await salary_elem.inner_text() if salary_elem else ""

                    # Parse salary range
                    salary_min, salary_max = self._parse_salary(salary_text)

                    # Get location
                    location_elem = await job_link.query_selector("[data-test='JobListingLocation']")
                    location = await location_elem.inner_text() if location_elem else ""

                    # Generate ID from URL
                    job_id = job_url.split("/")[-1] if job_url else f"{company}-{title}"

                    job = JobPosting(
                        id=self._generate_job_id(self.source, job_id),
                        title=title.strip(),
                        company=company.strip(),
                        url=job_url,
                        source=self.source,
                        location=location.strip(),
                        salary_min=salary_min,
                        salary_max=salary_max,
                        salary_text=salary_text,
                        company_stage=company_stage,
                        company_size=company_size,
                        company_description=company_description,
                        company_url=company_url,
                        is_remote="remote" in location.lower(),
                    )
                    jobs.append(job)

                except Exception as e:
                    logger.debug(f"Error parsing job link: {e}")

        except Exception as e:
            logger.error(f"Error parsing Wellfound startup card: {e}")

        return jobs

    def _parse_salary(self, salary_text: str) -> tuple[Optional[int], Optional[int]]:
        """Parse salary text like '$150K – $200K' into min/max integers."""
        if not salary_text:
            return None, None

        # Find all numbers with K suffix
        matches = re.findall(r'\$(\d+)K', salary_text)
        if len(matches) >= 2:
            return int(matches[0]) * 1000, int(matches[1]) * 1000
        elif len(matches) == 1:
            return int(matches[0]) * 1000, None

        # Try without K
        matches = re.findall(r'\$(\d{2,3}),?(\d{3})', salary_text)
        if matches:
            return int(matches[0][0] + matches[0][1]), None

        return None, None

    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        """Get detailed job information."""
        await self._ensure_browser()
        page = await self.browser.new_page()

        try:
            await page.goto(job_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # Get job description
            desc_elem = await page.query_selector("[data-test='JobDescription']")
            description = ""
            if desc_elem:
                description = await desc_elem.inner_text()

            # Get title
            title_elem = await page.query_selector("h1")
            title = await title_elem.inner_text() if title_elem else ""

            # Get company
            company_elem = await page.query_selector("[data-test='StartupName']")
            company = await company_elem.inner_text() if company_elem else ""

            # Generate ID
            job_id = job_url.split("/")[-1]

            return JobPosting(
                id=self._generate_job_id(self.source, job_id),
                title=title.strip(),
                company=company.strip(),
                url=job_url,
                source=self.source,
                description=description,
            )

        except Exception as e:
            logger.error(f"Error getting Wellfound job details: {e}")
            return None
        finally:
            await page.close()

    async def close(self):
        """Close browser and playwright."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
