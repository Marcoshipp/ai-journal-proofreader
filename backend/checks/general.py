import sys
from pathlib import Path

# Add the backend directory to sys.path so we can import from other modules when running this script directly
sys.path.append(str(Path(__file__).resolve().parent.parent))

import re
import difflib
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
import string
from dotenv import load_dotenv
from google import genai
from prompts.prompt import IRB_PROMPT_TEMPLATE
from playwright.sync_api import sync_playwright
from checks.extractions import (
    pdf_to_markdown,
    generate_metadata_json,
    populate_subheadings_to_metadata,
)

load_dotenv()

@dataclass
class ValidationResult:
    check_name: str
    status: str  # "SUCCESS", "WARNING", "FAILURE"
    messages: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


ARTICLES = {"a", "an", "the"}
PREPOSITIONS = {
    "about",
    "above",
    "across",
    "after",
    "against",
    "along",
    "among",
    "around",
    "at",
    "before",
    "behind",
    "below",
    "beneath",
    "beside",
    "between",
    "beyond",
    "but",
    "by",
    "concerning",
    "despite",
    "down",
    "during",
    "except",
    "for",
    "from",
    "in",
    "inside",
    "into",
    "like",
    "near",
    "of",
    "off",
    "on",
    "onto",
    "out",
    "outside",
    "over",
    "past",
    "since",
    "through",
    "throughout",
    "till",
    "to",
    "toward",
    "under",
    "underneath",
    "until",
    "up",
    "upon",
    "with",
    "within",
    "without",
}
# Usually, conjunctions are also lowercased in titles (and, but, or, nor)
CONJUNCTIONS = {"and", "but", "or", "nor", "yet", "so"}
LOWER_CASE_WORDS = ARTICLES | PREPOSITIONS | CONJUNCTIONS


def check_article_title(metadata: Dict[str, Any]) -> ValidationResult:
    title = metadata.get("titleName", "")
    messages = []
    issues = []

    if not title:
        messages.append("Error: Title not found or empty.")
        return ValidationResult(
            check_name="Article Title Check",
            status="FAILURE",
            messages=messages,
            details={"title": ""},
        )

    messages.append(f"Title found: {title}")
    words = title.split()
    has_error = False

    for idx, raw_word in enumerate(words):
        clean_word = raw_word.strip(string.punctuation)
        if not clean_word:
            continue
        is_first_word = idx == 0
        prev_ended_sentence = idx > 0 and words[idx - 1].endswith((":", "?", "!", "."))
        if "-" in clean_word or "‑" in clean_word:
            parts = clean_word.replace("‑", "-").split("-")
            if len(parts) > 1 and parts[0].istitle() and not parts[1].islower():
                issues.append(
                    f"Warning: Hyphenated suffix '{parts[1]}' in '{raw_word}' is not lowercase."
                )
            continue

        should_be_lower = clean_word.lower() in LOWER_CASE_WORDS

        # EXCEPTIONS where "should_be_lower" gets overruled:
        # - It's the first word of the title
        # - It's the first word of a subtitle (after a colon)
        if is_first_word or prev_ended_sentence:
            if not clean_word[0].istitle():
                reason = "Start of title" if is_first_word else "Start of subtitle"
                issues.append(f"Error: '{raw_word}' should be capitalized ({reason}).")
                has_error = True

        # CASE: Standard Lowercase Words (in middle of sentence)
        elif should_be_lower:
            if not clean_word.islower():
                issues.append(
                    f"Error: '{raw_word}' should be lowercase (Article/Preposition)."
                )
                has_error = True

        # CASE: Regular Words (Nouns, Verbs, etc.)
        else:
            if not clean_word[0].istitle():
                issues.append(f"Error: '{raw_word}' should be capitalized.")
                has_error = True

    status = "SUCCESS"
    if issues:
        status = "FAILURE" if has_error else "WARNING"
        messages.append(f"Found {len(issues)} issues:")
        messages.extend(issues)
    else:
        messages.append("Success: Title looks like it's in the correct format.")

    return ValidationResult(
        check_name="Article Title Check",
        status=status,
        messages=messages,
        details={"title": title, "issues": issues},
    )


def contains_aq(md_name) -> ValidationResult:
    # Read the file content
    assert md_name, f"markdown file: {md_name} not available"

    messages = []
    text = Path(md_name).read_text(encoding="utf-8")
    pattern = r"(AQ\d+):\s*(.*?)(?=(?:AQ\d+:|\n\*\*|\Z))"
    matches = re.findall(pattern, text, re.DOTALL)
    results = {label: content.strip() for label, content in matches}
    status = "WARNING"
    if results:
        messages.append(f"Detected {len(results)} AQs:")
        for idx, item in enumerate(results.items()):
            k, v = item
            if idx == len(results) - 1:
                v = v.split("\n")
                if "" in v:
                    v = v[: v.index("")]
                v = "\n".join(v)
            messages.append(f"{k} -> {v}")
    else:
        status = "SUCCESS"
        messages.append("No Author Queries (AQs) detected.")

    return ValidationResult(
        check_name="Author Queries Check",
        status=status,
        messages=messages,
        details={"aqs": results},
    )


