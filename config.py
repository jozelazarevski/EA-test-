"""Configuration for the HVAC Testing Agent."""

import os
from pathlib import Path

# Load .env file if present
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                os.environ.setdefault(_key.strip(), _val.strip())

# Target application
TARGET_URL = "https://expertadvisor.jci.com/"

# Directories
BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
DOWNLOADS_DIR = BASE_DIR / "downloads"

# Ensure directories exist
REPORTS_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Browser settings
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
SLOW_MO = int(os.getenv("SLOW_MO", "500"))  # ms between actions
DEFAULT_TIMEOUT = int(os.getenv("TIMEOUT", "60000"))  # 60s default

# Agent settings
MAX_WAIT_FOR_RESPONSE = 120  # seconds to wait for EA response
SCREENSHOT_ON_EACH_STEP = True

# LLM settings
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

# Session persistence settings
SESSION_PERSIST = os.getenv("SESSION_PERSIST", "true").lower() == "true"
SESSION_DIR = Path(os.getenv("SESSION_DIR", str(BASE_DIR / ".session")))
SESSION_MAX_AGE_HOURS = float(os.getenv("SESSION_MAX_AGE_HOURS", "12"))
