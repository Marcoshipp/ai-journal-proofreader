"""
Unit tests for the 5 back-matter section checks in checks/general.py.

Each test writes a small synthetic markdown string to a tmp file
(provided by pytest's `tmp_path` fixture) and calls the check function
directly — no PDFs, no Gemini, no running server needed.
"""
import pytest
from pathlib import Path

from checks.general import (
    check_section_order,
    check_acknowledgments,
    check_author_contributions,
    check_data_availability,
    check_financial_support,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_md(tmp_path: Path, content: str) -> str:
    """Write *content* to a temp file and return its path as a string."""
    p = tmp_path / "article.md"
    p.write_text(content, encoding="utf-8")
    return str(p)


def make_metadata(**kwargs) -> dict:
    """Build a minimal metadata dict for tests that need one."""
    base = {"authorInformation": [], "conflictOfInterest": ""}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# check_section_order
# ---------------------------------------------------------------------------

class TestCheckSectionOrder:

    def test_all_sections_correct_order(self, tmp_path):
        """All 4 sections present in the correct order → SUCCESS."""
        md = make_md(tmp_path, """
**Acknowledgments**
We thank the reviewers.

**Author contributions**
A did X, B did Y.

**Data availability statement**
Data available on request.

**Financial support and sponsorship**
Nil.
""")
        result = check_section_order(md)
        assert result.status == "SUCCESS"

    def test_wrong_order(self, tmp_path):
        """Author contributions appears BEFORE Acknowledgments → FAILURE."""
        md = make_md(tmp_path, """
**Author contributions**
A did X.

**Acknowledgments**
We thank the reviewers.

**Data availability statement**
Data available.

**Financial support and sponsorship**
Nil.
""")
        result = check_section_order(md)
        assert result.status == "FAILURE"
        assert any("FAILURE" in m for m in result.messages)

    def test_missing_one_section(self, tmp_path):
        """One section absent → WARNING (partial order check)."""
        md = make_md(tmp_path, """
**Acknowledgments**
We thank the reviewers.

**Author contributions**
A did X.

**Financial support and sponsorship**
Nil.
""")
        result = check_section_order(md)
        # Data availability statement is missing
        assert result.status == "WARNING"
        assert any("Data availability statement" in m for m in result.messages)

    def test_all_sections_missing(self, tmp_path):
        """No back-matter sections at all → WARNING."""
        md = make_md(tmp_path, "## Introduction\nBody text here.\n")
        result = check_section_order(md)
        assert result.status == "WARNING"


# ---------------------------------------------------------------------------
# check_acknowledgments
# ---------------------------------------------------------------------------

class TestCheckAcknowledgments:

    def test_section_absent_is_info(self, tmp_path):
        """Acknowledgments is optional — absent → INFO, not FAILURE."""
        md = make_md(tmp_path, "## Introduction\nSome text.\n")
        meta = make_metadata()
        result = check_acknowledgments(meta, md)
        assert result.status == "INFO"

    def test_clean_acknowledgments(self, tmp_path):
        """No author names, no financial keywords → SUCCESS."""
        md = make_md(tmp_path, """
**Acknowledgments**
We thank the staff at the hospital for their assistance.
""")
        meta = make_metadata(authorInformation=[{"name": "John Smith"}])
        result = check_acknowledgments(meta, md)
        assert result.status == "SUCCESS"

    def test_author_name_in_acknowledgments(self, tmp_path):
        """Author name present in Acknowledgments → FAILURE."""
        md = make_md(tmp_path, """
**Acknowledgments**
We thank John Smith for his support.
""")
        meta = make_metadata(authorInformation=[{"name": "John Smith"}])
        result = check_acknowledgments(meta, md)
        assert result.status == "FAILURE"
        assert any("John Smith" in m for m in result.messages)

    def test_financial_keyword_in_acknowledgments(self, tmp_path):
        """Financial keyword in Acknowledgments → FAILURE."""
        md = make_md(tmp_path, """
**Acknowledgments**
This study was funded by the Ministry of Health.
""")
        meta = make_metadata()
        result = check_acknowledgments(meta, md)
        assert result.status == "FAILURE"
        assert any("funded" in m or "Financial" in m for m in result.messages)

    def test_both_violations(self, tmp_path):
        """Both author name AND financial keyword → FAILURE."""
        md = make_md(tmp_path, """
**Acknowledgments**
John Smith received a grant from the foundation.
""")
        meta = make_metadata(authorInformation=[{"name": "John Smith"}])
        result = check_acknowledgments(meta, md)
        assert result.status == "FAILURE"


# ---------------------------------------------------------------------------
# check_author_contributions
# ---------------------------------------------------------------------------

class TestCheckAuthorContributions:

    def test_section_missing(self, tmp_path):
        """Section absent → FAILURE."""
        md = make_md(tmp_path, "## Introduction\nSome text.\n")
        result = check_author_contributions(md)
        assert result.status == "FAILURE"

    def test_correct_last_sentence(self, tmp_path):
        """Last sentence has required statement → SUCCESS."""
        md = make_md(tmp_path, """
**Author contributions**
A wrote the manuscript. B analysed the data.
All authors have read and agreed to the final version of the manuscript.
""")
        result = check_author_contributions(md)
        assert result.status == "SUCCESS"

    def test_missing_required_last_sentence(self, tmp_path):
        """Last sentence does not contain required statement → FAILURE."""
        md = make_md(tmp_path, """
**Author contributions**
A wrote the manuscript. B analysed the data.
""")
        result = check_author_contributions(md)
        assert result.status == "FAILURE"
        assert any("does NOT contain" in m for m in result.messages)

    def test_bold_markers_in_text_still_passes(self, tmp_path):
        """Bold markers (**) around words must not break the comparison."""
        md = make_md(tmp_path, """
**Author contributions**
**A** wrote the manuscript.
All authors have **read** and agreed to the final version of the manuscript.
""")
        result = check_author_contributions(md)
        assert result.status == "SUCCESS"

    def test_required_sentence_in_middle_not_last(self, tmp_path):
        """Required statement in the middle but NOT the last sentence → FAILURE."""
        md = make_md(tmp_path, """
**Author contributions**
All authors have read and agreed to the final version of the manuscript.
Additional disclaimer text added after.
""")
        result = check_author_contributions(md)
        assert result.status == "FAILURE"

    def test_empty_section(self, tmp_path):
        """Section header present but body is empty → FAILURE."""
        md = make_md(tmp_path, """
**Author contributions**

**Data availability statement**
Data available.
""")
        result = check_author_contributions(md)
        assert result.status == "FAILURE"


# ---------------------------------------------------------------------------
# check_data_availability
# ---------------------------------------------------------------------------

class TestCheckDataAvailability:

    def test_section_missing(self, tmp_path):
        """Section absent → FAILURE."""
        md = make_md(tmp_path, "## Introduction\nSome text.\n")
        result = check_data_availability(md)
        assert result.status == "FAILURE"

    def test_section_with_content(self, tmp_path):
        """Section present with declaration → SUCCESS."""
        md = make_md(tmp_path, """
**Data availability statement**
The data that support the findings of this study are available on request.
""")
        result = check_data_availability(md)
        assert result.status == "SUCCESS"

    def test_section_empty(self, tmp_path):
        """Section header present but no content → FAILURE."""
        md = make_md(tmp_path, """
**Data availability statement**

**Financial support and sponsorship**
Nil.
""")
        result = check_data_availability(md)
        assert result.status == "FAILURE"


# ---------------------------------------------------------------------------
# check_financial_support
# ---------------------------------------------------------------------------

class TestCheckFinancialSupport:

    def test_section_missing(self, tmp_path):
        """Section absent → FAILURE."""
        md = make_md(tmp_path, "## Introduction\nSome text.\n")
        result = check_financial_support(md)
        assert result.status == "FAILURE"

    def test_nil_declaration(self, tmp_path):
        """'Nil.' content → SUCCESS."""
        md = make_md(tmp_path, """
**Financial support and sponsorship**
Nil.
""")
        result = check_financial_support(md)
        assert result.status == "SUCCESS"

    def test_nil_case_insensitive(self, tmp_path):
        """'nil.' (lowercase) also counts as Nil. declaration."""
        md = make_md(tmp_path, """
**Financial support and sponsorship**
nil.
""")
        result = check_financial_support(md)
        assert result.status == "SUCCESS"

    def test_funding_with_grant_number(self, tmp_path):
        """Funding present with a grant number → SUCCESS."""
        md = make_md(tmp_path, """
**Financial support and sponsorship**
This study was supported by the Ministry of Health, grant number 110-2314-B-001-010.
""")
        result = check_financial_support(md)
        assert result.status == "SUCCESS"

    def test_funding_without_grant_number(self, tmp_path):
        """Funding mentioned but no grant number → FAILURE."""
        md = make_md(tmp_path, """
**Financial support and sponsorship**
This study was supported by the Ministry of Health.
""")
        result = check_financial_support(md)
        assert result.status == "FAILURE"
        assert any("grant/award number" in m for m in result.messages)