def check_titles(metadata: Dict[str, Any], params: Dict[str, Any] = None) -> ValidationResult:
    subheadings = metadata.get("subheadings", [])
    messages = []
    params = params or {}

    expected_titles = params.get("expected_headings", [
        "Introduction",
        "Materials and Methods",
        "Results",
        "Discussion",
        "Conclusions",
    ])

    missing_titles = []
    warnings_count = 0

    for expected in expected_titles:
        # Case A: Exact Match
        if expected in subheadings:
            messages.append(f"[OK] Detected: {expected}")
        # Case B: Fuzzy Match
        else:
            close_matches = difflib.get_close_matches(
                expected, subheadings, n=1, cutoff=0.8
            )

            if close_matches:
                found_fuzzy = close_matches[0]
                messages.append(
                    f"[WARNING] Exact match missing for '{expected}'. Found similar header: '{found_fuzzy}'"
                )
                warnings_count += 1
            else:
                missing_titles.append(expected)

    status = "SUCCESS"
    if missing_titles:
        status = "FAILURE"
        messages.insert(
            0, f"Failed: Missing {len(missing_titles)} mandatory heading(s):"
        )
        for t in missing_titles:
            messages.append(f"  [X] {t}")
    elif warnings_count > 0:
        status = "WARNING"
        messages.insert(
            0,
            f"Passed with {warnings_count} warnings. Please check spelling/formatting.",
        )
    else:
        messages.insert(0, "Success: All mandatory headings detected perfectly.")

    return ValidationResult(
        check_name="Mandatory Headings Check",
        status=status,
        messages=messages,
        details={"missing": missing_titles, "warnings_count": warnings_count},
    )


DEFAULT_ABSTRACT_SECTIONS = [
    ("Background:",),
    ("Objectives:",),
    ("Materials and Methods:", "Materials and Methods:"),
    ("Results:",),
    ("Conclusions:",),
]


def check_abstract_structure(abstract_text, params: Dict[str, Any] = None) -> ValidationResult:
    messages = []
    params = params or {}
    if not abstract_text:
        return ValidationResult(
            check_name="Abstract Structure Check",
            status="FAILURE",
            messages=["[ERROR] Abstract text is empty."],
        )

    # Build expected_structure from params or fall back to defaults.
    # params["required_sections"] is a flat list of strings like ["Background:", "Results:"]
    # We wrap each in a tuple to preserve the existing variants-tuple logic.
    raw_sections = params.get("required_sections")
    if raw_sections:
        expected_structure = [(s,) for s in raw_sections]
    else:
        expected_structure = DEFAULT_ABSTRACT_SECTIONS

    # Split abstract into sections by looking for known headers
    pattern = r"([A-Z][A-Za-z\s]+:)"
    found_matches = re.findall(pattern, abstract_text)
    found_candidates = [m.strip() for m in found_matches]

    messages.append(
        f"Found {len(found_candidates)} potential headers in text: {found_candidates}"
    )

    # Fuzzy Compare (Expected vs Candidates)
    missing_items = []
    matched_candidates = set()
    warnings = 0

    for variants in expected_structure:
        primary_name = variants[0]
        found_any_variant = False

        # 1. Check Exact Matches
        for v in variants:
            if v in found_candidates:
                messages.append(f"[OK] Found: {v}")
                matched_candidates.add(v)
                found_any_variant = True
                break

        if found_any_variant:
            continue

        # 2. Check Fuzzy Matches
        matches = difflib.get_close_matches(
            primary_name, found_candidates, n=1, cutoff=0.6
        )

        if matches:
            messages.append(
                f"[WARNING] Exact match missing for '{primary_name}'. Found similar: '{matches[0]}'"
            )
            matched_candidates.add(matches[0])
            warnings += 1
        else:
            messages.append(f"[FAIL] Completely missing: {primary_name}")
            missing_items.append(primary_name)

    # Identify Extra/Unexpected Headers
    extra_headers = [c for c in found_candidates if c not in matched_candidates]
    if extra_headers:
        messages.append(
            f"[WARNING] Found extra headers not in expected list: {extra_headers}"
        )
        warnings += 1

    # Final Status Logic
    status = "SUCCESS"
    if missing_items:
        status = "FAILURE"
        messages.insert(0, f"Status: FAILED. Missing {len(missing_items)} section(s).")
    elif extra_headers or warnings > 0:
        status = "WARNING"
        msg = f"Status: PASSED with {warnings} formatting warning(s)"
        if extra_headers:
            msg += f" and {len(extra_headers)} unexpected header(s)"
        messages.insert(0, msg + ".")
    else:
        messages.insert(0, "Status: PERFECT. All sections found exactly as expected.")

    return ValidationResult(
        check_name="Abstract Structure Check",
        status=status,
        messages=messages,
        details={"missing": missing_items, "warnings": warnings},
    )


def check_abstract(metadata: Dict[str, Any], params: Dict[str, Any] = None) -> ValidationResult:
    abstract_text = metadata.get("abstract", "")
    return check_abstract_structure(abstract_text, params=params)



