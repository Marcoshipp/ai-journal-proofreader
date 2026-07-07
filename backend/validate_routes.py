import os
import uuid
import json
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from google import genai

from checks.extractions import (
    pdf_to_markdown,
    generate_metadata_json,
    populate_subheadings_to_metadata,
)
from checks.general import (
    ValidationResult,
    check_article_title,
    check_titles,
    contains_aq,
    check_abstract,
    check_authors,
    check_irb_and_pc,
    check_coi,
    check_section_order,
    check_acknowledgments,
    check_author_contributions,
    check_data_availability,
    check_financial_support,
    check_keywords,
    check_date_format,
    check_online_access,
    check_htcta,
)
from config_manager import load_config

router = APIRouter(prefix="/api")

# In-memory store for job results (job_id -> result dict)
_jobs: Dict[str, Dict[str, Any]] = {}

# Map check_section keys to their built-in functions
# Each entry: key -> (function, arg_type)
#   arg_type: "metadata" | "md" | "metadata+md"
BUILTIN_CHECKS = {
    "title": (check_article_title, "metadata"),
    "abstract": (check_abstract, "metadata"),
    "subheadings": (check_titles, "metadata"),
    "authors": (check_authors, "metadata"),
    "coi": (check_coi, "metadata+md"),
    "aq": (contains_aq, "md"),
    "irb": (check_irb_and_pc, "md"),
    "section_order": (check_section_order, "md"),
    "acknowledgments": (check_acknowledgments, "metadata+md"),
    "author_contributions": (check_author_contributions, "md"),
    "data_availability": (check_data_availability, "md"),
    "financial_support": (check_financial_support, "md"),
    "keywords": (check_keywords, "metadata"),
    "date_format": (check_date_format, "metadata"),
    "online_access": (check_online_access, "metadata"),
    "htcta": (check_htcta, "metadata"),
}


def get_effective_rules(config: Dict[str, Any], article_type: Dict[str, Any]) -> Dict[str, Any]:
    """Merge rule sources (lowest → highest priority):
      1. auto-defaults: every key in BUILTIN_CHECKS enabled=True, type='general'
      2. config['default_rules']: global overrides declared in config.json
      3. article_type['rules']: per-article-type exceptions
    """
    auto_defaults = {key: {"type": "general", "enabled": True} for key in BUILTIN_CHECKS}
    config_defaults = config.get("default_rules", {})
    overrides = article_type.get("rules", {}) if article_type else {}

    merged: Dict[str, Any] = {}
    for key in set(auto_defaults) | set(config_defaults) | set(overrides):
        merged[key] = {
            **auto_defaults.get(key, {}),
            **config_defaults.get(key, {}),
            **overrides.get(key, {}),
        }
    return merged


def _run_builtin_check(
    key: str, metadata: Dict[str, Any], md_path: str, params: Dict[str, Any] = None
) -> ValidationResult:
    """Run a built-in check by its section key, forwarding params to parameterised functions."""
    params = params or {}
    if key not in BUILTIN_CHECKS:
        return ValidationResult(
            check_name=key,
            status="WARNING",
            messages=[f"No built-in check for '{key}'."],
        )
    func, arg_type = BUILTIN_CHECKS[key]
    if arg_type == "metadata":
        # Pass params only if the function accepts it
        try:
            return func(metadata, params=params)
        except TypeError:
            return func(metadata)
    elif arg_type == "md":
        try:
            return func(md_path, params=params)
        except TypeError:
            return func(md_path)
    elif arg_type == "metadata+md":
        try:
            return func(metadata, md_path, params=params)
        except TypeError:
            return func(metadata, md_path)


