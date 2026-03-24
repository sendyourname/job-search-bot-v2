"""Configuration management for Job Search Bot."""

import os
import json
import tempfile
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


def get_google_credentials_path() -> str:
    """
    Get Google credentials path.

    Supports both:
    1. Local file path via GOOGLE_CREDENTIALS_PATH
    2. JSON content via GOOGLE_CREDENTIALS_JSON (for Railway/cloud deployment)
    """
    # Check for JSON content in environment (Railway)
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        # Write to temp file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        temp_file.write(creds_json)
        temp_file.close()
        return temp_file.name

    # Fall back to file path
    return os.environ.get("GOOGLE_CREDENTIALS_PATH", "./credentials.json")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    adzuna_app_id: Optional[str] = Field(None, env="ADZUNA_APP_ID")
    adzuna_app_key: Optional[str] = Field(None, env="ADZUNA_APP_KEY")

    # Google Drive
    google_credentials_path: str = Field(default_factory=get_google_credentials_path)
    google_drive_folder_id: str = Field(..., env="GOOGLE_DRIVE_FOLDER_ID")

    # Pushover
    pushover_user_key: str = Field(..., env="PUSHOVER_USER_KEY")
    pushover_api_token: str = Field(..., env="PUSHOVER_API_TOKEN")

    # LinkedIn (optional)
    linkedin_email: Optional[str] = Field(None, env="LINKEDIN_EMAIL")
    linkedin_password: Optional[str] = Field(None, env="LINKEDIN_PASSWORD")

    # Notification
    notification_phone: str = Field("6463694772", env="NOTIFICATION_PHONE")

    # Database
    database_url: str = Field("sqlite:///./jobs.db", env="DATABASE_URL")

    # Environment
    environment: str = Field("development", env="ENVIRONMENT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Job search criteria for Regan O'Connor
SEARCH_CRITERIA = {
    # Broad search queries for scrapers (LinkedIn fuzzy-matches, so fewer is better)
    "search_queries": [
        "Financial Analyst",
        "FP&A",
        "Strategic Finance",
        "Product Finance",
        "Head of Finance",
        "Finance Manager",
        "Finance Director",
        "Corporate Finance",
        "Product Partnerships",
        "Strategic Partnerships",
    ],
    # Full title list used for matching/filtering results
    "titles": [
        # Core FP&A roles
        "Financial Analyst",
        "Senior Financial Analyst",
        "Staff Financial Analyst",
        "Lead Financial Analyst",
        "FP&A Analyst",
        "FP&A Manager",
        "Senior FP&A",
        "FP&A Lead",
        # Strategic Finance
        "Strategic Finance",
        "Strategic Finance Analyst",
        "Strategic Finance Manager",
        "Strategic Finance Associate",
        # Product Finance
        "Product Finance",
        "Product Finance Manager",
        "Product Finance Analyst",
        # Leadership
        "Finance Manager",
        "Senior Finance Manager",
        "Head of Finance",
        "Finance Lead",
        "Director of Finance",
        "VP Finance",
        "Finance Director",
        # Broader searches
        "Corporate Finance",
        "Business Finance",
        "Finance Operations",
        # Product Partnerships
        "Product Partnerships",
        "Strategic Partnerships",
        "Partnerships Manager",
        "Product Partnership Manager",
        "Strategic Partnership Manager",
        "Head of Partnerships",
        "Business Development",
    ],
    "exclude_keywords": [
        "GTM Finance",
        "Sales Finance",
        "Revenue Operations",
        "RevOps",
        "Accounting Manager",
        "Controller",
        "Tax Manager",
        "Tax Analyst",
        "Payroll",
        "Bookkeeper",
        "Accounts Payable",
        "Accounts Receivable",
        "Collections",
        "Billing",
        "Junior",
        "Entry Level",
        "Intern",
        "Investment Banking",
        "Private Equity",
        "Hedge Fund",
        "Trader",
        "Quant",
    ],
    # Keywords that boost a job's score when found in the description
    "preferred_keywords": [
        "product finance",
        "cross-functional",
        "cross functional",
        "business partner",
        "stakeholder management",
        "procurement",
        "fp&a",
        "strategic finance",
        "product partnerships",
        "strategic partnerships",
        "partner management",
    ],
    # Keywords in descriptions that should penalize/skip a job
    "avoid_keywords": [
        "data visualization",
        "data visualisation",
        "market analysis",
        "market research",
        "equity research",
    ],
    # Companies to always exclude (FAANG, big tech, legacy)
    "excluded_companies": [
        "Nielsen", "NielsenIQ",
        # FAANG / Big Tech
        "Google", "Alphabet",
        "Apple",
        "Amazon", "AWS",
        "Meta", "Facebook",
        "Netflix",
        "Microsoft",
        "Nvidia",
        "Salesforce",
        "Adobe",
        "Oracle",
        "Uber",
        "Airbnb",
        "Spotify",
        "Twitch",
        "PayPal",
        "Intel",
        "IBM",
        "Cisco",
        "VMware",
        "SAP",
    ],
    # Company age filter
    "max_company_age_years": 30,
    # Companies exempt from age filter (well-known but still startup-ish)
    "exempt_companies": [
        "Stripe",
        "Figma",
        "Notion",
        "Datadog",
        "Brex",
    ],
    "locations": [
        "New York, NY",
        "New York City",
        "NYC",
        "Manhattan",
        "Brooklyn",
    ],
    "min_salary": 150000,
    "company_filters": {
        "stages": ["Seed", "Series A", "Series B", "Series C"],
        "industries": [
            "Technology",
            "Fintech",
            "SaaS",
            "AI",
            "Machine Learning",
            "Consumer Tech",
            "Enterprise Software",
            "B2B",
            "Marketplace",
        ],
        "min_employees": 15,
        "max_employees": 500,
    },
    "bonus_signals": [
        "recently funded",
        "YC",
        "Y Combinator",
        "a]6z",
        "Sequoia",
        "Andreessen",
        "interesting mission",
        "high growth",
    ],
}

# Candidate profile
CANDIDATE_PROFILE = {
    "name": "Regan O'Connor",
    "email": "reganmdoconnor@gmail.com",
    "phone": "(310) 963-6001",
    "linkedin": "linkedin.com/in/reganoconnor",
    "current_role": "Financial Analyst (FP&A)",
    "current_company": "Google",
    "current_team": "Search & Commerce",
    "years_experience": 6,
    "credentials": ["Chartered Accountant (CA)"],
    "education": "BCom - University of Sydney",
    "skills": [
        "SQL",
        "SAP",
        "Annual Planning",
        "Forecasting",
        "Budget Management",
        "P&L Analysis",
        "Cross-functional Partnership",
        "Financial Modeling",
        "Variance Analysis",
    ],
    "highlights": [
        "Led annual planning for Google Search and Commerce",
        "Managed $XXXM budget with 50+ cross-functional partners",
        "Drove operational improvements saving ~25hrs/month",
        "Experience across FP&A, controllership, and sales finance",
        "Chartered Accountant with Big 4 background (Deloitte)",
    ],
}

# Resume path
RESUME_PATH = Path(__file__).parent.parent / "data" / "resume.pdf"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
