"""
XMUOJ Submit Engine
Handles code submission and result monitoring.
Uses CodeMirror editor via Playwright for code input.
"""
import asyncio
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from config import config


class JudgeStatus(Enum):
    PENDING = "Pending"
    COMPILING = "Compiling"
    RUNNING = "Running & Judging"
    ACCEPTED = "Accepted"
    WRONG_ANSWER = "Wrong Answer"
    TIME_LIMIT_EXCEEDED = "Time Limit Exceeded"
    MEMORY_LIMIT_EXCEEDED = "Memory Limit Exceeded"
    RUNTIME_ERROR = "Runtime Error"
    COMPILE_ERROR = "Compile Error"
    OUTPUT_LIMIT_EXCEEDED = "Output Limit Exceeded"
    PRESENTATION_ERROR = "Presentation Error"
    SYSTEM_ERROR = "System Error"
    UNKNOWN = "Unknown"


@dataclass
class SubmissionResult:
    submission_id: str = ""
    problem_id: str = ""
    status: JudgeStatus = JudgeStatus.PENDING
    score: int = 0
    time_usage: str = ""
    memory_usage: str = ""
    error_message: str = ""
    submitted_at: str = ""
    judged_at: str = ""


class SubmitEngine:
    """Handles code submission to XMUOJ using Playwright."""

    LANGUAGE_MAP = {
        'c': 'C', 'cpp': 'C++', 'c++': 'C++',
        'java': 'Java', 'py': 'Python', 'python': 'Python',
    }

    def __init__(self, page):
        self.page = page

    async def submit(self, problem_id: str, code: str,
                     language: str = 'cpp',
                     contest_id: int = None) -> Optional[str]:
        """
        Submit code for a problem.
        Returns submission_id if successful, None otherwise.
        """
        if contest_id is None:
            contest_id = config.contest_id

        print(f"[Submit] Submitting {language} code for problem #{problem_id}...")

        # Navigate to problem page (this is where the submit form is)
        await self.page.goto(f"{config.base_url}/problem/{problem_id}",
                             wait_until='domcontentloaded')
        await asyncio.sleep(4)

        # Check if we need to enter contest password (for contest problems)
        pw_input = await self.page.query_selector('input[type="password"]')
        if pw_input:
            await pw_input.fill(config.contest_password)
            await pw_input.press('Enter')
            await asyncio.sleep(3)

        # Find the CodeMirror editor instance
        print("[Submit] Locating CodeMirror editor...")

        # Method 1: Use CodeMirror API via JavaScript
        code_set = await self._set_code_via_codemirror(code)

        # Method 2: If CodeMirror API fails, try clicking and pasting
        if not code_set:
            print("[Submit] Trying clipboard paste method...")
            code_set = await self._set_code_via_clipboard(code)

        # Method 3: Try the hidden textarea if visible
        if not code_set:
            print("[Submit] Trying direct textarea method...")
            textarea = await self.page.query_selector('textarea:visible, textarea')
            if textarea:
                await textarea.evaluate(f'el => el.style.display = "block"')
                await textarea.fill(code)
                code_set = True

        if not code_set:
            print("[Submit] ERROR: Could not input code!")
            return None

        print("[Submit] Code entered successfully!")

        # Select language if dropdown exists
        lang_selector = await self.page.query_selector('select, [name="language"]')
        if lang_selector:
            try:
                lang_value = self.LANGUAGE_MAP.get(language.lower(), 'C++')
                options = await lang_selector.query_selector_all('option')
                for opt in options:
                    text = (await opt.inner_text()).strip()
                    if lang_value.lower() in text.lower():
                        val = await opt.get_attribute('value')
                        if val:
                            await lang_selector.select_option(value=val)
                            print(f"[Submit] Language: {text}")
                            break
            except Exception as e:
                print(f"[Submit] Language select skipped: {e}")

        # Enable O2 optimization
        o2_checkbox = await self.page.query_selector('input[type="checkbox"]')
        if o2_checkbox:
            is_checked = await o2_checkbox.is_checked()
            if not is_checked:
                await o2_checkbox.click()
                print("[Submit] Enabled O2 optimization")

        # Click submit button
        print("[Submit] Clicking submit...")
        submit_btn = None
        buttons = await self.page.query_selector_all('button')
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if '提交' in text or 'Submit' in text:
                submit_btn = btn
                break

        if not submit_btn:
            print("[Submit] ERROR: Submit button not found!")
            return None

        # Set up response capture before clicking
        submission_id = None

        async def on_response(response):
            nonlocal submission_id
            if '/api/' in response.url:
                try:
                    body = await response.text()
                    # Look for submission ID
                    id_match = re.search(r'"submission_id"\s*:\s*"?(\w+)"?', body)
                    if not id_match:
                        id_match = re.search(r'"id"\s*:\s*"?(\d+)"?', body)
                    if id_match:
                        submission_id = id_match.group(1)
                        print(f"[Submit] ID captured: {submission_id}")
                except:
                    pass

        self.page.on('response', on_response)
        await submit_btn.click()
        await asyncio.sleep(5)

        # If API didn't give us the ID, try page content
        if not submission_id:
            page_text = await self.page.content()
            # Look for submission in status page redirect
            id_match = re.search(r'submission[/\s]+(\d+)', page_text)
            if id_match:
                submission_id = id_match.group(1)

        if submission_id:
            print(f"[Submit] Success! Submission ID: {submission_id}")
        else:
            print("[Submit] WARNING: Could not determine submission ID")

        return submission_id

    async def _set_code_via_codemirror(self, code: str) -> bool:
        """Set code using CodeMirror's JavaScript API."""
        try:
            result = await self.page.evaluate(f'''
                (() => {{
                    // Find CodeMirror instance
                    const editors = document.querySelectorAll('.CodeMirror');
                    for (let el of editors) {{
                        if (el.CodeMirror) {{
                            el.CodeMirror.setValue({json.dumps(code)});
                            return true;
                        }}
                    }}
                    // Try global CodeMirror instances
                    if (typeof window.CodeMirror !== 'undefined') {{
                        return false;
                    }}
                    return false;
                }})()
            ''')
            if result:
                print("[Submit] Code set via CodeMirror API")
                return True
        except Exception as e:
            print(f"[Submit] CodeMirror API failed: {e}")
        return False

    async def _set_code_via_clipboard(self, code: str) -> bool:
        """Set code using clipboard paste into CodeMirror."""
        try:
            # Click on CodeMirror to focus
            cm = await self.page.query_selector('.CodeMirror')
            if not cm:
                return False

            await cm.click()
            await asyncio.sleep(0.3)

            # Use clipboard API to set content
            await self.page.evaluate(f'''
                navigator.clipboard.writeText({json.dumps(code)});
            ''')
            await asyncio.sleep(0.3)

            # Select all and paste
            await self.page.keyboard.press('Control+a')
            await asyncio.sleep(0.2)
            await self.page.keyboard.press('Control+v')
            await asyncio.sleep(0.5)

            print("[Submit] Code pasted via clipboard")
            return True
        except Exception as e:
            print(f"[Submit] Clipboard method failed: {e}")
            return False