def print_report(results: List[ValidationResult], output_format: str = "text"):
    if output_format == "json":
        output = [r.to_dict() for r in results]
        print(json.dumps(output, indent=2))
    elif output_format == "markdown":
        lines = ["# Validation Report\n"]
        for res in results:
            lines.append(f"## {res.check_name}")
            status_emoji = "✅" if res.status == "SUCCESS" else "⚠️" if res.status == "WARNING" else "❌"
            lines.append(f"**Status**: {status_emoji} {res.status}\n")
            for msg in res.messages:
                lines.append(f"- {msg}")
            lines.append("")  # Add empty line between checks
        
        with open("report.md", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print("Report saved to report.md")
    else:
        for res in results:
            print(f"========== {res.check_name} ==========")
            print(f"Status: {res.status}")
            for msg in res.messages:
                print(f"  {msg}")
            print()


def get_text_from_heading(md_name: str, heading: str) -> str:
    extracted_lines = []
    capture = False
    
    # Determine the level of the target heading (e.g., "## " is level 2)
    heading_stripped = heading.strip()
    match = re.match(r"^(#+)", heading_stripped)
    if not match:
        print(f"[{heading}] is not a valid markdown heading.")
        return ""
    
    target_level = len(match.group(1))

    try:
        with open(md_name, "r", encoding="utf-8") as md:
            for line in md:
                clean_line = line.strip()
                
                # Check if we hit a new section that should stop capture
                if capture:
                    # Check if the line is a heading
                    curr_match = re.match(r"^(#+)", clean_line)
                    if curr_match:
                        curr_level = len(curr_match.group(1))
                        # If we encounter a heading of equal or higher level (smaller number), stop.
                        if curr_level <= target_level:
                            break
                    extracted_lines.append(line)
                
                # Check if we found the start heading
                if clean_line == heading_stripped:
                    capture = True
                    
        return "".join(extracted_lines)
    except FileNotFoundError:
        print(f"Error: File {md_name} not found.")
        return ""


def check_irb_and_pc(md_name: str, params: Dict[str, Any] = None) -> ValidationResult:
    params = params or {}
    api_key = params.get("_api_key")
    
    assert md_name, "Markdown filename is empty"
    text = get_text_from_heading(md_name, "## **Materials and Methods**")

    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        client = genai.Client()
        
    prompt = IRB_PROMPT_TEMPLATE.format(manuscript_text=text)

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
    )
    status = "INFO"
    return ValidationResult(
        check_name="IRB & Patient Consent check",
        status=status,
        messages=[response.text],
    )


def check_authors(metadata: Dict[str, Any]) -> ValidationResult:
    author_info = metadata.get("authorInformation", [])
    messages = []
    has_error = False
    
    # 1. Validate Author Names
    valid_authors_count = 0
    for author_obj in author_info:
        name = author_obj.get("name", "")
        
        if not name.strip():
            continue
            
        names = name.split()
        if len(names) < 2:
            messages.append(f"[ERROR] Author name '{name}' is too short (expected First name and Last name).")
            has_error = True
            continue
        messages.append(f"[INFO] Author name '{name}' is valid.")
            
        # Check capitalization
        if not (names[0][0].isupper() and names[1][0].isupper()):
            messages.append(f"[WARNING] Author name '{name}' may have incorrect capitalization.")
        
        valid_authors_count += 1

    if valid_authors_count == 0:
        messages.append("[ERROR] No valid authors found.")
        has_error = True
    else:
        messages.append(f"[INFO] {valid_authors_count} valid authors found.")

    # 2. Identify Corresponding Author
    c_authors = [a for a in author_info if a.get("isCorrespondenceAuthor", False)]
    
    if c_authors:
        for ca in c_authors:
            messages.append(f"[INFO] Corresponding author: {ca['name']}")
    else:
        messages.append("[WARNING] No corresponding author identified.")

    # Determine Final Status
    if has_error:
        status = "FAILURE"
    elif any("WARNING" in m for m in messages):
        status = "WARNING"
    else:
        status = "SUCCESS"

    return ValidationResult(
        check_name="Author Name Check",
        status=status,
        messages=messages,
    )