def run_llm_check(
    display_name: str,
    instruction: str,
    context_fields: List[str],
    metadata: Dict[str, Any],
    md_path: str,
    effective_rules: Dict[str, Any],
    api_key: str = None,
) -> ValidationResult:
    """Run a custom LLM check using a supervisor-defined instruction.

    context_fields can reference metadata keys (e.g. 'abstract') or
    document sections (e.g. 'section:Discussion'). Section names are
    resolved using expected_headings from the subheadings rule params,
    so they respect per-article-type heading overrides.
    """
    from checks.general import get_text_from_heading

    # Build the expected_headings lookup from effective rules
    subheadings_params = effective_rules.get("subheadings", {}).get("params", {})
    expected_headings: List[str] = subheadings_params.get("expected_headings", [
        "Introduction", "Materials and Methods", "Results", "Discussion", "Conclusions"
    ])
    # Build a lowercase→original map for case-insensitive lookup
    heading_map = {h.lower(): h for h in expected_headings}

    # Assemble context dict
    context: Dict[str, Any] = {}
    for field in context_fields:
        if field.startswith("section:"):
            section_name = field[len("section:"):]
            resolved = heading_map.get(section_name.lower(), section_name)
            text = get_text_from_heading(md_path, f"## **{resolved}**")
            context[field] = text or f"[Section '{resolved}' not found in document]"
        else:
            context[field] = metadata.get(field)

    prompt = f"""You are a journal proofreading assistant. Apply the following check rule to the provided paper metadata and return your judgment.

Check Rule:
{instruction}

Paper Context:
{json.dumps(context, indent=2, ensure_ascii=False)}

Respond ONLY in this exact format (2 lines):
STATUS: PASS
REASON: one-sentence explanation

Or:
STATUS: FAIL
REASON: one-sentence explanation
"""

    try:
        if api_key:
            client = genai.Client(api_key=api_key)
        else:
            client = genai.Client()
        interaction = client.interactions.create(
            model="gemini-3.1-flash-lite",
            input=prompt,
        )
        text = interaction.output_text.strip()
        lines = {}
        for line in text.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                lines[k.strip().upper()] = v.strip()

        raw_status = lines.get("STATUS", "FAIL").upper()
        reason = lines.get("REASON", text)
        status = "SUCCESS" if raw_status == "PASS" else "FAILURE"
        return ValidationResult(
            check_name=display_name,
            status=status,
            messages=[f"[{'OK' if status == 'SUCCESS' else 'FAILURE'}] {reason}"],
        )
    except Exception as e:
        return ValidationResult(
            check_name=display_name,
            status="WARNING",
            messages=[f"[WARNING] Custom LLM check failed to run: {e}"],
        )


def _generate_report_markdown(
    results: List[ValidationResult],
    paper_title: Optional[str] = None,
    journal_name: Optional[str] = None,
    article_type_name: Optional[str] = None,
) -> str:
    """Generate a markdown report from validation results."""
    lines = ["# Validation Report\n"]
    
    if paper_title or journal_name or article_type_name:
        lines.append("## General Information")
        if paper_title:
            lines.append(f"- **Paper Title**: {paper_title}")
        if journal_name:
            lines.append(f"- **Journal**: {journal_name}")
        if article_type_name:
            lines.append(f"- **Article Type**: {article_type_name}")
        lines.append("")

    for res in results:
        lines.append(f"## {res.check_name}")
        if res.status == "SUCCESS":
            emoji = "✅"
        elif res.status == "WARNING":
            emoji = "⚠️"
        elif res.status == "INFO":
            emoji = "ℹ️"
        else:
            emoji = "❌"
        lines.append(f"**Status**: {emoji} {res.status}\n")
        for msg in res.messages:
            lines.append(f"- {msg}")
        lines.append("")
    return "\n".join(lines)


