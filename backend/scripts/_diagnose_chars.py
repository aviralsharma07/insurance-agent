"""Test character-level extraction and alternative text extraction approaches."""

import pdfplumber
from collections import defaultdict
from pathlib import Path

HANDBOOK_DIR = Path(
    "/Users/aviralsharma/Personal Projects/policy_data/_irdai_reference/data"
)


def test_char_extraction(filename, page_num):
    path = HANDBOOK_DIR / filename
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_num - 1]

        # Method 1: Default extract_text()
        text1 = page.extract_text() or ""

        # Method 2: Extract words (position-aware)
        words = page.extract_words(keep_blank_chars=True, x_tolerance=3)

        # Method 3: Use chars sorted by (top, x0) to reconstruct natural order
        chars = page.chars
        # Group chars by vertical position (within tolerance)
        lines = defaultdict(list)
        for c in chars:
            y_key = round(c["top"], 0)  # round to nearest pixel
            lines[y_key].append(c)

        # Sort lines by y, and chars within each line by x0
        reconstructed_lines = []
        for y in sorted(lines.keys()):
            line_chars = sorted(lines[y], key=lambda c: c["x0"])
            line_text = "".join(c["text"] for c in line_chars)
            reconstructed_lines.append(line_text)

        reconstructed = "\n".join(reconstructed_lines)

        print(f"\n{'=' * 80}")
        print(f"[{filename}] Page {page_num} - Character-position-reconstructed text")
        print(f"{'=' * 80}")
        for i, line in enumerate(reconstructed_lines[:60]):
            print(f"  {line}")

        # Check for year patterns in reconstructed text
        import re

        yr = re.findall(r"\d{4}-\d{2}", reconstructed[:3000])
        rev_yr = re.findall(r"\d{2}-\d{4}", reconstructed[:3000])
        print(f"\n--- YYYY-YY patterns: {yr[:10]}")
        print(f"--- YY-YYYY patterns: {rev_yr[:10]}")

        # Check for keywords
        if "gross direct premium" in reconstructed.lower()[:2000]:
            print("--- FOUND 'gross direct premium' in reconstructed text!")
        if "gross" in reconstructed.lower()[:2000]:
            print("--- FOUND 'gross' in reconstructed text!")

        # Also try extract_text with different settings
        text2 = page.extract_text(x_tolerance=1)
        print(f"\n--- extract_text(x_tolerance=1) sampling:")
        print(text2[:500])


# Test on 2018-19 page 219
test_char_extraction("Handbook_Insurance_Stats_2018-19.pdf", 219)

# Also check 2019-20 page 219
test_char_extraction("Handbook_Insurance_Stats_2019-20.pdf", 219)
