"""Notification service using Pushover."""

import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class Notifier:
    """
    Push notification service using Pushover.

    Pushover is a simple push notification service that costs $5 one-time
    for the mobile app. API is free to use.

    Setup:
    1. Download Pushover app on your phone
    2. Create account at pushover.net
    3. Get your User Key from the dashboard
    4. Create an Application to get an API Token
    """

    PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"

    def __init__(self, user_key: str, api_token: str):
        """
        Initialize Pushover notifier.

        Args:
            user_key: Your Pushover user key
            api_token: Your application API token
        """
        self.user_key = user_key
        self.api_token = api_token
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send(
        self,
        title: str,
        message: str,
        url: Optional[str] = None,
        url_title: Optional[str] = None,
        priority: int = 0,
        html: bool = False,
    ) -> bool:
        """
        Send a push notification.

        Args:
            title: Notification title
            message: Notification message
            url: Optional URL to include
            url_title: Title for the URL link
            priority: -2 (silent) to 2 (emergency)
            html: Enable HTML formatting in message

        Returns:
            True if sent successfully
        """
        payload = {
            "token": self.api_token,
            "user": self.user_key,
            "title": title,
            "message": message,
            "priority": priority,
        }

        if html:
            payload["html"] = 1

        if url:
            payload["url"] = url
            if url_title:
                payload["url_title"] = url_title

        try:
            response = await self.client.post(self.PUSHOVER_API_URL, data=payload)
            response.raise_for_status()

            result = response.json()
            if result.get("status") == 1:
                logger.info(f"Notification sent: {title}")
                return True
            else:
                logger.error(f"Pushover error: {result}")
                return False

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    async def notify_new_jobs(
        self,
        jobs_count: int,
        top_jobs: list[dict],
        drive_folder_url: Optional[str] = None,
    ) -> bool:
        """
        Send notification about new job matches.

        Args:
            jobs_count: Total number of new matches
            top_jobs: List of top job matches with details
            drive_folder_url: URL to Google Drive folder with details

        Returns:
            True if sent successfully
        """
        if jobs_count == 0:
            return True  # Nothing to notify

        # Build message
        title = f"🎯 {jobs_count} New Job Match{'es' if jobs_count > 1 else ''}!"

        lines = []
        for job in top_jobs[:5]:  # Top 5 jobs
            company = job.get("company", "Unknown")
            job_title = job.get("title", "Unknown")
            score = job.get("score", "?")
            lines.append(f"• {company}: {job_title} ({score}/10)")

        message = "\n".join(lines)

        if jobs_count > 5:
            message += f"\n\n+{jobs_count - 5} more matches"

        # Add Drive link
        url = drive_folder_url
        url_title = "View Cover Letters & Details"

        return await self.send(
            title=title,
            message=message,
            url=url,
            url_title=url_title,
            priority=1 if jobs_count >= 3 else 0,  # Higher priority for multiple matches
        )

    async def notify_error(self, error_message: str) -> bool:
        """
        Send error notification.

        Args:
            error_message: Error description

        Returns:
            True if sent successfully
        """
        return await self.send(
            title="⚠️ Job Search Bot Error",
            message=error_message,
            priority=-1,  # Low priority for errors
        )

    async def notify_daily_summary(
        self,
        total_scraped: int,
        matches_found: int,
        cover_letters_generated: int,
    ) -> bool:
        """
        Send daily summary notification.

        Args:
            total_scraped: Total jobs scraped
            matches_found: Jobs matching criteria
            cover_letters_generated: Cover letters created

        Returns:
            True if sent successfully
        """
        title = "📊 Daily Job Search Summary"

        message = f"""Jobs scraped: {total_scraped}
Matches found: {matches_found}
Cover letters: {cover_letters_generated}"""

        return await self.send(
            title=title,
            message=message,
            priority=-1,  # Low priority for summary
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class ConsoleNotifier:
    """
    Fallback notifier that prints to console.
    Useful for testing without Pushover setup.
    """

    async def send(self, title: str, message: str, **kwargs) -> bool:
        print(f"\n{'='*50}")
        print(f"📱 NOTIFICATION: {title}")
        print(f"{'='*50}")
        print(message)
        if kwargs.get("url"):
            print(f"\nLink: {kwargs['url']}")
        print(f"{'='*50}\n")
        return True

    async def notify_new_jobs(self, jobs_count: int, top_jobs: list, **kwargs) -> bool:
        if jobs_count == 0:
            print("No new job matches today.")
            return True

        lines = [f"Found {jobs_count} new job matches:"]
        for job in top_jobs[:5]:
            lines.append(f"  • {job.get('company')}: {job.get('title')}")
        return await self.send("New Job Matches", "\n".join(lines), **kwargs)

    async def notify_error(self, error_message: str) -> bool:
        return await self.send("Error", error_message)

    async def notify_daily_summary(self, **kwargs) -> bool:
        return await self.send("Daily Summary", str(kwargs))

    async def close(self):
        pass
