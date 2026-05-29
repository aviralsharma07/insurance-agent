"""Convert 4 test PDFs to Markdown using Docling.

Saves each .md to data/docling_markdown/ and creates REFERENCE.md.

Usage:
    .venv/bin/python backend/scripts/docling_convert.py
"""

import time, sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent.parent
PDF_BASE = Path("/Users/aviralsharma/Personal Projects/policy_data")
OUT_DIR = BASE / "data" / "docling_markdown"

TEST_PDFS = [
    (
        "01_New_India_Assurance",
        "NewIndia_Floater_Mediclaim_IRDAI.pdf",
        "NIAHLIP21278V042021",
        "33 pages",
    ),
    (
        "02_Star_Health",
        "Star_Policy_POS_Accident_Care_Individual_Insurance_Policy.pdf",
        "SHAHPAIP18070V031718",
        "19 pages",
    ),
    (
        "09_HDFC_ERGO",
        "HDFC_ERGO_Arogya_Sanjeevani_Policy_HDFC_ERGO.pdf",
        "HDFHLIP20175V011920",
        "39 pages",
    ),
    (
        "04_ICICI_Lombard",
        "ICICI_Family_Shield_IRDAI.pdf",
        "ICIHLIP22092V032122",
        "60 pages",
    ),
]


def convert_one(pdf_path: Path, out_path: Path) -> dict:
    result = {"status": "ok", "elapsed_s": 0, "chars": 0, "error": None}
    t0 = time.perf_counter()
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        doc_result = converter.convert(pdf_path)
        doc = doc_result.document
        md = doc.export_to_markdown()
        elapsed = time.perf_counter() - t0
        result["elapsed_s"] = round(elapsed, 1)
        result["chars"] = len(md)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            f.write(md)
        return result
    except Exception as e:
        elapsed = time.perf_counter() - t0
        result["status"] = "fail"
        result["error"] = str(e)
        result["elapsed_s"] = round(elapsed, 1)
        return result


def main():
    print("=" * 70)
    print("  DOCLING PDF → MARKDOWN CONVERSION")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    ref_lines = [
        "# Docling Markdown Reference",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Source PDFs: /Users/aviralsharma/Personal Projects/policy_data/{{folder}}/{{filename}}",
        f"Output: data/docling_markdown/{{folder}}/{{filename}}.md",
        "",
        "| # | Insurer | Product | UIN | Pages | PDF Path | Markdown Path | Status | Chars | Time |",
        "|---|---------|---------|-----|-------|----------|---------------|--------|-------|------|",
    ]
    results = []

    for i, (folder, fname, uin, pages) in enumerate(TEST_PDFS, 1):
        pdf_path = PDF_BASE / folder / fname
        out_path = OUT_DIR / folder / f"{fname}.md"
        label = f"[{i}/{len(TEST_PDFS)}] {folder}/{fname}"

        print(f"\n{'─' * 60}")
        print(f"  {label}")
        print(f"  UIN: {uin} | {pages}")
        print(f"  PDF: {pdf_path}")
        print(f"{'─' * 60}")

        if not pdf_path.exists():
            print(f"  ✗ FILE NOT FOUND - skipping")
            results.append(
                (
                    folder,
                    fname,
                    uin,
                    pages,
                    str(pdf_path),
                    str(out_path),
                    "FILE NOT FOUND",
                    "-",
                    "-",
                )
            )
            continue

        print(f"  Converting...", end=" ", flush=True)
        res = convert_one(pdf_path, out_path)

        if res["status"] == "ok":
            print(f"✓ {res['elapsed_s']}s, {res['chars']:,} chars → {out_path}")
        else:
            print(f"✗ FAILED after {res['elapsed_s']}s: {res['error']}")

        results.append(
            (
                folder,
                fname,
                uin,
                pages,
                str(pdf_path),
                str(out_path),
                "✓" if res["status"] == "ok" else "✗",
                f"{res['chars']:,}" if res["status"] == "ok" else "-",
                f"{res['elapsed_s']}s" if res["status"] == "ok" else "-",
            )
        )

    for r in results:
        ref_lines.append(
            f"| {results.index(r) + 1} | {r[0]} | {r[1]} | {r[2]} | {r[3]} | `{r[4]}` | `{r[5]}` | {r[6]} | {r[7]} | {r[8]} |"
        )

    ref_path = OUT_DIR / "REFERENCE.md"
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ref_path, "w") as f:
        f.write("\n".join(ref_lines) + "\n")

    print(f"\n{'=' * 70}")
    print(f"  SUMMARY")
    print(f"{'=' * 70}")
    ok = sum(1 for r in results if r[6] == "✓")
    print(f"  {ok}/{len(results)} converted successfully")
    print(f"  Reference: {ref_path}")
    print(f"  Output:    {OUT_DIR}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
