import contextlib
import json
import threading
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

# Module-level lock: all reads and writes must hold this to prevent
# race conditions from FastAPI's threadpool executing sync handlers
# concurrently (even with a single uvicorn worker).
# We use a reentrant lock (RLock) to allow recursive acquisition
# within the edit_config context manager.
_lock = threading.RLock()


def load_config() -> dict:
    """Load config from JSON file."""
    with _lock:
        if not CONFIG_PATH.exists():
            return {"check_sections": [], "journals": []}
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)


def save_config(config: dict) -> None:
    """Save config to JSON file.

    Serializes to memory first, then writes directly to the file.
    This avoids replacing the file path, which fails with EBUSY (Device or resource busy)
    in Docker environments when the config file is bind-mounted directly.
    """
    with _lock:
        content = json.dumps(config, indent=4, ensure_ascii=False)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(content)


@contextlib.contextmanager
def edit_config():
    """Context manager to safely load, modify, and automatically save config under a lock."""
    with _lock:
        config = load_config()
        yield config
        save_config(config)


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
    with edit_config() as config:
        if not config.get("check_sections"):
            config["check_sections"] = DEFAULT_CHECK_SECTIONS
        if not config.get("journals"):
            config["journals"] = []
    return config
