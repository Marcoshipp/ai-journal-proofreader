from pathlib import Path
import pymupdf4llm
import re
import json
import base64
from typing import List, Dict, Any
from dotenv import load_dotenv
from google import genai
from prompts.prompt import JSON_PROMPT_TEMPLATE

load_dotenv()


def clean_markdown_lines(lines: List[str]) -> List[str]:
    cleaned_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # 1. Remove Page Numbers (matches original "numeric" check)
        if line.strip().isnumeric():
            cleaned_lines.append("")
            i += 1
            continue

        # 2. Fix prefix artifacts (original regex logic)
        curr_line = line
        if re.search(r"^\d+AQ", curr_line):
            curr_line = re.sub(r"^\d+(AQ.*)", r"\1", curr_line)
        elif re.match(r"^\d+\s+[A-Za-z0-9]", curr_line):
            curr_line = re.sub(r"^\d+\s+([A-Za-z0-9].*)", r"\1", curr_line)

        # 3. AQ Logic
        # Check if line starts with AQ<digits>
        aq_match = re.match(r"^(AQ\d+)(.*)", curr_line.strip())
        if aq_match:
            rest_of_line = aq_match.group(2).strip()

            # Case A: Definition (AQ1: ...) -> Keep it
            if rest_of_line.startswith(":"):
                cleaned_lines.append(curr_line)
                i += 1
                continue

            # Case B: Ghost Check
            candidate_text = re.sub(r"^AQ\d+\s*", "", curr_line).strip()

            if not candidate_text:
                cleaned_lines.append("")
                i += 1
                continue

            is_duplicate = False
            for j in range(1, 21):
                if i + j >= len(lines):
                    break
                future_line = lines[i + j].strip()
                if candidate_text and candidate_text in future_line:
                    is_duplicate = True
                    break

            if is_duplicate:
                cleaned_lines.append("")
            else:
                cleaned_lines.append(candidate_text)

        else:
            cleaned_lines.append(curr_line)

        i += 1

    return cleaned_lines


def pdf_to_markdown(pdf_path: str, md_name: str, api_key: str = None):
    assert pdf_path, f"PDF file: {pdf_path} not available"
    md = pymupdf4llm.to_markdown(pdf_path)
    lines = md.splitlines()

    cleaned_list = clean_markdown_lines(lines)

    md_cleaned = "\n".join(cleaned_list)
    with open(md_name, "w", encoding="utf-8") as f:
        f.write(md_cleaned)


def extract_subheadings(md_name: str) -> List[str]:
    """Extract all ## subheadings from a markdown file.

    Returns a list of heading texts with markdown formatting removed
    (e.g. '## **Introduction**' -> 'Introduction').
    """
    subheadings = []
    with open(md_name, "r", encoding="utf-8") as md:
        for line in md:
            clean_line = line.strip()
            if clean_line.startswith("## "):
                # Strip the '## ' prefix and any bold markers
                heading_text = clean_line[3:].replace("**", "").strip()
                if heading_text and heading_text != "References":
                    subheadings.append(heading_text)
    return subheadings


def populate_subheadings_to_metadata(json_path: str, md_path: str) -> None:
    """Populate the subheadings from the markdown file to the JSON file."""
    with open(json_path, "r", encoding="utf-8") as json_file:
        metadata = json.load(json_file)

    subheadings = extract_subheadings(md_path)
    metadata["subheadings"] = subheadings

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(metadata, json_file, indent=4)


def generate_metadata_json(
    pdf_path: str, output_path: str = None, api_key: str = None
) -> Dict[str, Any]:
    """Upload a PDF to Gemini and extract structured metadata as JSON.

    Uses JSON_PROMPT_TEMPLATE to instruct Gemini to analyse the visual layout
    of the PDF and return title, author information, abstract, and conflict
    of interest data.

    Args:
        pdf_path: Path to the PDF file.
        output_path: Where to save the JSON. Defaults to
                     ``<pdf_basename>_metadata.json``.
        api_key: Optional Gemini API Key.

    Returns:
        Parsed metadata dict.
    """
    path = Path(pdf_path)
    assert path.exists(), f"PDF file not found: {pdf_path}"

    # Default output path: same stem + _metadata.json
    if output_path is None:
        output_path = path.stem + "_metadata.json"

    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        client = genai.Client()

    # Upload the PDF via the Files API so Gemini can inspect its layout
    # uploaded_file = client.files.upload(file=pdf_path)
    interaction = client.interactions.create(
        model="gemini-3.1-flash-lite",
        input=[
            {
                "type": "document",
                "mime_type": "application/pdf",
                "data": base64.b64encode(path.read_bytes()).decode("utf-8"),
            },
            {"type": "text", "text": JSON_PROMPT_TEMPLATE},
        ],
    )

    # Strip markdown code fences if Gemini wraps the JSON in ```json ... ```
    raw_text = interaction.output_text.strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"```\s*$", "", raw_text)

    metadata = json.loads(raw_text)

    metadata["subheadings"] = []

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    print(f"Metadata saved to {output_path}")
    return metadata
