"""
XMUOJ Problem Fetcher
Uses the REST API for fast, reliable problem data extraction.
API endpoint: GET /api/contest/problem?contest_id={id}
"""
import asyncio
import os
import re
import json
import requests
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup

from config import config


@dataclass
class ProblemInfo:
    """Represents a single problem's information."""
    problem_id: str = ""
    display_id: str = ""       # e.g., "LinK01"
    title: str = ""
    description: str = ""
    input_description: str = ""
    output_description: str = ""
    sample_input: str = ""
    sample_output: str = ""
    hint: str = ""
    time_limit: str = ""
    memory_limit: str = ""
    source: str = ""
    tags: list = field(default_factory=list)
    samples: list = field(default_factory=list)  # Raw samples from API

    @staticmethod
    def from_api(data: dict) -> 'ProblemInfo':
        """Create ProblemInfo from API response data."""
        problem = ProblemInfo(
            problem_id=str(data.get('id', '')),
            display_id=data.get('_id', ''),
            title=data.get('title', ''),
            description=ProblemInfo._clean_html(data.get('description', '')),
            input_description=ProblemInfo._clean_html(data.get('input_description', '')),
            output_description=ProblemInfo._clean_html(data.get('output_description', '')),
            hint=ProblemInfo._clean_html(data.get('hint', '')),
            time_limit=str(data.get('time_limit', '')),
            memory_limit=str(data.get('memory_limit', '')),
            source=data.get('source', ''),
            tags=data.get('tags', []),
            samples=data.get('samples', []),
        )

        # Extract first sample for easy access
        if problem.samples:
            first = problem.samples[0]
            problem.sample_input = first.get('input', '')
            problem.sample_output = first.get('output', '')

        return problem

    def to_prompt_text(self) -> str:
        """Convert problem info to a clean text format for AI prompting."""
        parts = [f"## Problem {self.display_id}: {self.title}\n"]

        if self.time_limit:
            parts.append(f"**Time Limit:** {self.time_limit}ms")
        if self.memory_limit:
            parts.append(f"**Memory Limit:** {self.memory_limit}MB")
        parts.append("")

        if self.description:
            parts.append(f"### Description:\n{self.description}\n")
        if self.input_description:
            parts.append(f"### Input Format:\n{self.input_description}\n")
        if self.output_description:
            parts.append(f"### Output Format:\n{self.output_description}\n")

        # List all samples
        for i, sample in enumerate(self.samples, 1):
            parts.append(f"### Sample {i}:")
            parts.append(f"Input:\n{sample.get('input', '')}")
            parts.append(f"Output:\n{sample.get('output', '')}")
            parts.append("")

        if self.hint:
            parts.append(f"### Hint:\n{self.hint}\n")

        return '\n'.join(parts)

    @staticmethod
    def _clean_html(html: str) -> str:
        """Strip HTML tags and decode entities."""
        if not html:
            return ""
        soup = BeautifulSoup(html, 'html.parser')
        for br in soup.find_all('br'):
            br.replace_with('\n')
        for p in soup.find_all('p'):
            p.append('\n')
        text = soup.get_text()
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


class ProblemFetcher:
    """Fetches problems from XMUOJ using the REST API."""

    def __init__(self, page=None):
        """page is optional — kept for compatibility with Playwright-based modules."""
        self.page = page
        self.api_base = config.api_base
        self.session = requests.Session()
        self.session.verify = False
        requests.packages.urllib3.disable_warnings()

    def set_cookies(self, cookies: dict):
        """Set session cookies from Playwright context."""
        self.session.cookies.update(cookies)

    def get_contest_problems(self, contest_id: int = None) -> list[ProblemInfo]:
        """
        Get the list of problems in a contest via API.
        Returns list of ProblemInfo with full details.
        """
        if contest_id is None:
            contest_id = config.contest_id

        print(f"[Fetcher] Getting problems for contest {contest_id} via API...")

        url = f"{self.api_base}/contest/problem?contest_id={contest_id}"
        try:
            r = self.session.get(url, timeout=15)
            if r.status_code != 200:
                print(f"[Fetcher] API error: {r.status_code} {r.text[:200]}")
                return []

            data = r.json()
            if data.get('error'):
                print(f"[Fetcher] API error: {data.get('data', '')[:200]}")
                return []

            if not isinstance(data.get('data'), list):
                print(f"[Fetcher] Unexpected response: {str(data.get('data', ''))[:200]}")
                return []
                print(f"[Fetcher] API error: {data['error']}")
                return []

            problems_data = data.get('data', [])
            problems = [ProblemInfo.from_api(p) for p in problems_data]

            print(f"[Fetcher] Found {len(problems)} problems in contest {contest_id}")
            for p in problems[:5]:
                print(f"  #{p.problem_id} [{p.display_id}] {p.title}")
            if len(problems) > 5:
                print(f"  ... and {len(problems) - 5} more")

            return problems
        except Exception as e:
            print(f"[Fetcher] Error: {e}")
            return []

    async def get_problem_detail(self, problem_id: str, contest_id: int = None) -> ProblemInfo:
        """
        Get detailed information about a specific problem.
        Since the API returns full details in the list, this just filters.
        """
        if contest_id is None:
            contest_id = config.contest_id

        # Since the API returns full details, we can get all and filter
        all_problems = self.get_contest_problems(contest_id)
        for p in all_problems:
            if p.problem_id == str(problem_id) or p.display_id == str(problem_id):
                return p

        # If not found in list, try direct page scraping (fallback)
        if self.page:
            print(f"[Fetcher] API didn't find problem {problem_id}, trying page...")
            await self.page.goto(f"{config.base_url}/problem/{problem_id}")
            await asyncio.sleep(2)
            return ProblemInfo(problem_id=str(problem_id),
                              title=f"Problem {problem_id}")

        return ProblemInfo(problem_id=str(problem_id), title=f"Problem {problem_id}")

    async def get_all_problem_details(self, contest_id: int = None) -> list[ProblemInfo]:
        """Get detailed info for all problems in a contest (uses API)."""
        return self.get_contest_problems(contest_id)
