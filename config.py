import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

DEEP_MODEL = "deepseek-chat"
QUICK_MODEL = "deepseek-chat"

MAX_DEBATE_ROUNDS = 2
MAX_ANALYST_TOOL_LOOPS = 3

DATA_CACHE_DIR = os.path.expanduser("~/.trading-agent/cache")
MEMORY_LOG_PATH = os.path.expanduser("~/.trading-agent/memory/trading_memory.md")
MEMORY_DIR = os.path.expanduser("~/.trading-agent/memory")


def detect_market(code: str) -> str:
    if code.startswith(("60", "68")):
        return "sh"
    return "sz"


def full_ticker(code: str) -> str:
    return f"{detect_market(code)}{code}"


def gtimg_code(code: str) -> str:
    market = detect_market(code)
    return f"{market}{code}"
