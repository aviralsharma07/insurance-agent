"""Test text reversal and table extraction on problematic PDF pages."""

import pdfplumber
import re
from pathlib import Path

HANDBOOK_DIR = Path(
    "/Users/aviralsharma/Personal Projects/policy_data/_irdai_reference/data"
)


def reverse_text(s):
    """Reverse each line character by character."""
    return s[::-1]


def diagnose_page(filename, page_num, label):
    path = HANDBOOK_DIR / filename
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_num - 1]
        text = page.extract_text() or ""

        print(f"\n{'=' * 80}")
        print(f"[{label}] Page {page_num} of {filename}")
        print(f"{'=' * 80}")
        print(f"\n--- Original text (first 600 chars) ---")
        print(text[:600])

        # Try reversing
        reversed_text = reverse_text(text)
        print(f"\n--- Reversed text (first 600 chars) ---")
        print(reversed_text[:600])

        # Check year patterns in original
        yr_pattern = r"\d{4}-\d{2}"
        yr_matches = re.findall(yr_pattern, text[:2000])
        print(f"\n--- Year matches (YYYY-YY) in original: {yr_matches}")

        # Check reversed year patterns
        rev_yr_pattern = r"\d{2}-\d{4}"
        rev_yr_matches = re.findall(rev_yr_pattern, text[:2000])
        print(f"--- Year matches (YY-YYYY) in original: {rev_yr_matches}")

        # Check year patterns in reversed text
        yr_in_rev = re.findall(yr_pattern, reversed_text[:2000])
        print(f"--- Year matches (YYYY-YY) in reversed: {yr_in_rev}")

        # Try pdfplumber table extraction
        print(f"\n--- pdfplumber extract_tables() ---")
        tables = page.extract_tables()
        if tables:
            for ti, table in enumerate(tables):
                print(f"\n  Table {ti}: {len(table)} rows")
                for ri, row in enumerate(table[:5]):
                    print(f"    Row {ri}: {row[:6]}")  # first 6 cells
        else:
            print("  No tables found by pdfplumber")

        # Check for reversed keywords
        gwp_keywords_rev = [
            "muimerp tcerid ssorg",
            "ssorg muimerp",
            "tcerid muimerp ssorg",
        ]
        text_lower = text.lower()
        for kw in gwp_keywords_rev:
            if kw in text_lower:
                print(f"\n--- Found reversed keyword: '{kw}'")


# Test 2018-19 GWP pages (219-220)
diagnose_page("Handbook_Insurance_Stats_2018-19.pdf", 219, "2018-19 GWP p1")
diagnose_page("Handbook_Insurance_Stats_2018-19.pdf", 220, "2018-19 GWP p2")

# Also test 2019-20
print("\n\n\n^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
print("TESTING 2019-20 PDF")
print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
with pdfplumber.open(HANDBOOK_DIR / "Handbook_Insurance_Stats_2019-20.pdf") as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    # Check if 2019-20 also has reversed text on relevant pages
    for pg in [219, 220, 221]:
        page = pdf.pages[pg - 1]
        text = page.extract_text() or ""
        rev_yr = re.findall(r"\d{2}-\d{4}", text[:2000])
        yr = re.findall(r"\d{4}-\d{2}", text[:2000])
        first_line = text[:200].replace("\n", " | ")
        print(
            f"  Page {pg}: YYYY-YY={yr[:5]}, YY-YYYY={rev_yr[:5]}, First: {first_line}"
        )

# Test 2010-11 and 2011-12
for fn in [
    "Handbook_Insurance_Stats_2010-11.pdf",
    "Handbook_Insurance_Stats_2011-12.pdf",
]:
    print(f"\n\n{'=' * 80}")
    print(f"Testing {fn}")
    print(f"{'=' * 80}")
    with pdfplumber.open(HANDBOOK_DIR / fn) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        # Scan for GWP pages
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            # Check for any table-identifying text
            if re.search(r"gross\s+direct\s+premium", text[:500], re.IGNORECASE):
                first_line = text[:200].replace("\n", " | ")
                print(f"  Page {i + 1} (GWP match): {first_line}")
            # Also look for non-life or general+health
            if re.search(
                r"table.*general.*health|gross.*premium.*general",
                text[:500],
                re.IGNORECASE,
            ):
                first_line = text[:200].replace("\n", " | ")
                print(f"  Page {i + 1} (general/health): {first_line}")
