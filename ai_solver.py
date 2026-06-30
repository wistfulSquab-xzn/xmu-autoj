"""
XMUOJ AI Code Generator
Supports OpenAI-compatible + Anthropic backends, multiple languages.
"""
import json, os, re, time
from dataclasses import dataclass
from typing import Optional

from config import config
from fetcher import ProblemInfo


LANG_CFG = {
    "cpp": {
        "name": "C++", "fence": "cpp", "submit": "C++",
        "prompt": """You are a competitive programming expert. Write a correct C++ solution.

## REQUIREMENTS:
- C++17. #include <bits/stdc++.h>
- Fast I/O: ios_base::sync_with_stdio(false); cin.tie(nullptr)
- Use long long for values > 2^31
- Brief inline comments

## OUTPUT: ONLY ```cpp ... ``` block, nothing else.""",
    },
    "c": {
        "name": "C", "fence": "c", "submit": "C",
        "prompt": """You are a competitive programming expert. Write a correct C solution.

## REQUIREMENTS:
- C11. #include <stdio.h>, <stdlib.h>, <string.h>
- scanf/printf for I/O. Use long long for large values
- malloc/free for dynamic memory. Brief comments

## OUTPUT: ONLY ```c ... ``` block, nothing else.""",
    },
    "python": {
        "name": "Python3", "fence": "python", "submit": "Python3",
        "prompt": """You are a competitive programming expert. Write a correct Python 3 solution.

## REQUIREMENTS:
- Python 3.8+. Use sys.stdin.readline() for fast input
- sys.stdout.write() for fast output
- Python int is arbitrary precision, no overflow issues
- Avoid deep recursion, use iterative approach
- Brief inline comments

## OUTPUT: ONLY ```python ... ``` block, nothing else.""",
    },
    "java": {
        "name": "Java", "fence": "java", "submit": "Java",
        "prompt": """You are a competitive programming expert. Write a correct Java solution.

## REQUIREMENTS:
- Java 11+. Public class named Main
- BufferedReader + InputStreamReader for fast input
- BufferedWriter/StringBuilder for fast output. Avoid Scanner
- Use long for values > 2^31. Brief comments

## OUTPUT: ONLY ```java ... ``` block, nothing else.""",
    },
}

RETRY_PROMPT = """Your previous solution was judged:

**Status:** {status}
**Details:** {error}

The problem:

{problem_text}

Fix the issues and provide a CORRECTED solution in **{lang_name}**.

Output ONLY the corrected code in ```{lang} ... ``` markers."""


@dataclass
class AIGeneratedCode:
    code: str = ""
    language: str = "cpp"
    confidence: float = 0.0


