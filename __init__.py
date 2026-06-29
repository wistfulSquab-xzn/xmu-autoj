"""
XMUOJ Auto Answer - Automated OJ problem solver for xmuoj.com

Usage:
    python run.py --contest 361 --range 1-10
    python run.py --contest 362 --limit 5
    python run.py --dry-run

Main components:
    - Orchestrator: Main controller coordinating all modules
    - ProblemFetcher: Fetches problems via XMUOJ API
    - AISolver: Generates C++ solutions via DeepSeek V4 Pro
    - SubmitEngine: Submits code and monitors results
    - XMUOJAuth: Handles login and session management
"""
__version__ = "2.0.0"