def fetch_editors(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        real_user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        context = browser.new_context(user_agent=real_user_agent)
        page = context.new_page()
        page.goto(url, wait_until="networkidle")
        text = page.locator("#wpHTMLContentEditor").inner_text()
        lines = text.split('\n')
        names = []

        for line in lines:
            if ", M.D." in line:
                name = line.split(',')[0].strip()
                if name and not name.isupper(): 
                    names.append(name)
        browser.close()
        return set(names)


def check_coi(metadata: Dict[str, Any], md_name: str, params: Dict[str, Any] = None) -> ValidationResult:
    messages = []
    has_error = False
    params = params or {}
    board_url = params.get("board_url", "https://journals.lww.com/FJMD/pages/editorialboard.aspx")
    
    # 1. Check Section Ordering (requires markdown file)
    with open(md_name, "r", encoding="utf-8") as md:
        before = False
        found_coi_section = False
        
        for line in md:
            clean_line = line.strip()
            if clean_line.startswith("**Financial support and sponsorship**"):
                before = True
                continue
            
            if clean_line.startswith("**Conflicts of interest**"):
                found_coi_section = True
                if not before:
                    messages.append("[FAILURE] 'Financial support and sponsorship' section must appear before 'Conflicts of interest'.")
                    has_error = True
                break

    if not found_coi_section:
        messages.append("[WARNING] 'Conflicts of interest' section not found in markdown.")

    # 2. Check COI content from metadata
    coi_text = metadata.get("conflictOfInterest", "")
    
    if not coi_text:
        messages.append("[WARNING] 'conflictOfInterest' is empty in metadata.")
        return ValidationResult("Conflict of Interest Check", "WARNING", messages)

    coi_declared = True
    if "no conflicts of interest" in coi_text.lower():
        coi_declared = False
    
    # 3. Check Editors vs Authors
    try:
        author_info = metadata.get("authorInformation", [])
        clean_authors = [a.get("name", "") for a in author_info if a.get("name")]

        editors = fetch_editors(board_url)
        for author in clean_authors:
            if "\u2011" in author:
                author = author.replace("\u2011", "-")
            if author in editors:
                if coi_declared:
                    messages.append(f"[FAILURE] Author '{author}' is an Editor but no Conflict of Interest was declared.")
                    has_error = True
                else:
                    if author not in coi_text:
                        messages.append(f"[FAILURE] Author '{author}' is an Editor but COI section did not mention him.")
                        has_error = True
                    else:
                        messages.append(f"[INFO] Author '{author}' is an Editor and COI section mentioned him.")
                
    except Exception as e:
        messages.append(f"[WARNING] Failed to fetch editors or parse authors for COI check: {e}")

    status = "FAILURE" if has_error else "SUCCESS"
    if status == "SUCCESS":
        messages.append("[INFO] No conflicts of interest found.")
    return ValidationResult(
        check_name="Conflict of Interest Check",
        status=status,
        messages=messages,
    )

def check_keywords(metadata: Dict[str, Any]) -> ValidationResult:
    keywords = metadata.get("keywords", None)
    messages = []
    has_error = False

    if not keywords:
        messages.append("[WARNING] 'keywords' is empty in metadata.")
        return ValidationResult("Keywords Check", "WARNING", messages)

    keywords = keywords.strip().split(",")
    messages.append(f"[INFO] {len(keywords)} keyword(s) found: {keywords}")

    # Check alphabetical order (case-insensitive)
    lowered = [k.lower() for k in keywords]
    if lowered != sorted(lowered):
        messages.append(
            f"[FAILURE] Keywords are not in alphabetical order. "
            f"Expected order: {sorted(keywords, key=str.lower)}"
        )
        has_error = True
    else:
        messages.append("[OK] Keywords are in alphabetical order.")

    # Check for duplicates
    seen = set()
    duplicate_pass = True
    for kw in lowered:
        if kw in seen:
            messages.append(f"[FAILURE] Duplicate keyword detected: '{kw}'")
            has_error = True
            duplicate_pass = False
        seen.add(kw)
    
    if duplicate_pass:
        messages.append("[OK] No duplicate keywords found.")
    status = "FAILURE" if has_error else "SUCCESS"

    # Tell user to manually check the capitalization of keywords
    messages.append("[INFO] Please manually check the capitalization of keywords.")

    return ValidationResult("Keywords Check", status, messages)
    
def check_date_format(metadata: Dict[str, Any], params: Dict[str, Any] = None) -> ValidationResult:
    params = params or {}
    # Default required date labels (case-insensitive matching)
    required_dates = params.get("required_dates", ["Received", "Revised", "Accepted", "Published"])
    
    # date_format is now a list of {label, date} objects
    # Support both the new list format and the legacy dict format for backwards compatibility
    raw_date_format = metadata.get("date_format", [])
    if isinstance(raw_date_format, dict):
        # Legacy format: {"received": "...", "revised": "...", ...}
        found_labels = {k.capitalize(): v for k, v in raw_date_format.items() if v}
    elif isinstance(raw_date_format, list):
        # New format: [{label: "Received", date: "..."}, ...]
        found_labels = {}
        for entry in raw_date_format:
            if isinstance(entry, dict) and entry.get("label") and entry.get("date"):
                found_labels[entry["label"].strip()] = entry["date"]
    else:
        found_labels = {}

    messages = []
    has_error = False

    for required in required_dates:
        # Case-insensitive lookup
        matched = next(
            (v for k, v in found_labels.items() if k.lower() == required.lower()),
            None,
        )
        if matched:
            messages.append(f"[INFO] '{required}' date found: {matched}")
        else:
            messages.append(f"[FAILURE] '{required}' date not found.")
            has_error = True

    # Report any extra date labels found in the document (informational)
    required_lower = {r.lower() for r in required_dates}
    extra = [k for k in found_labels if k.lower() not in required_lower]
    if extra:
        messages.append(f"[INFO] Additional date labels found (not required): {extra}")

    status = "FAILURE" if has_error else "SUCCESS"
    return ValidationResult(
        check_name="Date Format Check",
        status=status,
        messages=messages,
    )

def check_online_access(metadata: Dict[str, Any], params: Dict[str, Any] = None) -> ValidationResult:
    params = params or {}
    expected_url = params.get("expected_url", "")
    
    online_access = metadata.get("online_access", dict())
    messages = []
    has_error = False
    doi = online_access.get("doi", None)
    website = online_access.get("website", None)
    qr_code = online_access.get("qr_code", None)
    is_at_first_page = online_access.get("is_at_first_page", None)

    if not doi:
        messages.append("[FAILURE] The DOI was not found.")
        has_error = True
    else:
        messages.append(f"[INFO] The DOI was found: {doi}")
        
    if not website:
        messages.append("[FAILURE] The website URL was not found.")
        has_error = True
    else:
        if expected_url:
            # Simple substring match check (e.g. journals.lww.com/fjmd)
            if expected_url.strip().lower() in website.lower() or website.lower() in expected_url.strip().lower():
                messages.append(f"[INFO] The website URL matches the expected URL: {website}")
            else:
                messages.append(f"[FAILURE] The website URL ({website}) does not match the expected URL ({expected_url}).")
                has_error = True
        else:
            messages.append(f"[INFO] The website URL was found: {website}")
    if qr_code:
        messages.append("[FAILURE] The QR Code was found.")
        has_error = True
    else:
        messages.append("[INFO] The QR Code is empty as expected.")
    if not is_at_first_page:
        messages.append("[FAILURE] Online Access wasn't found at first page.")
        has_error = True
    else:
        messages.append("[INFO] Online Access was found at first page.")

    if has_error:
        status = "FAILURE"
    else:
        status = "SUCCESS"
    return ValidationResult(
        check_name="Online Access Check",
        status=status,
        messages=messages,
    )

def check_htcta(metadata: Dict[str, Any]) -> ValidationResult:
    """Check the 'How to Cite This Article' (HTCTA) field.

    Rules:
    1. Must contain all required fields: authors, title, journal name, year, vol/issue, pages.
    2. Format: Authors. Title. Journal Abbrev Year;Vol:Pages.
    3. Author format: LastName Initials (e.g. "Yen JZ"), max 6 authors then "et al."
    4. Title must be in Sentence case; first word after a colon must be capitalised.
    5. Must end with a period.
    6. Volume/issue and pages may be "XX" (placeholder).
    """
    htcta = metadata.get("htcta", None)
    messages = []
    has_error = False

    if not htcta:
        return ValidationResult(
            check_name="How to Cite This Article Check",
            status="FAILURE",
            messages=["[FAILURE] 'htcta' field not found in metadata."],
        )

    messages.append(f"[INFO] 'htcta' found: {htcta}")

    # ------------------------------------------------------------------ #
    # Rule 5: Must end with a period                                       #
    # ------------------------------------------------------------------ #
    if not htcta.rstrip().endswith("."):
        messages.append("[FAILURE] HTCTA string does not end with a period ('.').")
        has_error = True
    else:
        messages.append("[OK] String ends with a period.")

    # ------------------------------------------------------------------ #
    # Parse into three major parts using regex:                            #
    #   <Authors>. <Title>. <Journal Year;Vol:Pages>.                     #
    # We use a non-greedy match for each section separated by ". "        #
    # ------------------------------------------------------------------ #
    normalised = htcta.replace("\u2011", "-")  # normalise non-breaking hyphens

    pattern = re.compile(
        r"^"
        r"(?P<authors>.+?)\.\s+"    # authors block, ends at first ". "
        r"(?P<title>.+?)\.\s+"      # title block
        r"(?P<citation>.+\.)"       # journal + year;vol:pages.
        r"\s*$",
        re.DOTALL,
    )
    m = pattern.match(normalised)

    if not m:
        messages.append(
            "[FAILURE] Could not parse HTCTA into the expected format: "
            "'Authors. Title. Journal Year;Vol:Pages.'"
        )
        return ValidationResult(
            check_name="How to Cite This Article Check",
            status="FAILURE",
            messages=messages,
        )

    authors_str  = m.group("authors").strip()
    title_str    = m.group("title").strip()
    citation_str = m.group("citation").strip()

    messages.append(f"[INFO] Authors block : {authors_str}")
    messages.append(f"[INFO] Title block   : {title_str}")
    messages.append(f"[INFO] Citation block: {citation_str}")

    # ------------------------------------------------------------------ #
    # Rule 3: Author format — LastName Initials, up to 6, then "et al."  #
    # ------------------------------------------------------------------ #
    raw_authors = [a.strip() for a in authors_str.split(",") if a.strip()]
    has_et_al = raw_authors and raw_authors[-1].lower() in ("et al.", "et al")
    author_list = raw_authors[:-1] if has_et_al else raw_authors

    author_format_re = re.compile(r"^[A-Z][a-zA-Z\-]+\s+[A-Z]{1,4}$")
    for author in author_list:
        if author_format_re.match(author):
            messages.append(f"[OK] Author format valid: '{author}'")
        else:
            messages.append(
                f"[FAILURE] Author '{author}' does not match expected format 'LastName XX' "
                "(last name followed by uppercase initials)."
            )
            has_error = True

    if len(author_list) > 6 and not has_et_al:
        messages.append(
            f"[FAILURE] More than 6 authors listed ({len(author_list)}) without 'et al.' — "
            "please truncate at 6 and append 'et al.'"
        )
        has_error = True
    elif len(author_list) >= 6 and has_et_al:
        messages.append("[OK] 6 or more authors correctly abbreviated with 'et al.'")
    elif len(author_list) < 6 and has_et_al:
        messages.append(
            f"[WARNING] 'et al.' found but only {len(author_list)} named authors "
            "(et al. is typically used when there are more than 6 authors)."
        )

    # ------------------------------------------------------------------ #
    # Rule 3b: Cross-reference HTCTA authors against authorInformation    #
    # Converts "Firstname [Middle] Lastname" to "Lastname FM" and checks  #
    # whether each expected author appears in the HTCTA string.           #
    # Emits WARNINGs (not FAILUREs) to tolerate extraction imprecision.  #
    # ------------------------------------------------------------------ #
    def to_htcta_format(full_name: str) -> str:
        """Convert 'First [Middle] Last' → 'Last FI' (HTCTA abbreviation)."""
        parts = full_name.strip().replace("\u2011", "-").split()
        if len(parts) < 2:
            return full_name  # can't convert, return as-is
        last = parts[-1]
        initials = "".join(p[0].upper() for p in parts[:-1])
        return f"{last} {initials}"

    author_info = metadata.get("authorInformation", [])
    if author_info:
        # Only cross-check up to the first 6 (the ones that should appear before et al.)
        expected_authors = [a.get("name", "") for a in author_info if a.get("name")]
        check_count = min(len(expected_authors), 6)
        expected_to_check = expected_authors[:check_count]

        htcta_authors_lower = [a.lower() for a in author_list]

        for full_name in expected_to_check:
            converted = to_htcta_format(full_name)
            converted_lower = converted.lower()
            # Check exact converted match OR if the last name alone appears in the list
            last_name = full_name.strip().split()[-1].lower()
            match_found = any(
                converted_lower == htcta_a or last_name == htcta_a.split()[0].lower()
                for htcta_a in htcta_authors_lower
            )
            if match_found:
                messages.append(f"[OK] Author '{full_name}' (→ '{converted}') found in HTCTA.")
            else:
                messages.append(
                    f"[WARNING] Author '{full_name}' (→ '{converted}') not found in HTCTA — "
                    "please verify the author list manually."
                )

        # Check if HTCTA has more authors than authorInformation
        if len(author_list) > len(expected_authors) and not has_et_al:
            messages.append(
                f"[WARNING] HTCTA lists {len(author_list)} authors but metadata only has "
                f"{len(expected_authors)} — there may be extra authors in the HTCTA string."
            )
    else:
        messages.append("[INFO] No authorInformation in metadata — skipping author cross-reference.")

    # ------------------------------------------------------------------ #
    # Rule 4: Title — Sentence case, capitalise first word after colon    #
    # ------------------------------------------------------------------ #
    title_words = title_str.split()
    if title_words:
        if not title_words[0][0].isupper():
            messages.append(
                f"[FAILURE] Title first word '{title_words[0]}' must start uppercase (Sentence case)."
            )
            has_error = True
        else:
            messages.append("[OK] Title starts with an uppercase letter.")

        # Collect indices that should be capitalised (position 0 + after ":")
        must_capitalise = {0}
        for i, word in enumerate(title_words):
            if word.rstrip().endswith(":") and i + 1 < len(title_words):
                must_capitalise.add(i + 1)

        for i, word in enumerate(title_words):
            clean = word.strip("\"'(),;")
            if not clean:
                continue
            if i in must_capitalise:
                if not clean[0].isupper():
                    label = "after colon" if i > 0 else "first word"
                    messages.append(
                        f"[FAILURE] Title word '{word}' ({label}) must start with an uppercase letter."
                    )
                    has_error = True
                elif i > 0:
                    messages.append(f"[OK] Word after colon '{word}' is correctly capitalised.")
            else:
                # Non-mandatory positions should be lowercase (warn if unexpectedly capitalised)
                if clean[0].isupper() and clean.isalpha() and not clean.isupper():
                    messages.append(
                        f"[WARNING] Title word '{word}' at position {i + 1} is capitalised — "
                        "ensure this is a proper noun (Sentence case expected)."
                    )

    # ------------------------------------------------------------------ #
    # Rule 1 & 2: Citation — Journal Year;Vol:Pages.                      #
    # Vol and Pages may be "XX" or numeric.                               #
    # ------------------------------------------------------------------ #
    citation_pattern = re.compile(
        r"^(?P<journal>.+?)\s+"
        r"(?P<year>\d{4});"
        r"(?P<vol>[A-Z0-9]+):"
        r"(?P<pages>[A-Z0-9\-]+)\.?$",
        re.IGNORECASE,
    )
    cm = citation_pattern.match(citation_str)
    if cm:
        messages.append(f"[OK] Journal abbreviation : '{cm.group('journal')}'")
        messages.append(f"[OK] Year                 : {cm.group('year')}")
        messages.append(f"[OK] Volume/Issue         : {cm.group('vol')}")
        messages.append(f"[OK] Pages                : {cm.group('pages')}")
    else:
        messages.append(
            "[FAILURE] Citation block does not match expected format "
            f"'Journal Abbrev Year;Vol:Pages.' — got: '{citation_str}'"
        )
        has_error = True

    # ------------------------------------------------------------------ #
    # Final status                                                         #
    # ------------------------------------------------------------------ #
    if has_error:
        status = "FAILURE"
    elif any("[WARNING]" in msg for msg in messages):
        status = "WARNING"
    else:
        status = "SUCCESS"

    return ValidationResult(
        check_name="HTCTA Check",
        status=status,
        messages=messages,
    )

# ---------------------------------------------------------------------------
# Bold-section helpers & new back-matter checks
# ---------------------------------------------------------------------------

BACK_MATTER_SECTIONS = [
    "Acknowledgments",
    "Author contributions",
    "Data availability statement",
    "Financial support and sponsorship",
]


def get_text_from_bold_section(md_name: str, section_name: str) -> str | None:
    """Return the text that follows a **bold** section label in the markdown.

    Scans line-by-line for a line whose de-bolded text starts with
    *section_name* (case-insensitive). Captures subsequent lines until it
    hits the next bold-only label (``**Something**``) or a ``##`` heading.
    Returns ``None`` if the section label is never found.
    """
    lines = Path(md_name).read_text(encoding="utf-8").splitlines()
    capturing = False
    result = []

    for line in lines:
        stripped = line.strip()
        # De-bold the line for comparison
        clean = stripped.replace("**", "").strip()

        # Detect start of our target section
        if not capturing:
            if clean.lower().startswith(section_name.lower()):
                capturing = True
            continue

        # Stop at the next bold-label line or markdown heading
        if re.match(r"^\*\*.+\*\*\s*$", stripped) or stripped.startswith("#"):
            break

        result.append(line)

    return "\n".join(result).strip() if capturing else None


def _find_bold_section_line(lines: list[str], section_name: str) -> int | None:
    """Return the 0-based line index of a bold section label, or None."""
    for i, line in enumerate(lines):
        clean = line.strip().replace("**", "").strip()
        if clean.lower().startswith(section_name.lower()):
            return i
    return None


def check_section_order(md_name: str) -> ValidationResult:
    """Verify the 4 back-matter sections appear in the required order:

    Acknowledgments → Author contributions → Data availability statement
    → Financial support and sponsorship
    """
    lines = Path(md_name).read_text(encoding="utf-8").splitlines()
    messages = []
    has_error = False

    positions: dict[str, int] = {}
    for section in BACK_MATTER_SECTIONS:
        idx = _find_bold_section_line(lines, section)
        if idx is not None:
            positions[section] = idx
            messages.append(f"[OK] Found: '{section}' at line {idx + 1}")
        else:
            messages.append(f"[WARNING] Could not find section: '{section}'")

    # Check ordering only among sections that were found
    found_ordered = [s for s in BACK_MATTER_SECTIONS if s in positions]
    for i in range(len(found_ordered) - 1):
        a, b = found_ordered[i], found_ordered[i + 1]
        if positions[a] >= positions[b]:
            messages.append(
                f"[FAILURE] '{a}' (line {positions[a] + 1}) must appear "
                f"before '{b}' (line {positions[b] + 1}), but the order is wrong."
            )
            has_error = True

    if has_error:
        status = "FAILURE"
    elif len(found_ordered) < len(BACK_MATTER_SECTIONS):
        status = "WARNING"
        messages.insert(0, "Some sections could not be found — order check is partial.")
    else:
        status = "SUCCESS"
        messages.insert(0, "[OK] All 4 sections appear in the correct order.")

    return ValidationResult(
        check_name="Section Order Check",
        status=status,
        messages=messages,
        details={"positions": {k: v + 1 for k, v in positions.items()}},
    )


def check_acknowledgments(metadata: Dict[str, Any], md_name: str) -> ValidationResult:
    """Check Acknowledgments section rules (section is optional).

    Rules:
    1. Section is optional — only checked if present.
    2. Must not contain any author names.
    3. Must not contain financial/funding statements (those belong in FSS).
    """
    messages = []
    text = get_text_from_bold_section(md_name, "Acknowledgments")

    if text is None:
        return ValidationResult(
            check_name="Acknowledgments Check",
            status="INFO",
            messages=["[INFO] Acknowledgments section is absent — skipping check (optional)."],
        )

    has_error = False

    # Rule 2: No author names
    author_info = metadata.get("authorInformation", [])
    author_names = [a.get("name", "") for a in author_info if a.get("name")]
    found_authors = [name for name in author_names if name and name in text]
    if found_authors:
        messages.append(
            f"[FAILURE] Author name(s) found in Acknowledgments: {found_authors}. "
            "Author names must not appear here."
        )
        has_error = True
    else:
        messages.append("[OK] No author names detected in Acknowledgments.")

    # Rule 3: No financial/funding content
    financial_keywords = [
        "grant", "funded", "funding", "supported by", "financial support",
        "ministry", "foundation", "award", "contract",
    ]
    found_financial = [
        kw for kw in financial_keywords if kw.lower() in text.lower()
    ]
    if found_financial:
        messages.append(
            f"[FAILURE] Financial keywords detected in Acknowledgments: {found_financial}. "
            "Funding statements should be in 'Financial support and sponsorship'."
        )
        has_error = True
    else:
        messages.append("[OK] No financial/funding content detected in Acknowledgments.")

    status = "FAILURE" if has_error else "SUCCESS"
    return ValidationResult(
        check_name="Acknowledgments Check",
        status=status,
        messages=messages,
    )


ALL_AUTHORS_SENTENCE = "all authors have read and agreed to the final version of the manuscript"


def check_author_contributions(md_name: str, params: Dict[str, Any] = None) -> ValidationResult:
    """Check Author contributions section rules.

    Rules:
    1. Section must be present.
    2. Last sentence must contain the mandatory all-authors agreement statement.
    """
    params = params or {}
    # The frontend 'string_list' schema saves as a list of strings. Support both list and raw string.
    raw_statement = params.get("required_statement", [ALL_AUTHORS_SENTENCE])
    if isinstance(raw_statement, str):
        required_statements = [raw_statement]
    else:
        # Filter out empty strings just in case
        required_statements = [s for s in raw_statement if s.strip()]
        if not required_statements:
            required_statements = [ALL_AUTHORS_SENTENCE]
    
    messages = []
    text = get_text_from_bold_section(md_name, "Author contributions")

    if text is None:
        return ValidationResult(
            check_name="Author Contributions Check",
            status="FAILURE",
            messages=["[FAILURE] 'Author contributions' section not found."],
        )

    messages.append("[OK] 'Author contributions' section found.")

    # Strip markdown bold markers and normalise whitespace before comparing
    clean_text = re.sub(r"\*\*", "", text)          # remove **
    clean_text = re.sub(r"\s+", " ", clean_text).strip()  # collapse newlines/spaces

    # Split into sentences and check the last non-empty one
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_text) if s.strip()]
    if not sentences:
        messages.append("[FAILURE] 'Author contributions' section appears to be empty.")
        return ValidationResult(
            check_name="Author Contributions Check",
            status="FAILURE",
            messages=messages,
        )

    last_sentence = sentences[-1].lower()
    
    # Check if ANY of the required statements appear in the last sentence
    matched_statement = next(
        (stmt for stmt in required_statements if stmt.lower() in last_sentence),
        None
    )

    if matched_statement:
        messages.append(
            f'[OK] Last sentence contains the required statement: "{matched_statement}"'
        )
        status = "SUCCESS"
    else:
        messages.append(
            f'[FAILURE] Last sentence does NOT contain the required statement(s).'
        )
        messages.append(f'  Expected one of: {required_statements}')
        messages.append(f'  Found instead: "{sentences[-1]}"')
        status = "FAILURE"

    return ValidationResult(
        check_name="Author Contributions Check",
        status=status,
        messages=messages,
    )


