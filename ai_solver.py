"""
XMUOJ AI Code Generator
Uses DeepSeek V4 Pro via Anthropic-compatible API (CC Switch).
Reads API credentials from Claude Code settings or environment variables.
"""
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from anthropic.types import Message

from config import config
from fetcher import ProblemInfo


@dataclass
class AIGeneratedCode:
    """AI-generated solution code."""
    code: str = ""
    language: str = "cpp"
    confidence: float = 0.0


class AISolver:
    """
    Generates code solutions using DeepSeek V4 Pro via Anthropic-compatible API.
    API credentials are read from Claude Code's CC Switch configuration.
    """

    SYSTEM_PROMPT = """You are a competitive programming expert. You will be given a programming problem and must produce a correct solution in C++.

## CRITICAL REQUIREMENTS:
1. Write the solution in C++ (C++17 standard)
2. Include ALL necessary #include directives
3. Use fast I/O: ios_base::sync_with_stdio(false), cin.tie(nullptr)
4. Handle ALL edge cases carefully
5. Use long long for large numbers (constraints > 2^31)
6. Add brief inline comments explaining the algorithm

## OUTPUT FORMAT:
Respond with ONLY the C++ code wrapped in ```cpp ... ``` markers.
NO explanations, NO analysis, NO text outside the code block.

## ALGORITHM GUIDELINES:
- First analyze constraints → choose appropriate O() complexity
- For OI-style problems, partial scoring matters
- Consider edge cases: empty input, single element, large values, negative numbers
- Use standard library: sort, binary_search, lower_bound, vector, map, set, queue, etc.
"""

    RETRY_PROMPT = """Your previous solution was judged:

**Status:** {status}
**Details:** {error}

The problem:

{problem_text}

Fix the issues and provide a CORRECTED solution.

Common causes by status:
- Wrong Answer: logic error, missed edge case, wrong data type, off-by-one
- Time Limit Exceeded: O() too slow, optimize algorithm, remove unnecessary work
- Runtime Error: array bounds, division by zero, null pointer, stack overflow
- Compile Error: syntax error, missing #include, C++ version mismatch

Output ONLY the corrected C++ code in ```cpp ... ``` markers."""

    def __init__(self):
        self.solutions_dir = os.path.join(config.output_dir, "solutions")
        self.prompts_dir = os.path.join(config.output_dir, "prompts")
        self.responses_dir = os.path.join(config.output_dir, "responses")

    def _ensure_dirs(self):
        """Ensure output directories exist (called before each use)."""
        os.makedirs(self.solutions_dir, exist_ok=True)
        os.makedirs(self.prompts_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

        # Initialize API client from Claude Code settings
        self.client = self._init_client()

    def _init_client(self) -> Optional[Anthropic]:
        """Initialize API client. Reads credentials from multiple sources.

        Priority: env vars > .env file > Claude Code settings.json
        Supports two key name formats:
          - DEEPSEEK_API_KEY (recommended for standalone use)
          - ANTHROPIC_AUTH_TOKEN (used by Claude Code CC Switch)
        """
        # Try multiple key/env names
        api_key = os.getenv("DEEPSEEK_API_KEY", "") or os.getenv("ANTHROPIC_AUTH_TOKEN", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "") or os.getenv("ANTHROPIC_BASE_URL", "")

        # If base_url not set, default to DeepSeek's Anthropic-compatible endpoint
        if api_key and not base_url:
            base_url = "https://api.deepseek.com/anthropic"

        # Fallback: Claude Code settings.json
        if not api_key or not base_url:
            settings_path = os.path.join(
                os.path.expanduser("~"), ".claude", "settings.json"
            )
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, 'r') as f:
                        settings = json.load(f)
                    cc_env = settings.get('env', {})
                    if not api_key:
                        api_key = cc_env.get('ANTHROPIC_AUTH_TOKEN', '')
                    if not base_url:
                        base_url = cc_env.get('ANTHROPIC_BASE_URL', '')
                except Exception:
                    pass

        if api_key:
            print(f"[AI] API ready: {base_url}")
            return Anthropic(api_key=api_key, base_url=base_url)

        print("[AI] 未找到 AI 密钥！请在 .env 中添加:")
        print("     DEEPSEEK_API_KEY=sk-你的密钥")
        print("     获取地址: https://platform.deepseek.com")
        return None

    def generate_solution(self, problem: ProblemInfo,
                          previous_attempts: list = None) -> Optional[AIGeneratedCode]:
        """
        Generate a solution for a problem.
        Uses API if available, falls back to file-based protocol.
        """
        self._ensure_dirs()
        if previous_attempts is None:
            previous_attempts = []

        is_retry = len(previous_attempts) > 0

        if is_retry:
            last_attempt = previous_attempts[-1]
            prompt = self.RETRY_PROMPT.format(
                status=last_attempt.get('status', 'Unknown'),
                error=last_attempt.get('error', 'No details'),
                problem_text=problem.to_prompt_text(),
            )
        else:
            prompt = f"{self.SYSTEM_PROMPT}\n\n## Problem:\n\n{problem.to_prompt_text()}"

        suffix = 'retry' if is_retry else 'initial'
        print(f"[AI] {'Retrying' if is_retry else 'Generating'} problem #{problem.problem_id}...")

        # Save prompt
        prompt_file = os.path.join(
            self.solutions_dir,
            f"problem_{problem.problem_id}_prompt_{suffix}.txt"
        )
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)

        # Generate code
        code = None
        if self.client:
            code = self._call_api(prompt)
        else:
            code = self._call_file_based(prompt, problem.problem_id)

        if not code:
            print("[AI] FAILED to generate solution!")
            return None

        # Clean and save
        code = self._clean_code(code)

        attempt_num = len(previous_attempts) + 1
        code_file = os.path.join(
            self.solutions_dir,
            f"problem_{problem.problem_id}_attempt_{attempt_num}.cpp"
        )
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"[AI] Solution saved ({len(code)} chars)")

        return AIGeneratedCode(code=code, language='cpp')

    def _call_api(self, prompt: str, retry_count: int = 0) -> Optional[str]:
        """Call DeepSeek V4 Pro via Anthropic Messages API.
        Handles thinking-block-only responses by retrying with higher max_tokens.
        """
        try:
            max_tokens = 4096 + retry_count * 2048  # Increase on retry
            print(f"[AI] Calling DeepSeek API (max_tokens={max_tokens})...")
            response: Message = self.client.messages.create(
                model=config.ai_model,
                max_tokens=max_tokens,
                temperature=0.2,
                system="You are a competitive programming expert. Output ONLY C++ code in ```cpp fences.",
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            # Extract text from response (DeepSeek may include ThinkingBlock)
            text_blocks = [b for b in response.content if b.type == 'text']
            if not text_blocks:
                if retry_count < 2:
                    print(f"[AI] Thinking-only response, retrying with more tokens (retry {retry_count+1})...")
                    return self._call_api(prompt, retry_count + 1)
                print("[AI] No text in response after retries")
                return None
            output = text_blocks[0].text
            print(f"[AI] API returned {len(output)} chars")

            code = self._extract_code(output)
            if code:
                return code

            # If code extraction failed but we got output, it might be raw code
            if '#include' in output and 'int main' in output:
                start = output.find('#include')
                end = output.rfind('}')
                if start >= 0 and end > start:
                    return output[start:end+1].strip()

            print("[AI] Could not extract valid code from API response")
            return None

        except Exception as e:
            print(f"[AI] API error: {e}")
            return None

    def _call_file_based(self, prompt: str, problem_id: str) -> Optional[str]:
        """
        File-based protocol for interactive mode.
        Writes prompt to file and polls for response.
        Use AISolver.provide_solution() to respond from Claude Code session.
        """
        prompt_path = os.path.join(self.prompts_dir, f"{problem_id}.txt")
        response_path = os.path.join(self.responses_dir, f"{problem_id}.cpp")
        status_path = os.path.join(self.responses_dir, f"{problem_id}.status")

        # Write prompt
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        with open(status_path, 'w') as f:
            f.write('pending')

        print(f"[AI] Prompt → {prompt_path}")
        print(f"[AI] Waiting for response (max 10 min)...")

        max_wait = 600
        poll_interval = 3
        waited = 0

        while waited < max_wait:
            if os.path.exists(status_path):
                with open(status_path, 'r') as f:
                    status = f.read().strip()
                if status == 'done' and os.path.exists(response_path):
                    with open(response_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    print(f"[AI] Response received ({len(code)} chars)")
                    os.unlink(status_path)
                    return code
                elif status == 'error':
                    print("[AI] Generation reported error")
                    return None

            time.sleep(poll_interval)
            waited += poll_interval
            if waited % 30 == 0:
                print(f"[AI] Still waiting... ({waited}s)")

        print(f"[AI] Timeout ({max_wait}s)")
        return None

    def write_pending_prompts(self, problems: list[ProblemInfo]):
        """Write all problem prompts to files for batch processing."""
        for problem in problems:
            prompt = f"{self.SYSTEM_PROMPT}\n\n## Problem:\n\n{problem.to_prompt_text()}"
            prompt_path = os.path.join(self.prompts_dir, f"{problem.problem_id}.txt")
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt)
            print(f"[AI] Prepared: problem #{problem.problem_id}")

    @staticmethod
    def provide_solution(problem_id: str, code: str):
        """Provide a solution from Claude Code session to the file-based protocol."""
        responses_dir = os.path.join(config.output_dir, "responses")
        os.makedirs(responses_dir, exist_ok=True)

        response_path = os.path.join(responses_dir, f"{problem_id}.cpp")
        status_path = os.path.join(responses_dir, f"{problem_id}.status")

        with open(response_path, 'w', encoding='utf-8') as f:
            f.write(code)
        with open(status_path, 'w') as f:
            f.write('done')

        print(f"[AI] Solution for #{problem_id} written to {response_path}")

    @staticmethod
    def mark_error(problem_id: str, error: str = "Generation failed"):
        """Mark a problem as failed for the file-based protocol."""
        responses_dir = os.path.join(config.output_dir, "responses")
        os.makedirs(responses_dir, exist_ok=True)

        status_path = os.path.join(responses_dir, f"{problem_id}.status")
        with open(status_path, 'w') as f:
            f.write(f'error: {error}')

    def _extract_code(self, output: str) -> Optional[str]:
        """Extract code block from AI output."""
        # Try ```cpp ... ``` first
        match = re.search(r'```(?:cpp|c\+\+|c)\s*\n(.*?)\n\s*```', output, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try ``` ... ```
        match = re.search(r'```\s*\n(.*?)\n\s*```', output, re.DOTALL)
        if match:
            code = match.group(1).strip()
            if '#include' in code or 'int main' in code or 'public class' in code:
                return code

        return None

    def _clean_code(self, code: str) -> str:
        """Clean up generated code."""
        # Remove text before first #include
        include_pos = code.find('#include')
        if include_pos > 0:
            # Check if there's non-comment text before #include
            before = code[:include_pos].strip()
            if before and not before.startswith('//'):
                code = code[include_pos:]

        # Remove trailing non-code text
        lines = code.split('\n')
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines).strip()

    def analyze_error(self, problem: ProblemInfo, error_info: dict) -> str:
        """Analyze judging error and provide debug guidance."""
        status = error_info.get('status', 'Unknown')
        error_msg = error_info.get('error', '')

        if 'Wrong Answer' in status:
            return (
                "WRONG ANSWER: The output is incorrect.\n"
                "- Verify algorithm correctness on ALL edge cases\n"
                "- Check input parsing (whitespace, newlines)\n"
                "- Verify output format matches exactly\n"
                "- Consider overflow with large values → use long long\n"
                "- Double-check boundary conditions"
            )
        elif 'Time Limit' in status:
            return (
                "TIME LIMIT EXCEEDED: Algorithm too slow.\n"
                "- Analyze: can you reduce from O(n²) to O(n log n)?\n"
                "- Use fast I/O: sync_with_stdio(false)\n"
                "- Avoid unnecessary copies, use references\n"
                "- Consider more efficient data structures"
            )
        elif 'Runtime Error' in status:
            return (
                "RUNTIME ERROR: Program crashed.\n"
                "- Check array index bounds (especially with 0-indexed vs 1-indexed)\n"
                "- Division by zero?\n"
                "- Recursion too deep? Use iterative approach\n"
                "- Null pointer or uninitialized variable?"
            )
        elif 'Compile Error' in status:
            return f"COMPILE ERROR:\n{error_msg}\n- Check syntax and includes"
        elif 'Memory Limit' in status:
            return (
                "MEMORY LIMIT EXCEEDED: Too much memory used.\n"
                "- Use more memory-efficient structures\n"
                "- Consider streaming/on-the-fly processing\n"
                "- Watch for unnecessary copies of large data"
            )

        return f"Status: {status}\n{error_msg}"
