"""Diagnose the gap between Table 41 (page 197) and Table 54 (page 246) for 2018-19 PDF.
Also check 2016-17 for comparison (known working)."""

import pdfplumber
import re
from pathlib import Path

HANDBOOK_DIR = Path(
    "/Users/aviralsharma/Personal Projects/policy_data/_irdai_reference/data"
)


def examine_pages(filename, start, end, label):
    path = HANDBOOK_DIR / filename
    with pdfplumber.open(path) as pdf:
        print(f"\n{'=' * 80}")
        print(
            f"[{label}] Pages {start}-{end} (0-indexed: {start - 1}-{end - 1}) of {filename}"
        )
        print(f"{'=' * 80}")
        for pg in range(start - 1, min(end, len(pdf.pages))):
            page = pdf.pages[pg]
            text = page.extract_text() or ""
            # First 500 chars + any table references
            first_line = text[:400].replace("\n", " | ")
            table_match = re.search(
                r"(table\s+\d+[a-zA-Z]?)", text[:800], re.IGNORECASE
            )
            table_ref = f" [TABLE: {table_match.group(1)}]" if table_match else ""
            # Check if it mentions gross premium, GWP, etc in full text
            gwp_match = re.search(r"gross\s+(direct\s+)?premium", text, re.IGNORECASE)
            gwp_ref = " [HAS GROSS PREMIUM]" if gwp_match else ""
            print(f"  Page {pg + 1}:{table_ref}{gwp_ref} {first_line}")


# First see the gap in 2018-19
examine_pages("Handbook_Insurance_Stats_2018-19.pdf", 198, 250, "2018-19 Pages 198-250")

# Also check what 2016-17 looks like (known working)
print("\n\n")
examine_pages("Handbook_Insurance_Stats_2016-17.pdf", 1, 10, "2016-17 Pages 1-10")

# Find GWP-related pages in 2016-17
path = HANDBOOK_DIR / "Handbook_Insurance_Stats_2016-17.pdf"
with pdfplumber.open(path) as pdf:
    print(f"\n{'=' * 80}")
    print("[2016-17] ALL pages matching 'gross direct premium' or 'non-life'")
    print(f"{'=' * 80}")
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if re.search(r"gross\s+direct\s+premium|non.life", text[:500], re.IGNORECASE):
            first_line = text[:300].replace("\n", " | ")
            print(f"  Page {i + 1}: {first_line}")