async def _process_pdf(job_id: str):
    """Run the full validation pipeline, updating job progress as we go."""
    job = _jobs[job_id]

    try:
        config = load_config()
        api_key = config.get("global_settings", {}).get("api_key")

        work_dir = job["work_dir"]
        pdf_path = job["pdf_path"]
        md_path = os.path.join(work_dir, "article.md")
        json_path = os.path.join(work_dir, "metadata.json")

        # Step 1: Extract metadata from PDF via Gemini
        job["steps"].append({"key": "extracting_metadata", "status": "running", "label": "Extracting metadata from PDF..."})
        metadata = await asyncio.to_thread(generate_metadata_json, pdf_path, json_path, api_key)
        job["steps"][-1]["status"] = "done"

        # Step 2: Convert PDF to markdown
        job["steps"].append({"key": "converting_markdown", "status": "running", "label": "Converting PDF to markdown..."})
        await asyncio.to_thread(pdf_to_markdown, pdf_path, md_path, api_key)
        job["steps"][-1]["status"] = "done"

        # Step 3: Populate subheadings
        job["steps"].append({"key": "populating_subheadings", "status": "running", "label": "Extracting subheadings..."})
        await asyncio.to_thread(populate_subheadings_to_metadata, json_path, md_path)
        # Reload metadata after subheadings are added
        with open(json_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        job["steps"][-1]["status"] = "done"
        
        # Get paper title from metadata
        paper_title = metadata.get("titleName", "Unknown Title")
        job["paper_title"] = paper_title

        # Step 4: Determine which checks to run
        # Find journal and article type rules
        journal_id = job.get("journal_id")
        article_type_id = job.get("article_type_id")
        
        journal = next((j for j in config.get("journals", []) if j["id"] == journal_id), None)
        article_type = None
        
        if journal and "article_types" in journal and journal["article_types"]:
            if article_type_id:
                article_type = next((t for t in journal["article_types"] if t["id"] == article_type_id), None)
            
            # Fallback to the first article type if not specified or not found
            if not article_type:
                article_type = journal["article_types"][0]

        journal_name = journal["name"] if journal else "Unknown Journal"
        article_type_name = article_type["name"] if article_type else "Unknown Article Type"
        
        job["journal_name"] = journal_name
        job["article_type_name"] = article_type_name

        check_sections = config.get("check_sections", [])
        
        # Compute effective rules once (auto-defaults + config defaults + article overrides)
        effective_rules = get_effective_rules(config, article_type)

        # Pre-populate all steps in job["steps"] so the frontend gets them immediately
        step_indices = {}
        for section in check_sections:
            key = section["key"]
            display = section["display_name"]
            
            rule = effective_rules.get(key, {})
            is_enabled = rule.get("enabled", True)
            
            step = {
                "key": f"check_{key}",
                "status": "running" if is_enabled else "skipped",
                "label": f"Checking {display}...",
            }
            if not is_enabled:
                skipped_result = ValidationResult(
                    check_name=display,
                    status="INFO",
                    messages=["[SKIPPED] This check is disabled in settings."],
                )
                step["result"] = skipped_result.to_dict()
                
            job["steps"].append(step)
            step_indices[key] = len(job["steps"]) - 1

        # Define individual task worker for parallel execution
        async def execute_check(section):
            key = section["key"]
            display = section["display_name"]

            rule = effective_rules.get(key, {})
            rule_type = rule.get("type", "general")
            is_enabled = rule.get("enabled", True)
            params = rule.get("params", {}).copy()

            if not is_enabled:
                skipped_result = ValidationResult(
                    check_name=display,
                    status="INFO",
                    messages=["[SKIPPED] This check is disabled in settings."],
                )
                return key, skipped_result

            if api_key:
                params["_api_key"] = api_key

            try:
                if rule_type == "general":
                    result = await asyncio.to_thread(
                        _run_builtin_check, key, metadata, md_path, params
                    )
                elif rule_type == "custom":
                    instruction = rule.get("instruction", "")
                    context_fields = params.get("context_fields", list(metadata.keys())[:5])
                    result = await asyncio.to_thread(
                        run_llm_check,
                        display, instruction, context_fields, metadata, md_path, effective_rules, api_key
                    )
                else:
                    result = ValidationResult(
                        check_name=display,
                        status="INFO",
                        messages=[f"[INFO] Unknown rule type '{rule_type}' — skipped."],
                    )
                return key, result
            except Exception as e:
                result = ValidationResult(
                    check_name=display,
                    status="WARNING",
                    messages=[f"[WARNING] Check failed to run: {e}"],
                )
                return key, result

        # Gather tasks and run them concurrently
        tasks = [execute_check(section) for section in check_sections]
        completed_tasks = await asyncio.gather(*tasks)

        # Collect results and update step statuses in the correct order
        results = []
        for key, result in completed_tasks:
            results.append(result)
            idx = step_indices[key]
            if job["steps"][idx]["status"] == "running":
                job["steps"][idx]["status"] = "done"
                job["steps"][idx]["result"] = result.to_dict()

        # Generate markdown report
        report_md = _generate_report_markdown(
            results,
            paper_title=job.get("paper_title"),
            journal_name=job.get("journal_name"),
            article_type_name=job.get("article_type_name"),
        )
        job["report_markdown"] = report_md
        job["metadata"] = metadata
        job["results"] = [r.to_dict() for r in results]
        job["status"] = "complete"

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        import traceback
        job["traceback"] = traceback.format_exc()
    finally:
        # Clean up the temporary working directory
        if os.path.exists(job["work_dir"]):
            shutil.rmtree(job["work_dir"])


# We need to define UPLOADS_DIR if it doesn't exist to prevent NameError
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

@router.post("/validate")
async def validate_pdf(
    file: UploadFile = File(...),
    journal_id: str = Form(...),
    article_type_id: Optional[str] = Form(None)
):
    """Upload a PDF and start validation. Returns a job_id for progress tracking."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    job_id = str(uuid.uuid4())
    
    # Create a temp working directory for this job
    work_dir = tempfile.mkdtemp(prefix=f"pdf_validate_{job_id}_")
    
    # Save uploaded file to UPLOADS_DIR
    pdf_path = UPLOADS_DIR / f"{job_id}.pdf"
    content = await file.read()
    with open(pdf_path, "wb") as f:
        f.write(content)

    _jobs[job_id] = {
        "status": "processing",
        "steps": [],
        "report_markdown": None,
        "metadata": None,
        "results": None,
        "error": None,
        "pdf_path": str(pdf_path), # Store path to uploaded PDF
        "work_dir": work_dir,      # Store path to job's working directory
        "journal_id": journal_id,
        "article_type_id": article_type_id,
    }

    # Run processing in background
    asyncio.create_task(_process_pdf(job_id))

    return {"job_id": job_id}


@router.get("/validate/{job_id}/progress")
async def validate_progress(job_id: str):
    """SSE endpoint — streams job progress until complete."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    async def event_stream():
        while True:
            job = _jobs.get(job_id)
            if not job:
                break

            # Send current state
            payload = {
                "status": job["status"],
                "steps": job["steps"],
            }

            if job["status"] == "complete":
                payload["report_markdown"] = job["report_markdown"]
                payload["metadata"] = job["metadata"]
                payload["results"] = job["results"]
                payload["paper_title"] = job.get("paper_title")
                payload["journal_name"] = job.get("journal_name")
                payload["article_type_name"] = job.get("article_type_name")
                yield f"data: {json.dumps(payload)}\n\n"
                break
            elif job["status"] == "error":
                payload["error"] = job["error"]
                yield f"data: {json.dumps(payload)}\n\n"
                break
            else:
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/validate/{job_id}/result")
async def validate_result(job_id: str):
    """Get the final result for a completed job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = _jobs[job_id]
    if job["status"] != "complete":
        raise HTTPException(status_code=202, detail="Job still processing.")

    return {
        "status": "complete",
        "report_markdown": job["report_markdown"],
        "metadata": job["metadata"],
        "results": job["results"],
        "paper_title": job.get("paper_title"),
        "journal_name": job.get("journal_name"),
        "article_type_name": job.get("article_type_name"),
    }
