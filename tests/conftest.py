from __future__ import annotations

import os
import sys
from pathlib import Path

# 测试必须可复现，不能被开发者本机的 .env（例如 APP_MODE=local）改变路线。
os.environ["APP_MODE"] = "demo"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
