"""LinkedIn job scraper using Playwright."""

import asyncio
import re
import logging
from typing import Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote_plus

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, JobPosting, JobSource

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """
    LinkedIn job scraper using Playwright for browser automation.

    Note: LinkedIn has anti-scraping measures. This scraper uses the public
    job search (no login required) which has limited results. For better results,
    consider using LinkedIn's official Job Search API if you have access.
    """

    source = JobSource.LINKEDIN
    BASE_URL = "https://www.linkedin.com/jobs/search"

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
        max_results: int = 100,
        posted_within_days: int = 7,
        **kwargs
    ) -> list[JobPosting]:
        """
        Search LinkedIn for jobs.

        Args:
            titles: Job titles to search for
            locations: Locations to search in
            max_results: Max results per title
            posted_within_days: Only get jobs posted within N days

        Returns:
            List of JobPosting objects
        """
        await self._ensure_browser()
        jobs = []

        # Calculate results per title to hit target
        results_per_title = max(10, max_results // len(titles))

        for title in titles:
            for location in locations[:1]:  # Just use first location
                try:
                    results = await self._search_single(
                        title=title,
                        location=location,
                        max_results=results_per_title,
                        posted_within_days=posted_within_days,
                    )
                    jobs.extend(results)
                    await asyncio.sleep(1.5)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error searching LinkedIn for '{title}': {e}")

        # Deduplicate
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
        max_results: int = 25,
        posted_within_days: int = 7,
    ) -> list[JobPosting]:
        """Search for a single title/location combo."""
        page = await self.browser.new_page()

        try:
            # Build search URL
            # f_TPR: time posted filter (r86400 = 24hrs, r604800 = 7 days)
            time_filter = f"r{posted_within_days * 86400}"

            # Search both remote and NYC-based jobs
            params = {
                "keywords": title,
                "location": location,
                "f_TPR": time_filter,
                "sortBy": "DD",  # Sort by date
            }

            url = f"{self.BASE_URL}?{urlencode(params)}"
            logger.info(f"LinkedIn: Searching for '{title}' in '{location}'")

            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(3)  # Wait for JS rendering

            # Scroll more to load more results
            for _ in range(5):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(0.8)
                # Click "See more jobs" button if present
                try:
                    see_more = await page.query_selector("button.infinite-scroller__show-more-button")
                    if see_more:
                        await see_more.click()
                        await asyncio.sleep(1)
                except:
                    pass

            # Get job cards
            job_cards = await page.query_selector_all(".job-search-card")
            jobs = []

            for card in job_cards[:max_results]:
                try:
                    job = await self._parse_job_card(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.debug(f"Error parsing job card: {e}")

            logger.info(f"LinkedIn: Found {len(jobs)} jobs for '{title}'")
            return jobs

        except PlaywrightTimeout:
            logger.warning(f"LinkedIn: Timeout searching for '{title}'")
            return []
        finally:
            await page.close()

    async def _parse_job_card(self, card) -> Optional[JobPosting]:
        """Parse a LinkedIn job card element."""
        try:
            # Get job link and ID
            link_elem = await card.query_selector("a.base-card__full-link")
            if not link_elem:
                return None

            job_url = await link_elem.get_attribute("href")
            if not job_url:
                return None

            # Extract job ID from URL
            job_id_match = re.search(r"/view/(\d+)", job_url)
            job_id = job_id_match.group(1) if job_id_match else job_url

            # Get title
            title_elem = await card.query_selector(".base-search-card__title")
            title = await title_elem.inner_text() if title_elem else "Unknown"

            # Get company
            company_elem = await card.query_selector(".base-search-card__subtitle")
            company = await company_elem.inner_text() if company_elem else "Unknown"

            # Get location
            location_elem = await card.query_selector(".job-search-card__location")
            location = await location_elem.inner_text() if location_elem else ""

            # Check if remote
            is_remote = "remote" in location.lower()

            # Get posted date
            date_elem = await card.query_selector("time")
            posted_date = None
            if date_elem:
                datetime_attr = await date_elem.get_attribute("datetime")
                if datetime_attr:
                    try:
                        posted_date = datetime.fromisoformat(datetime_attr)
                    except:
                        pass

            return JobPosting(
                id=self._generate_job_id(self.source, job_id),
                title=title.strip(),
                company=company.strip(),
                url=job_url.split("?")[0],  # Clean URL
                source=self.source,
                location=location.strip(),
                posted_date=posted_date,
                is_remote=is_remote,
            )

        except Exception as e:
            logger.error(f"Error parsing LinkedIn job card: {e}")
            return None

    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        """Get detailed job information from job page."""
        await self._ensure_browser()
        page = await self.browser.new_page()

        try:
            await page.goto(job_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # Get job description
            desc_elem = await page.query_selector(".description__text")
            description = ""
            if desc_elem:
                description = await desc_elem.inner_text()

            # Get company info
            company_elem = await page.query_selector(".topcard__org-name-link")
            company = ""
            company_url = ""
            if company_elem:
                company = await company_elem.inner_text()
                company_url = await company_elem.get_attribute("href") or ""

            # Get title
            title_elem = await page.query_selector(".topcard__title")
            title = await title_elem.inner_text() if title_elem else ""

            # Extract job ID
            job_id_match = re.search(r"/view/(\d+)", job_url)
            job_id = job_id_match.group(1) if job_id_match else job_url

            # Get location
            location_elem = await page.query_selector(".topcard__flavor--bullet")
            location = await location_elem.inner_text() if location_elem else ""

            return JobPosting(
                id=self._generate_job_id(self.source, job_id),
                title=title.strip(),
                company=company.strip(),
                url=job_url,
                source=self.source,
                description=description,
                location=location.strip(),
                company_url=company_url,
                is_remote="remote" in location.lower(),
            )

        except Exception as e:
            logger.error(f"Error getting LinkedIn job details: {e}")
            return None
        finally:
            await page.close()

    async def close(self):
        """Close browser and playwright."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
