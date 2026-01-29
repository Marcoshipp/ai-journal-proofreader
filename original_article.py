from pathlib import Path
import pymupdf4llm
import re
import difflib
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
import string


@dataclass
class ValidationResult:
    check_name: str
    status: str  # "SUCCESS", "WARNING", "FAILURE"
    messages: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def pdf_to_markdown(pdf_path: str, md_name: str):
    assert pdf_path, f"PDF file: {pdf_path} not available"
    md = pymupdf4llm.to_markdown(pdf_path)
    lines = md.splitlines()

    def filtering_logic(line: str):
        if line.strip().isnumeric():
            return ""
        if re.search(r"^\d+AQ", line):
            return re.sub(r"^\d+(AQ.*)", r"\1", line)
        if re.match(r"^\d+\s+[A-Za-z0-9]", line):
            return re.sub(r"^\d+\s+([A-Za-z0-9].*)", r"\1", line)
        return line

    cleaned_list = []
    for line in lines:
        result = filtering_logic(line)
        if result == "":
            cleaned_list.append("\n")
        else:
            cleaned_list.append(result)

    md_cleaned = "\n".join(cleaned_list).replace("*****", "")
    with open(md_name, "w") as md:
        md.write(md_cleaned)


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


def get_article_title(md_name: str) -> str:
    """Extracts title from markdown line after **Original Article** tag."""
    article_start = False
    try:
        with open(md_name, "r", encoding="utf-8") as md:
            for line in md:
                clean_line = line.strip()
                if clean_line == "**Original Article**":
                    article_start = True
                    continue

                if article_start and clean_line.startswith("#"):
                    # Split only once on #, take the second part
                    return clean_line.split("#", 1)[1].strip().replace("**", "")
    except FileNotFoundError:
        print(f"Error: File {md_name} not found.")
    return ""


def check_article_title(md_name: str) -> ValidationResult:
    title = get_article_title(md_name)
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
        prev_ended_colon = idx > 0 and words[idx - 1].endswith(":")

        if "-" in clean_word or "‑" in clean_word:
            parts = clean_word.replace("‑", "-").split("-")
            if len(parts) > 1 and not parts[1].islower():
                issues.append(
                    f"Warning: Hyphenated suffix '{parts[1]}' in '{raw_word}' is not lowercase."
                )
            continue

        should_be_lower = clean_word.lower() in LOWER_CASE_WORDS

        # EXCEPTIONS where "should_be_lower" gets overruled:
        # - It's the first word of the title
        # - It's the first word of a subtitle (after a colon)
        if is_first_word or prev_ended_colon:
            if not clean_word[0].isupper():
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
            if not clean_word[0].isupper():
                issues.append(f"Error: '{raw_word}' should be capitalized.")
                has_error = True

    status = "SUCCESS"
    if issues:
        status = "FAILURE" if has_error else "WARNING"
        messages.append(f"Found {len(issues)} issues:")
        messages.extend(issues)
    else:
        messages.append("Success: Title capitalization looks correct.")

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

    if results:
        messages.append(f"Detected {len(results)} AQs:")
        for k, v in results.items():
            messages.append(f"{k} -> {v}")
    else:
        messages.append("No Author Queries (AQs) detected.")

    return ValidationResult(
        check_name="Author Queries Check",
        status="WARNING",
        messages=messages,
        details={"aqs": results},
    )


