"""Test word-level extraction for handling reversed PDF text."""

import pdfplumber
from collections import defaultdict
from pathlib import Path

HANDBOOK_DIR = Path(
    "/Users/aviralsharma/Personal Projects/policy_data/_irdai_reference/data"
)


def extract_lines_from_words(words, tolerance=5):
    """Group words by vertical position into lines."""
    lines = defaultdict(list)
    for w in words:
        y_key = round(w["top"] / tolerance) * tolerance
        lines[y_key].append(w)

    result = []
    for y in sorted(lines.keys()):
        line_words = sorted(lines[y], key=lambda w: w["x0"])
        line_text = " ".join(w["text"] for w in line_words)
        result.append((y, line_text, line_words))
    return result


def diagnose_page_words(filename, page_num, label):
    path = HANDBOOK_DIR / filename
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_num - 1]

        words = page.extract_words(keep_blank_chars=True, x_tolerance=3)

        print(f"\n{'=' * 80}")
        print(f"[{label}] Page {page_num} - Word-level extraction")
        print(f"{'=' * 80}")
        print(f"Total words extracted: {len(words)}")

        # Group into lines
        lines = extract_lines_from_words(words)
        print(f"\n--- Lines (grouped by y-position) ---")
        for y, line_text, _ in lines[:30]:
            print(f"  y={y:6.0f}: {line_text}")

        # Check for year patterns
        import re

        all_text = "\n".join(t for _, t, _ in lines)
        yr = re.findall(r"\d{4}-\d{2}", all_text)
        rev_yr = re.findall(r"\d{2}-\d{4}", all_text)
        print(f"\n--- YYYY-YY patterns: {yr[:10]}")
        print(f"--- YY-YYYY patterns: {rev_yr[:10]}")

        # Check if words are in correct reading order by looking at x0 values
        print(f"\n--- Sample word x0 values (first data line) ---")
        for y, line_text, line_words in lines:
            if any(c.isdigit() for c in line_text) and len(line_words) > 3:
                for w in line_words[:10]:
                    print(f"    x0={w['x0']:6.0f} text='{w['text']}'")
                break

        # Try extract_words() with different settings
        words2 = page.extract_words(keep_blank_chars=True, x_tolerance=1)
        lines2 = extract_lines_from_words(words2)
        print(f"\n--- Lines with x_tolerance=1 (first 10) ---")
        for y, line_text, _ in lines2[:10]:
            print(f"  y={y:6.0f}: {line_text}")


# Test 2018-19 GWP page
diagnose_page_words("Handbook_Insurance_Stats_2018-19.pdf", 219, "2018-19 GWP")

# Test a working year for comparison
diagnose_page_words("Handbook_Insurance_Stats_2016-17.pdf", 182, "2016-17 GWP")

# Test 2010-11 GWP pages (Table 40 on page 158)
diagnose_page_words("Handbook_Insurance_Stats_2010-11.pdf", 158, "2010-11 GWP Table 40")
diagnose_page_words("Handbook_Insurance_Stats_2010-11.pdf", 159, "2010-11 Table 41")
