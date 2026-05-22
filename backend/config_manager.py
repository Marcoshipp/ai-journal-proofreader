import json
import threading
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

# Module-level lock: all reads and writes must hold this to prevent
# race conditions from FastAPI's threadpool executing sync handlers
# concurrently (even with a single uvicorn worker).
_lock = threading.Lock()


def load_config() -> dict:
    """Load config from JSON file."""
    with _lock:
        if not CONFIG_PATH.exists():
            return {"check_sections": [], "journals": []}
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)


def save_config(config: dict) -> None:
    """Save config to JSON file.

    Uses a write-to-temp-then-atomic-rename pattern so that:
    - Readers never see a truncated or partially-written file.
    - A crash mid-write leaves the original file intact.
    """
    with _lock:
        tmp = CONFIG_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        tmp.replace(CONFIG_PATH)  # atomic on Linux (POSIX rename syscall)


# ── Check section registry ───────────────────────────────────────
# Programmer-extensible: add new check section keys here and they
# appear in the config matrix automatically.
DEFAULT_CHECK_SECTIONS = [
    {"key": "aq", "display_name": "AQ", "general_description": "是否有未處理的AQ"},
    {"key": "title", "display_name": "篇名格式", "general_description": "1. Title Case\n2. 括號及介係詞小寫\n3. dash後第一個字母為大寫\n4. 冒號後第一個字母為大寫"},
    {"key": "authors", "display_name": "作者名格式", "general_description": "1. 須有全名\n2. 首字母大寫\n3. 先名再姓（First Name + Last Name）\n4. 通訊作者查核"},
    {"key": "abstract", "display_name": "摘要格式-大標", "general_description": "Background, Objectives, Materials and Methods, Results, Conclusions"},
    {"key": "subheadings", "display_name": "內文大標", "general_description": "INTRODUCTION, MATERIALS AND METHODS, RESULTS, DISCUSSION, CONCLUSIONS"},
    {"key": "coi", "display_name": "Conflict(s) of Interest", "general_description": "1. 順序正確\n2. 檢查文章每位作者是否為FJMD編委會成員\n3. 若是編委，則COI須聲明並提及該作者"},
    {"key": "irb", "display_name": "IRB & Patient Consent", "general_description": "使用LLM檢查「Materials and Methods」中IRB核准及病人同意相關資訊"},
]


def ensure_config() -> dict:
    """Return existing config, or create a default one if missing."""
    config = load_config()
    if not config.get("check_sections"):
        config["check_sections"] = DEFAULT_CHECK_SECTIONS
    if not config.get("journals"):
        config["journals"] = []
    save_config(config)
    return config
