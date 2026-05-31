import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# LLM 配置（从环境变量读取，支持任意 OpenAI 兼容 API）
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.deepseek.com/v1"
LLM_MODEL = os.getenv("LLM_MODEL") or "deepseek-chat"
LLM_QUICK_MODEL = os.getenv("LLM_QUICK_MODEL") or os.getenv("LLM_MODEL") or "deepseek-chat"

# 可选：从配置文件覆盖
_config_path = Path(__file__).resolve().parent / "llm_config.json"
if _config_path.exists():
    try:
        with open(_config_path) as _f:
            _cfg = json.load(_f)
        LLM_API_KEY = _cfg.get("api_key") or LLM_API_KEY
        LLM_BASE_URL = _cfg.get("base_url") or LLM_BASE_URL
        LLM_MODEL = _cfg.get("model") or LLM_MODEL
        LLM_QUICK_MODEL = _cfg.get("quick_model") or _cfg.get("model") or LLM_QUICK_MODEL
    except Exception:
        pass

# 保持向后兼容
DEEPSEEK_API_KEY = LLM_API_KEY
DEEPSEEK_BASE_URL = LLM_BASE_URL
DEEP_MODEL = LLM_MODEL
QUICK_MODEL = LLM_QUICK_MODEL

MAX_DEBATE_ROUNDS = int(os.getenv("MAX_DEBATE_ROUNDS", "1"))
MAX_ANALYST_TOOL_LOOPS = int(os.getenv("MAX_ANALYST_TOOL_LOOPS", "3"))

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