def check_titles(md_name) -> ValidationResult:
    assert md_name, f"markdown file: {md_name} not available"

    messages = []
    expected_titles = [
        "## **Introduction**",
        "## **Materials and Methods**",
        "## **Results**",
        "## **Discussion**",
        "## **Conclusions**",
    ]

    "Background:"

    file_headers = []
    with open(md_name, "r", encoding="utf-8") as md:
        for line in md:
            clean_line = line.strip()
            if clean_line.startswith("##"):
                file_headers.append(clean_line)

    missing_titles = []
    warnings_count = 0

    for expected in expected_titles:
        # Case A: Exact Match
        if expected in file_headers:
            messages.append(f"[OK] Detected: {expected}")
        # Case B: Fuzzy Match (The new feature)
        else:
            # get_close_matches returns a list of similar strings.
            # n=1 means "get the top 1 match".
            # cutoff=0.8 means "must be at least 80% similar".
            close_matches = difflib.get_close_matches(
                expected, file_headers, n=1, cutoff=0.8
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


def check_abstract_structure(abstract_text) -> ValidationResult:
    messages = []
    if not abstract_text:
        return ValidationResult(
            check_name="Abstract Structure Check",
            status="FAILURE",
            messages=["[ERROR] Abstract text is empty."],
        )

    expected_subtitles = [
        "**Background:**",
        "**Perspectives:**",
        "**Materials** **and** **Methods:**",
        "**Results:**",
        "**Conclusions:**",
    ]

    # Explanation of regex r"((?:\*\*.*?\*\*\s*)+:?)"
    # This captures all strings that starts wth ** and ends with :**
    pattern = r"((?:\*\*.*?\*\*\s*)+:?)"

    found_matches = re.findall(pattern, abstract_text)
    found_candidates = [m.strip() for m in found_matches]

    messages.append(
        f"Found {len(found_candidates)} potential headers in text: {found_candidates}"
    )

    # 3. Fuzzy Compare (Expected vs Candidates)
    missing_items = []
    warnings = 0

    for expected in expected_subtitles:
        # Exact Match
        if expected in found_candidates:
            messages.append(f"[OK] Found: {expected}")

        # Fuzzy Match (Typo or formatting difference)
        else:
            matches = difflib.get_close_matches(
                expected, found_candidates, n=1, cutoff=0.6
            )

            if matches:
                messages.append(
                    f"[WARNING] Exact match missing for '{expected}'. Found similar: '{matches[0]}'"
                )
                warnings += 1
            else:
                messages.append(f"[FAIL] Completely missing: {expected}")
                missing_items.append(expected)

    status = "SUCCESS"
    if missing_items:
        status = "FAILURE"
        messages.insert(0, f"Status: FAILED. Missing {len(missing_items)} section(s).")
    elif warnings > 0:
        status = "WARNING"
        messages.insert(0, f"Status: PASSED with {warnings} formatting warning(s).")
    else:
        messages.insert(0, "Status: PERFECT. All sections found exactly as expected.")

    return ValidationResult(
        check_name="Abstract Structure Check",
        status=status,
        messages=messages,
        details={"missing": missing_items, "warnings": warnings},
    )


def check_abstract(md_name) -> ValidationResult:
    assert md_name, f"markdown file: {md_name} not available"
    abstract_heading = "**Abstract**"
    keyword_heading = "**Keywords:**"

    start = False
    abstract_text = ""

    with open(md_name, "r", encoding="utf-8") as md:
        for line in md:
            clean_line = line.strip()
            # Stop if we hit keywords
            if keyword_heading in clean_line:
                break
            # Collect text
            if start:
                abstract_text += line.strip() + " "
            # Start signal
            if abstract_heading in clean_line:
                start = True

    final_text = abstract_text.strip()
    return check_abstract_structure(final_text)


def print_report(results: List[ValidationResult], output_format: str = "text"):
    if output_format == "json":
        output = [r.to_dict() for r in results]
        print(json.dumps(output, indent=2))
    else:
        for res in results:
            print(f"========== {res.check_name} ==========")
            print(f"Status: {res.status}")
            for msg in res.messages:
                print(f"  {msg}")
            print()


if __name__ == "__main__":
    pdf_path = "source_docs/test.pdf"
    md_name = "test.md"
    # pdf_to_markdown(pdf_path, md_name)

    # results = []
    # results.append(contains_aq(md_name))
    # results.append(check_titles(md_name))
    # results.append(check_abstract(md_name))

    # print_report(results, output_format="text")

    result = check_article_title(md_name)
    print_report([result], output_format="text")
