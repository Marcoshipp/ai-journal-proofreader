import json
import uuid
from pathlib import Path

# Path to the config
CONFIG_PATH = Path(__file__).parent / "config.json"

def migrate():
    if not CONFIG_PATH.exists():
        print("No config.json found or already new structure.")
        return
        
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    journals = data.get("journals", [])
    
    # Check if we need migration (if rules exists directly on journal)
    needs_migration = any("rules" in j for j in journals)
    if not needs_migration:
        print("No migration needed.")
        return
        
    new_journals = []
    for j in journals:
        rules = j.get("rules", {})
        
        # Create an 'Original Article' type mapping existing rules
        new_j = {
            "id": j.get("id"),
            "name": j.get("name"),
            "article_types": [
                {
                    "id": "original-article",
                    "name": "Original Article",
                    "rules": rules
                }
            ]
        }
        new_journals.append(new_j)
        
    data["journals"] = new_journals
    
    # Backup original just in case
    backup_path = CONFIG_PATH.with_suffix('.json.bak')
    import shutil
    shutil.copy2(CONFIG_PATH, backup_path)
    print(f"Backed up config to {backup_path}")
    
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print("Migration successful.")

if __name__ == "__main__":
    migrate()