def check_data_availability(md_name: str) -> ValidationResult:
    """Check Data availability statement section rules.

    Rules:
    1. Section must be present.
    2. Section must contain a declaration (non-empty content).
    """
    messages = []
    text = get_text_from_bold_section(md_name, "Data availability statement")

    if text is None:
        return ValidationResult(
            check_name="Data Availability Statement Check",
            status="FAILURE",
            messages=["[FAILURE] 'Data availability statement' section not found."],
        )

    messages.append("[OK] 'Data availability statement' section found.")

    if text.strip():
        messages.append("[OK] Section contains a declaration.")
        status = "SUCCESS"
    else:
        messages.append("[FAILURE] 'Data availability statement' section is empty — a declaration is required.")
        status = "FAILURE"

    return ValidationResult(
        check_name="Data Availability Statement Check",
        status=status,
        messages=messages,
    )


def check_financial_support(md_name: str) -> ValidationResult:
    """Check Financial support and sponsorship section rules.

    Rules:
    1. Section must be present.
    2a. If funding exists → institution name and grant/award number must be mentioned.
    2b. If no funding → section must state "Nil."
    """
    messages = []
    text = get_text_from_bold_section(md_name, "Financial support and sponsorship")

    if text is None:
        return ValidationResult(
            check_name="Financial Support and Sponsorship Check",
            status="FAILURE",
            messages=["[FAILURE] 'Financial support and sponsorship' section not found."],
        )

    messages.append("[OK] 'Financial support and sponsorship' section found.")
    has_error = False
    content = text.strip()

    if content.lower().startswith("nil"):
        messages.append('[OK] No funding declared ("Nil.")."')
    else:
        # If there is content, look for a grant/award number (digits in the text
        # or common patterns like #12345, grant 123456, etc.)
        has_number = bool(re.search(r"\b(grant|award|contract|no\.?|number|#)?\s*\d{4,}\b", content, re.IGNORECASE))
        if has_number:
            messages.append("[OK] Grant/award number detected in funding statement.")
        else:
            messages.append(
                "[FAILURE] Funding appears to be declared but no grant/award number was detected. "
                "Please include the institution name and grant number, or write \"Nil.\""
            )
            has_error = True

    status = "FAILURE" if has_error else "SUCCESS"
    return ValidationResult(
        check_name="Financial Support and Sponsorship Check",
        status=status,
        messages=messages,
    )


# if __name__ == "__main__":
#     test_metadata = {
#         "htcta": "Yen JZ, Chuang HC, Hong CK, Hsu KL, Kuan FC, Chen Y, et al. The number of loaded sutures alter the suture‑holding strength in different knotless suture anchors: A biomechanical study. Formos J Musculoskelet Disord 2025;XX:XX-XX."
#     }
    
#     # Run the specific check
#     results = [check_htcta(test_metadata)]
    
#     # Print the report to the console
#     print_report(results)
