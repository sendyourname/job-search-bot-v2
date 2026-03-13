"""Claude API client for AI-powered job processing."""

import logging
from typing import Optional
import anthropic

logger = logging.getLogger(__name__)


class ClaudeClient:
    """
    Wrapper for Anthropic's Claude API.

    Handles all AI-powered tasks: job matching, cover letter generation,
    and hiring manager research.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key
            model: Model to use (default: claude-sonnet-4-20250514 for cost efficiency)
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a completion request to Claude.

        Args:
            prompt: User prompt
            system: System prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Claude's response text
        """
        try:
            messages = [{"role": "user", "content": prompt}]

            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": messages,
                "temperature": temperature,
            }

            if system:
                kwargs["system"] = system

            response = self.client.messages.create(**kwargs)
            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def analyze_job_match(
        self,
        job_title: str,
        job_description: str,
        company: str,
        candidate_profile: dict,
        search_criteria: dict,
    ) -> dict:
        """
        Analyze how well a job matches the candidate profile.

        Returns:
            {
                "score": 1-10,
                "summary": "Brief match summary",
                "pros": ["list", "of", "pros"],
                "cons": ["list", "of", "cons"],
                "recommendation": "apply" | "maybe" | "skip"
            }
        """
        preferred_kw = ', '.join(search_criteria.get('preferred_keywords', []))
        avoid_kw = ', '.join(search_criteria.get('avoid_keywords', []))
        exempt_companies = search_criteria.get('exempt_companies', [])
        max_age = search_criteria.get('max_company_age_years', 30)

        system = """You are a career advisor helping match job opportunities to candidates.
Analyze jobs objectively and provide honest assessments. Be concise."""

        prompt = f"""Analyze this job opportunity for the candidate:

## Job
- Title: {job_title}
- Company: {company}
- Description: {job_description[:3000]}

## Candidate Profile
- Current Role: {candidate_profile.get('current_role')} at {candidate_profile.get('current_company')}
- Years Experience: {candidate_profile.get('years_experience')}
- Skills: {', '.join(candidate_profile.get('skills', []))}
- Credentials: {', '.join(candidate_profile.get('credentials', []))}

## Search Criteria
- Target Titles: {', '.join(search_criteria.get('titles', [])[:5])}
- Excluded: {', '.join(search_criteria.get('exclude_keywords', [])[:5])}
- Min Salary: ${search_criteria.get('min_salary', 0):,}
- Preferred Company Stage: {', '.join(search_criteria.get('company_filters', {}).get('stages', []))}

## IMPORTANT Scoring Rules
- BOOST score if description mentions: {preferred_kw}
- PENALIZE score if the role is primarily focused on: {avoid_kw}
- Company must be less than {max_age} years old UNLESS it is a major tech company (e.g., {', '.join(exempt_companies[:8])})
- If the company is clearly an old/traditional/legacy company (founded before ~1996) and NOT a major tech company, set is_legacy_company to true

Respond in this exact JSON format:
{{
    "score": <1-10 integer>,
    "summary": "<1 sentence summary>",
    "pros": ["<pro 1>", "<pro 2>"],
    "cons": ["<con 1>", "<con 2>"],
    "recommendation": "<apply|maybe|skip>",
    "is_gtm_sales": <true if this is GTM/Sales Finance, false otherwise>,
    "is_legacy_company": <true if company is over {max_age} years old and NOT a major tech company>
}}"""

        response = await self.complete(prompt, system=system, temperature=0.3)

        # Parse JSON response
        import json
        try:
            # Find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse job match response: {response[:200]}")

        return {
            "score": 5,
            "summary": "Could not analyze",
            "pros": [],
            "cons": [],
            "recommendation": "maybe",
            "is_gtm_sales": False,
        }

    async def generate_cover_letter(
        self,
        job_title: str,
        job_description: str,
        company: str,
        company_description: str,
        candidate_profile: dict,
        resume_text: str,
    ) -> str:
        """
        Generate a personalized cover letter.

        Returns:
            Cover letter text (markdown formatted)
        """
        system = """You are an expert cover letter writer. Write compelling,
authentic cover letters that highlight relevant experience without being generic or sycophantic.
Keep letters concise (250-350 words). Use a professional but personable tone."""

        prompt = f"""Write a cover letter for this job application:

## Job
- Title: {job_title}
- Company: {company}
- About Company: {company_description[:500] if company_description else 'Tech startup'}
- Job Description: {job_description[:2000]}

## Candidate
- Name: {candidate_profile.get('name')}
- Current: {candidate_profile.get('current_role')} at {candidate_profile.get('current_company')} ({candidate_profile.get('current_team')})
- Experience: {candidate_profile.get('years_experience')} years

## Resume Highlights
{resume_text[:2000]}

## Key Points to Emphasize
{chr(10).join('- ' + h for h in candidate_profile.get('highlights', []))}

Write a cover letter that:
1. Opens with genuine interest in the company/role (not generic flattery)
2. Connects specific experience to the job requirements
3. Highlights 2-3 most relevant achievements
4. Shows understanding of startup environment
5. Ends with clear call to action

Format as a professional letter with paragraphs. Do not include addresses or date headers."""

        return await self.complete(prompt, system=system, temperature=0.7)

    async def research_hiring_managers(
        self,
        company: str,
        job_title: str,
        company_description: str = "",
    ) -> dict:
        """
        Research and identify potential hiring managers.

        Returns:
            {
                "likely_hiring_manager": {
                    "title": "VP Finance",
                    "reasoning": "...",
                    "linkedin_search": "search query"
                },
                "other_stakeholders": [
                    {"title": "CFO", "linkedin_search": "..."},
                    ...
                ],
                "outreach_tips": "..."
            }
        """
        system = """You are a networking expert helping identify key decision makers
for job applications at startups. Be practical and specific."""

        prompt = f"""Identify likely hiring managers and stakeholders for this role:

Company: {company}
Role: {job_title}
About: {company_description[:500] if company_description else 'Tech startup'}

Based on typical startup org structures, identify:
1. Who is most likely the direct hiring manager?
2. Who else might be involved in the hiring decision?
3. How to find them on LinkedIn?

Respond in JSON format:
{{
    "likely_hiring_manager": {{
        "title": "<most likely title>",
        "reasoning": "<why this person>",
        "linkedin_search": "<LinkedIn search query to find them>"
    }},
    "other_stakeholders": [
        {{"title": "<title>", "linkedin_search": "<search query>"}},
        ...
    ],
    "outreach_tips": "<brief advice for reaching out>"
}}"""

        response = await self.complete(prompt, system=system, temperature=0.5)

        import json
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse HM response: {response[:200]}")

        return {
            "likely_hiring_manager": {
                "title": "Head of Finance / VP Finance",
                "reasoning": "Typical finance org structure",
                "linkedin_search": f'"{company}" "Head of Finance" OR "VP Finance"',
            },
            "other_stakeholders": [
                {"title": "CFO", "linkedin_search": f'"{company}" CFO'},
                {"title": "CEO", "linkedin_search": f'"{company}" CEO founder'},
            ],
            "outreach_tips": "Connect with a personalized note mentioning specific interest in the role.",
        }