class ResultMonitor:
    """Monitors judging results for submissions."""

    def __init__(self, page):
        self.page = page

    async def wait_for_result(self, submission_id: str,
                              max_wait_seconds: int = 120,
                              poll_interval: float = 3.0) -> SubmissionResult:
        """Poll for judging result until completion."""
        print(f"[Monitor] Waiting for result of #{submission_id}...")

        start_time = asyncio.get_event_loop().time()
        last_status = ""

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait_seconds:
                print(f"[Monitor] Timeout after {max_wait_seconds}s")
                return SubmissionResult(
                    submission_id=submission_id,
                    status=JudgeStatus.UNKNOWN,
                    error_message="Timeout waiting for result"
                )

            # Navigate to status page
            await self.page.goto(
                f"{config.base_url}/status",
                wait_until='domcontentloaded'
            )
            await asyncio.sleep(poll_interval)

            # Parse the status table
            result = await self._parse_status_page(submission_id)

            if result.status.value != last_status:
                print(f"[Monitor] Status: {result.status.value} (score: {result.score})")
                last_status = result.status.value

            # Check if judging is complete
            if result.status not in [JudgeStatus.PENDING,
                                       JudgeStatus.COMPILING,
                                       JudgeStatus.RUNNING]:
                print(f"[Monitor] Final: {result.status.value} (score: {result.score})")
                return result

            await asyncio.sleep(poll_interval)

    async def _parse_status_page(self, submission_id: str) -> SubmissionResult:
        """Parse submission status from page."""
        result = SubmissionResult(submission_id=submission_id)

        try:
            content = await self.page.content()

            # Status patterns
            status_patterns = [
                (JudgeStatus.ACCEPTED, r'Accepted|AC|答案正确|通过'),
                (JudgeStatus.WRONG_ANSWER, r'Wrong Answer|WA|答案错误'),
                (JudgeStatus.TIME_LIMIT_EXCEEDED, r'Time Limit Exceed|TLE|超时'),
                (JudgeStatus.MEMORY_LIMIT_EXCEEDED, r'Memory Limit Exceed|MLE|内存超限'),
                (JudgeStatus.RUNTIME_ERROR, r'Runtime Error|RE|运行错误'),
                (JudgeStatus.COMPILE_ERROR, r'Compil\w* Error|CE|编译错误'),
                (JudgeStatus.COMPILING, r'Compiling|编译中'),
                (JudgeStatus.RUNNING, r'Running|运行中|Judging|评测中'),
                (JudgeStatus.PENDING, r'Pending|等待|排队'),
            ]

            for status, pattern in status_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    result.status = status
                    break

            # Extract score
            score_match = re.search(r'score[:\s]*(\d+)', content, re.IGNORECASE)
            if score_match:
                result.score = int(score_match.group(1))
            elif result.status == JudgeStatus.ACCEPTED:
                result.score = 100

            # Extract error message
            error_section = re.search(
                r'(error|错误|stderr)[:\s]*(.*?)(?=\n\n|\Z)',
                content, re.IGNORECASE | re.DOTALL
            )
            if error_section:
                result.error_message = error_section.group(2).strip()[:500]

        except Exception as e:
            print(f"[Monitor] Parse error: {e}")

        return result
