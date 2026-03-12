"""SQLite database models for job tracking."""

import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logger = logging.getLogger(__name__)

Base = declarative_base()


class Job(Base):
    """Tracked job posting."""

    __tablename__ = "jobs"

    id = Column(String, primary_key=True)  # e.g., "linkedin:12345"
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    url = Column(String, nullable=False)
    source = Column(String, nullable=False)  # linkedin, wellfound, adzuna

    # Details
    description = Column(Text, default="")
    location = Column(String, default="")
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_text = Column(String, default="")
    company_stage = Column(String, default="")
    company_size = Column(String, default="")
    is_remote = Column(Boolean, default=False)

    # Analysis
    match_score = Column(Float, nullable=True)
    recommendation = Column(String, default="")  # apply, maybe, skip
    analysis_summary = Column(Text, default="")

    # Status
    status = Column(String, default="new")  # new, reviewed, applied, rejected
    cover_letter_generated = Column(Boolean, default=False)
    drive_folder_id = Column(String, default="")
    drive_folder_url = Column(String, default="")

    # Timestamps
    posted_date = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    analyzed_at = Column(DateTime, nullable=True)
    notified_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Job {self.title} at {self.company}>"


class Database:
    """Database manager for job tracking."""

    def __init__(self, database_url: str = "sqlite:///./jobs.db"):
        """
        Initialize database.

        Args:
            database_url: SQLAlchemy database URL
        """
        self.engine = create_engine(database_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()

    def job_exists(self, job_id: str) -> bool:
        """Check if a job already exists in the database."""
        with self.get_session() as session:
            return session.query(Job).filter(Job.id == job_id).first() is not None

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        with self.get_session() as session:
            return session.query(Job).filter(Job.id == job_id).first()

    def add_job(self, job_data: dict) -> Job:
        """
        Add a new job to the database.

        Args:
            job_data: Dictionary with job fields

        Returns:
            Created Job object
        """
        with self.get_session() as session:
            job = Job(**job_data)
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def update_job(self, job_id: str, **kwargs) -> Optional[Job]:
        """
        Update a job's fields.

        Args:
            job_id: Job ID
            **kwargs: Fields to update

        Returns:
            Updated Job or None
        """
        with self.get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                session.commit()
                session.refresh(job)
            return job

    def get_new_jobs(self) -> list[Job]:
        """Get all jobs with status 'new'."""
        with self.get_session() as session:
            return session.query(Job).filter(Job.status == "new").all()

    def get_jobs_to_notify(self) -> list[Job]:
        """Get jobs that need notification (analyzed but not notified)."""
        with self.get_session() as session:
            return session.query(Job).filter(
                Job.analyzed_at.isnot(None),
                Job.notified_at.is_(None),
                Job.recommendation.in_(["apply", "maybe"])
            ).all()

    def mark_notified(self, job_ids: list[str]) -> None:
        """Mark jobs as notified."""
        with self.get_session() as session:
            session.query(Job).filter(Job.id.in_(job_ids)).update(
                {Job.notified_at: datetime.utcnow()},
                synchronize_session=False
            )
            session.commit()

    def get_recent_jobs(
        self,
        limit: int = 50,
        recommendation: Optional[str] = None
    ) -> list[Job]:
        """
        Get recent jobs.

        Args:
            limit: Maximum number of jobs
            recommendation: Filter by recommendation (apply, maybe, skip)

        Returns:
            List of Job objects
        """
        with self.get_session() as session:
            query = session.query(Job).order_by(Job.scraped_at.desc())

            if recommendation:
                query = query.filter(Job.recommendation == recommendation)

            return query.limit(limit).all()

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self.get_session() as session:
            total = session.query(Job).count()
            by_recommendation = {}
            for rec in ["apply", "maybe", "skip", ""]:
                count = session.query(Job).filter(Job.recommendation == rec).count()
                if count > 0:
                    by_recommendation[rec or "unanalyzed"] = count

            by_source = {}
            for source in ["linkedin", "wellfound", "adzuna"]:
                count = session.query(Job).filter(Job.source == source).count()
                if count > 0:
                    by_source[source] = count

            return {
                "total_jobs": total,
                "by_recommendation": by_recommendation,
                "by_source": by_source,
            }

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """
        Remove jobs older than specified days.

        Args:
            days: Remove jobs older than this many days

        Returns:
            Number of jobs removed
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            count = session.query(Job).filter(Job.scraped_at < cutoff).delete()
            session.commit()
            return count
