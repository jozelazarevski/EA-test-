"""Configuration for the HVAC Testing Agent."""

import os
from pathlib import Path

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