class AISolver:
    """Generates solutions via OpenAI-compatible or Anthropic API."""

    def __init__(self, language: str = None):
        self._lang = language or config.language
        if self._lang not in LANG_CFG:
            print(f"[AI] Unknown language '{self._lang}', fallback to cpp")
            self._lang = "cpp"
        self._cfg = LANG_CFG[self._lang]

        self.solutions_dir = os.path.join(config.output_dir, "solutions")
        self.prompts_dir = os.path.join(config.output_dir, "prompts")
        self.responses_dir = os.path.join(config.output_dir, "responses")
        self._provider = None
        self._client = None
        self._valid = True
        self._init_client()

    @property
    def language(self) -> str:
        return self._lang

    @property
    def submit_language(self) -> str:
        return self._cfg["submit"]

    def _ensure_dirs(self):
        os.makedirs(self.solutions_dir, exist_ok=True)
        os.makedirs(self.prompts_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

    def _init_client(self):
        api_key = (os.getenv("API_KEY", "") or
                   os.getenv("DEEPSEEK_API_KEY", "") or
                   os.getenv("ANTHROPIC_AUTH_TOKEN", "") or
                   os.getenv("OPENAI_API_KEY", ""))
        base_url = (os.getenv("API_BASE", "") or
                    os.getenv("DEEPSEEK_BASE_URL", "") or
                    os.getenv("ANTHROPIC_BASE_URL", "") or
                    os.getenv("OPENAI_BASE_URL", ""))
        provider = os.getenv("API_PROVIDER", "").lower()
        model = os.getenv("API_MODEL", "") or config.ai_model

        if not api_key:
            settings_path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
            if os.path.exists(settings_path):
                try:
                    with open(settings_path) as f:
                        cc_env = json.load(f).get('env', {})
                    api_key = cc_env.get('ANTHROPIC_AUTH_TOKEN', '')
                    base_url = base_url or cc_env.get('ANTHROPIC_BASE_URL', '')
                except Exception:
                    pass

        if not api_key:
            print("[AI] 未找到 API 密钥！请在 .env 中设置 API_KEY=sk-xxx")
            self._valid = False
            return

        if not provider:
            provider = "anthropic" if "anthropic" in (base_url or "").lower() else "openai"

        if provider == "openai" and "/anthropic" in (base_url or ""):
            base_url = base_url.replace("/anthropic", "/v1")
        elif provider == "anthropic" and "/v1" in (base_url or "") and "/anthropic" not in (base_url or ""):
            base_url = base_url.replace("/v1", "/anthropic")

        if not base_url:
            base_url = "https://api.deepseek.com/v1" if provider == "openai" else "https://api.deepseek.com/anthropic"
        if not model:
            model = "deepseek-v4-pro"

        try:
            if provider == "anthropic":
                from anthropic import Anthropic
                self._client = Anthropic(api_key=api_key, base_url=base_url)
                self._call_fn = self._call_anthropic
            else:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key, base_url=base_url)
                self._call_fn = self._call_openai
            self._provider = provider
            self._valid = True
            print(f"[AI] {provider} | {base_url} | {model} | {self._cfg['name']}")
        except Exception as e:
            print(f"[AI] Init failed: {e}")
            self._valid = False

    def validate(self) -> bool:
        """Quick API connectivity test. Returns True if API key works.
        If current provider fails, tries the other provider automatically."""
        if not self._client or not self._valid:
            print("[AI] API 未初始化，无法验证")
            return False

        # Try current provider first
        if self._try_validate():
            return True

        # If failed, try the other provider (endpoint may not match key type)
        other = "anthropic" if self._provider == "openai" else "openai"
        print(f"[AI] 当前端点失败，尝试 {other} 端点...")
        old_provider = self._provider
        self._provider = other
        self._call_fn = self._call_anthropic if other == "anthropic" else self._call_openai

        # Rebuild client with corrected base_url
        api_key = (os.getenv("API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "") or
                   os.getenv("ANTHROPIC_AUTH_TOKEN", ""))
        if other == "anthropic":
            from anthropic import Anthropic
            base_url = os.getenv("API_BASE", "").replace("/v1", "/anthropic")
            if "/anthropic" not in base_url:
                base_url = "https://api.deepseek.com/anthropic"
            self._client = Anthropic(api_key=api_key, base_url=base_url)
        else:
            from openai import OpenAI
            base_url = os.getenv("API_BASE", "").replace("/anthropic", "/v1")
            if "/v1" not in base_url:
                base_url = "https://api.deepseek.com/v1"
            self._client = OpenAI(api_key=api_key, base_url=base_url)

        if self._try_validate():
            # Update .env with correct base_url for future runs
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
            if os.path.exists(env_path):
                try:
                    with open(env_path, 'r') as f:
                        content = f.read()
                    content = content.replace(
                        f'API_BASE={os.getenv("API_BASE", "")}',
                        f'API_BASE={base_url}'
                    )
                    with open(env_path, 'w') as f:
                        f.write(content)
                except Exception:
                    pass
            return True

        self._provider = old_provider
        return False

    def _try_validate(self) -> bool:
        """Single validation attempt."""
        try:
            if self._provider == "anthropic":
                self._client.messages.create(
                    model=os.getenv("API_MODEL", "") or config.ai_model,
                    max_tokens=5,
                    messages=[{"role": "user", "content": "hi"}],
                )
            else:
                self._client.chat.completions.create(
                    model=os.getenv("API_MODEL", "") or config.ai_model,
                    max_tokens=5,
                    messages=[{"role": "user", "content": "hi"}],
                )
            print(f"[AI] {self._provider} 端点验证通过")
            return True
        except Exception as e:
            msg = str(e)
            if "402" in msg or "Insufficient" in msg or "insufficient" in msg:
                print(f"[AI] API 余额不足，请充值！")
            elif "401" in msg or "403" in msg:
                print(f"[AI] API Key 无效")
            else:
                print(f"[AI] {self._provider} 端点失败: {msg[:150]}")
            return False

    # ================================================================
    #  Public
    # ================================================================

    def generate_solution(self, problem: ProblemInfo,
                          previous_attempts: list = None) -> Optional[AIGeneratedCode]:
        self._ensure_dirs()
        if previous_attempts is None:
            previous_attempts = []

        is_retry = len(previous_attempts) > 0
        if is_retry:
            last = previous_attempts[-1]
            prompt = RETRY_PROMPT.format(
                status=last.get('status', 'Unknown'),
                error=last.get('error', 'No details'),
                problem_text=problem.to_prompt_text(),
                lang_name=self._cfg["name"],
                lang=self._cfg["fence"],
            )
        else:
            prompt = f"{self._cfg['prompt']}\n\n## Problem:\n\n{problem.to_prompt_text()}"

        suffix = 'retry' if is_retry else 'initial'
        print(f"[AI] {'Retrying' if is_retry else 'Generating'} #{problem.problem_id} ({self._cfg['name']})...")

        prompt_file = os.path.join(self.solutions_dir,
                                   f"problem_{problem.problem_id}_prompt_{suffix}.txt")
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)

        code = self._call_fn(prompt) if self._client else self._call_file_based(prompt, problem.problem_id)
        if not code:
            print("[AI] FAILED")
            return None

        code = self._clean_code(code)
        attempt_num = len(previous_attempts) + 1
        code_file = os.path.join(self.solutions_dir,
                                 f"problem_{problem.problem_id}_attempt_{attempt_num}.{self._cfg['fence']}")
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"[AI] Saved ({len(code)} chars)")

        return AIGeneratedCode(code=code, language=self._lang)

    # ================================================================
    #  OpenAI backend
    # ================================================================

    def _call_openai(self, prompt: str, retry: int = 0) -> Optional[str]:
        try:
            max_tokens = 4096 + retry * 2048
            resp = self._client.chat.completions.create(
                model=os.getenv("API_MODEL", "") or config.ai_model,
                messages=[
                    {"role": "system", "content": f"Output ONLY {self._cfg['name']} code in ```{self._cfg['fence']} fences."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens, temperature=0.2,
            )
            output = resp.choices[0].message.content or ""
            code = self._extract_code(output)
            if code:
                return code
            if retry < 2:
                return self._call_openai(prompt, retry + 1)
            return None
        except Exception as e:
            print(f"[AI] OpenAI error: {e}")
            return None

    # ================================================================
    #  Anthropic backend
    # ================================================================

    def _call_anthropic(self, prompt: str, retry: int = 0) -> Optional[str]:
        try:
            max_tokens = 4096 + retry * 2048
            resp = self._client.messages.create(
                model=os.getenv("API_MODEL", "") or config.ai_model,
                max_tokens=max_tokens, temperature=0.2,
                system=f"Output ONLY {self._cfg['name']} code in ```{self._cfg['fence']} fences.",
                messages=[{"role": "user", "content": prompt}],
            )
            text_blocks = [b for b in resp.content if b.type == 'text']
            if not text_blocks:
                if retry < 2:
                    return self._call_anthropic(prompt, retry + 1)
                return None
            code = self._extract_code(text_blocks[0].text)
            if code:
                return code
            if retry < 2:
                return self._call_anthropic(prompt, retry + 1)
            return None
        except Exception as e:
            print(f"[AI] Anthropic error: {e}")
            return None

    # ================================================================
    #  Utilities
    # ================================================================

    def _call_file_based(self, prompt: str, problem_id: str) -> Optional[str]:
        prompt_path = os.path.join(self.prompts_dir, f"{problem_id}.txt")
        response_path = os.path.join(self.responses_dir, f"{problem_id}.{self._cfg['fence']}")
        status_path = os.path.join(self.responses_dir, f"{problem_id}.status")
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        with open(status_path, 'w') as f:
            f.write('pending')
        for _ in range(200):
            if os.path.exists(status_path):
                with open(status_path) as f:
                    if f.read().strip() == 'done' and os.path.exists(response_path):
                        with open(response_path, encoding='utf-8') as f:
                            return f.read()
            time.sleep(3)
        return None

    def _extract_code(self, output: str) -> Optional[str]:
        fence = self._cfg["fence"]
        # Try language-specific fence
        m = re.search(rf'```(?:{fence})\s*\n(.*?)\n\s*```', output, re.DOTALL)
        if m:
            return m.group(1).strip()
        # Try generic fence
        m = re.search(r'```\s*\n(.*?)\n\s*```', output, re.DOTALL)
        if m:
            code = m.group(1).strip()
            # Quick check: does it look like code?
            if any(kw in code for kw in ['#include', 'int main', 'def ', 'import', 'public class', 'printf', 'scanf']):
                return code
        return None

    def _clean_code(self, code: str) -> str:
        lines = code.split('\n')
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines).strip()

    def analyze_error(self, problem: ProblemInfo, error_info: dict) -> str:
        status = error_info.get('status', 'Unknown')
        msg = error_info.get('error', '')
        if 'Wrong Answer' in status:
            return "WRONG ANSWER: Check algorithm, edge cases, overflow, I/O format."
        elif 'Time Limit' in status:
            return "TLE: Optimize complexity; use fast I/O."
        elif 'Runtime Error' in status:
            return "RUNTIME ERROR: Check array bounds, null pointers, division by zero."
        elif 'Compile Error' in status:
            return f"COMPILE ERROR: {msg}"
        elif 'Memory Limit' in status:
            return "MLE: Reduce memory usage."
        return f"{status}: {msg}"
