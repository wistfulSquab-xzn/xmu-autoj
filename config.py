"""
XMUOJ Auto Answer - Configuration
Reads from: env vars > .env file > defaults
"""
import os
from dataclasses import dataclass, field


def _load_dotenv():
    """Load .env file if it exists (simple loader, no dependency needed)."""
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_file):
        return
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, val = line.partition('=')
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and val and key not in os.environ:
                    os.environ[key] = val


_load_dotenv()


@dataclass
class XMUOJConfig:
    """XMUOJ platform configuration."""
    base_url: str = "https://xmuoj.com"
    api_base: str = "https://xmuoj.com/api"

    # Credentials (env vars > .env file > set directly)
    username: str = field(default_factory=lambda: os.getenv("XMUOJ_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("XMUOJ_PASSWORD", ""))
    contest_password: str = field(default_factory=lambda: os.getenv("XMUOJ_CONTEST_PASSWORD", ""))

    # Target
    contest_id: int = 362

    # Browser
    headless: bool = True
    browser_timeout: int = 60000

    # Rate limiting
    request_interval: float = 3.0
    submit_cooldown: float = 5.0

    # AI solver
    max_retry_per_problem: int = 5
    ai_model: str = "deepseek-v4-pro"

    # Output
    output_dir: str = "output"
    cookies_file: str = "cookies.json"

    def validate(self) -> bool:
        if not self.username or not self.password:
            raise ValueError(
                "请设置 XMUOJ 凭据。方式：\n"
                "  1. 创建 .env 文件（推荐）:\n"
                "     复制 .env.example 为 .env 并填入凭据\n"
                "  2. 设置环境变量:\n"
                "     $env:XMUOJ_USERNAME = '学号'\n"
                "     $env:XMUOJ_PASSWORD = '密码'\n"
                "     $env:XMUOJ_CONTEST_PASSWORD = '比赛密码'"
            )
        return True


config = XMUOJConfig()
