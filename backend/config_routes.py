import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from config_manager import load_config, save_config

router = APIRouter(prefix="/api/config")


class JournalCreate(BaseModel):
    name: str


class ArticleTypeCreate(BaseModel):
    name: str


class RuleUpdate(BaseModel):
    type: Optional[str] = "general"  # Default to general for uninitialized rules
    instruction: Optional[str] = None
    enabled: Optional[bool] = None  # None means "not set" → treated as True
    params: Optional[dict] = None  # optional parameters for parameterised checks


class CheckSectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    instruction: str
    context_fields: list[str] = []
    target_journal_id: str
    target_article_type_id: str


class GlobalSettingsUpdate(BaseModel):
    api_key: Optional[str] = None


# ── Global Settings ───────────────────────────────────────────────

@router.get("/settings")
def get_global_settings():
    config = load_config()
    return config.get("global_settings", {"api_key": ""})


@router.put("/settings")
def update_global_settings(body: GlobalSettingsUpdate):
    config = load_config()
    if "global_settings" not in config:
        config["global_settings"] = {}
    config["global_settings"]["api_key"] = body.api_key
    save_config(config)
    return {"ok": True, "message": "Settings updated"}


# ── Journals ──────────────────────────────────────────────────────

@router.get("/journals")
def list_journals():
    """List all journal profiles."""
    config = load_config()
    return config.get("journals", [])


@router.post("/journals")
def create_journal(body: JournalCreate):
    """Create a new journal profile with a default 'Original Article' type."""
    config = load_config()
    journal_id = str(uuid.uuid4())[:8]

    # Start with an empty rules dict — get_effective_rules() provides auto-defaults at runtime
    journal = {
        "id": journal_id,
        "name": body.name,
        "article_types": [
            {
                "id": "original-article",
                "name": "Original Article",
                "rules": {}
            }
        ]
    }
    config["journals"].append(journal)
    save_config(config)
    return journal


@router.delete("/journals/{journal_id}")
def delete_journal(journal_id: str):
    """Delete a journal profile."""
    config = load_config()
    journals = config.get("journals", [])
    config["journals"] = [j for j in journals if j["id"] != journal_id]
    save_config(config)
    return {"ok": True}


# ── Article Types ────────────────────────────────────────────────

@router.post("/journals/{journal_id}/article-types")
def create_article_type(journal_id: str, body: ArticleTypeCreate):
    """Create a new article type for a journal."""
    config = load_config()
    journal = next((j for j in config.get("journals", []) if j["id"] == journal_id), None)
    if not journal:
        raise HTTPException(status_code=404, detail="Journal not found.")

    type_id = str(uuid.uuid4())[:8]
    
    new_type = {
        "id": type_id,
        "name": body.name,
        "rules": {}  # empty — get_effective_rules() provides auto-defaults at runtime
    }
    journal["article_types"].append(new_type)
    save_config(config)
    return new_type


@router.delete("/journals/{journal_id}/article-types/{type_id}")
def delete_article_type(journal_id: str, type_id: str):
    config = load_config()
    journal = next((j for j in config.get("journals", []) if j["id"] == journal_id), None)
    if not journal:
        raise HTTPException(status_code=404, detail="Journal not found.")

    if "article_types" in journal:
        journal["article_types"] = [t for t in journal["article_types"] if t["id"] != type_id]
        save_config(config)
        
    return {"ok": True}


# ── Check Sections ────────────────────────────────────────────────

@router.get("/check-sections")
def list_check_sections():
    """List all check sections (programmer-defined rows)."""
    config = load_config()
    return config.get("check_sections", [])


@router.post("/check-sections")
def create_check_section(body: CheckSectionCreate):
    """Create a new check section and initialize its custom rule for the target article type."""
    config = load_config()
    
    # 1. Add to check_sections list
    section_key = f"custom_{str(uuid.uuid4())[:8]}"
    new_section = {
        "key": section_key,
        "display_name": body.name,
        "general_description": body.description
    }
    config.setdefault("check_sections", []).append(new_section)
    
    # 2. Add rule to the specific article type
    journal = next((j for j in config.get("journals", []) if j["id"] == body.target_journal_id), None)
    if not journal:
        raise HTTPException(status_code=404, detail="Journal not found.")
        
    article_type = next((t for t in journal.get("article_types", []) if t["id"] == body.target_article_type_id), None)
    if not article_type:
        raise HTTPException(status_code=404, detail="Article Type not found.")
        
    if "rules" not in article_type:
        article_type["rules"] = {}
        
    article_type["rules"][section_key] = {
        "type": "custom",
        "instruction": body.instruction,
        "params": {"context_fields": body.context_fields},
        "enabled": True
    }
    
    save_config(config)
    return {"section": new_section, "rule": article_type["rules"][section_key]}


# ── Rules (cells) ────────────────────────────────────────────────

@router.put("/journals/{journal_id}/article-types/{type_id}/rules/{section_key}")
def update_rule(journal_id: str, type_id: str, section_key: str, body: RuleUpdate):
    """Update a rule for a specific article type + check section."""
    
    config = load_config()
    journal = next((j for j in config.get("journals", []) if j["id"] == journal_id), None)
    if not journal:
        raise HTTPException(status_code=404, detail="Journal not found.")
        
    article_type = next((t for t in journal.get("article_types", []) if t["id"] == type_id), None)
    if not article_type:
        raise HTTPException(status_code=404, detail="Article Type not found.")

    if "rules" not in article_type:
        article_type["rules"] = {}

    rule = {"type": body.type}
    if body.type == "custom" and body.instruction:
        rule["instruction"] = body.instruction
    if body.enabled is not None:
        rule["enabled"] = body.enabled
    if body.params is not None:
        rule["params"] = body.params

    article_type["rules"][section_key] = rule
    save_config(config)
    return rule


# ── Full config (for matrix view) ────────────────────────────────

@router.get("")
def get_full_config():
    """Return the full config (check_sections + journals with rules)."""
    config = load_config()
    return config
