"""Diagnostic script to explore PDF structure for problematic years."""

import pdfplumber
import re
from pathlib import Path

HANDBOOK_DIR = Path(
    "/Users/aviralsharma/Personal Projects/policy_data/_irdai_reference/data"
)


def examine_pdf(filename, label):
    path = HANDBOOK_DIR / filename
    if not path.exists():
        print(f"[{label}] File not found: {path}")
        return
    print(f"\n{'=' * 80}")
    print(f"[{label}] Examining {filename}")
    print(f"{'=' * 80}")
    with pdfplumber.open(path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")

        # Scan ALL pages for GWP-related keywords
        gwp_keywords = [
            "gross direct premium",
            "within & outside india",
            "gross direct premium of non-life",
            "premium income",
            "premium underwritten",
            "direct premium",
            "table no",
            "without reinsurance",
            "general insurance business",
            "segment-wise gross",
        ]

        print("\n--- Keyword matches (scanning ALL pages, first 500 chars) ---")
        for kw in gwp_keywords:
            matches = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if re.search(kw, text[:500], re.IGNORECASE):
                    matches.append(i + 1)
            if matches:
                print(
                    f"  '{kw}': pages {matches[:10]}{'...' if len(matches) > 10 else ''}"
                )

        # For 2018-19, also check what's on pages 434-456
        if "2018-19" in filename or "2019-20" in filename:
            print(f"\n--- Content of WRONG pages (434-456 for 2018-19) ---")
            for pg in range(433, min(456, len(pdf.pages))):
                page = pdf.pages[pg]
                text = page.extract_text() or ""
                first_line = text[:200].replace("\n", " | ")
                print(f"  Page {pg + 1}: {first_line}")

            # Find all table-of-contents-like entries to understand structure
            print(f"\n--- Pages mentioning 'Table' in first 300 chars ---")
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if re.search(r"table\s+\d+", text[:300], re.IGNORECASE):
                    first_line = text[:200].replace("\n", " | ")
                    print(f"  Page {i + 1}: {first_line}")

            # Search full page text for "gross" anywhere
            print(f"\n--- Pages containing 'gross direct premium' ANYWHERE in page ---")
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if re.search(r"gross\s+direct\s+premium", text, re.IGNORECASE):
                    first_line = text[:200].replace("\n", " | ")
                    print(f"  Page {i + 1}: {first_line}")

        # For 2010-11 / 2011-12, check pages 7-9 and 26
        if "2010-11" in filename or "2011-12" in filename:
            print(f"\n--- Content of pages 7-9 and 26 ---")
            for pg in [6, 7, 8, 25]:
                if pg < len(pdf.pages):
                    page = pdf.pages[pg]
                    text = page.extract_text() or ""
                    first_line = text[:300].replace("\n", " | ")
                    print(f"  Page {pg + 1}: {first_line}")

        # For 2018-19, look at table of contents page
        if "2018-19" in filename or "2019-20" in filename:
            print(f"\n--- Page 6 (Table of Contents) full text ---")
            if len(pdf.pages) > 5:
                page = pdf.pages[5]
                text = page.extract_text() or ""
                print(text[:2000])


# Run for all problematic years
examine_pdf("Handbook_Insurance_Stats_2018-19.pdf", "2018-19")
examine_pdf("Handbook_Insurance_Stats_2019-20.pdf", "2019-20")
examine_pdf("Handbook_Insurance_Stats_2010-11.pdf", "2010-11")
examine_pdf("Handbook_Insurance_Stats_2011-12.pdf", "2011-12")
examine_pdf("Handbook_Insurance_Stats_2007-08.pdf", "2007-08")
examine_pdf("Handbook_Insurance_Stats_2016-17.pdf", "2016-17")
