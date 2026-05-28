"""PDF Audit & Classification — classify all PDFs in policy_data/, prune non-policy files.

Outputs:
  - data/policy_index.json         — Classified index of all files
  - data/classification_report.json — Summary report
  - policy_data/_pruned/           — Moved non-policy files
"""

import os, json, re, sys, subprocess, shutil
from pathlib import Path
from datetime import datetime
from collections import Counter

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

BASE = Path("/Users/aviralsharma/Personal Projects/policy_data")
DATA_DIR = Path("/Users/aviralsharma/Personal Projects/insurance-agent/data")
UIN_LIFECYCLE_PATH = DATA_DIR / "uin_lifecycle.json"
OUTPUT_INDEX = DATA_DIR / "policy_index.json"
OUTPUT_REPORT = DATA_DIR / "classification_report.json"
PRUNE_DIR = BASE / "_pruned"

INSURER_MAP = {
    "01_New_India_Assurance": "New India Assurance",
    "02_Star_Health": "Star Health",
    "03_Care_Health": "Care Health",
    "04_ICICI_Lombard": "ICICI Lombard",
    "05_Niva_Bupa": "Niva Bupa",
    "06_United_India": "United India Insurance",
    "07_Oriental_Insurance": "Oriental Insurance",
    "08_Bajaj_Allianz": "Bajaj Allianz General Insurance",
    "09_HDFC_ERGO": "HDFC ERGO",
    "10_Tata_AIG": "Tata AIG General Insurance",
    "11_Aditya_Birla": "Aditya Birla Health Insurance",
    "12_IFFCO_Tokio": "IFFCO Tokio General Insurance",
    "13_Future_Generali": "Future Generali India Insurance",
    "14_Universal_Sompo": "Universal Sompo General Insurance",
    "15_Magma_HDI": "Magma HDI General Insurance",
    "16_Kotak_Mahindra": "Kotak Mahindra General Insurance",
    "17_Reliance": "Reliance General Insurance",
    "18_Cholamandalam": "Cholamandalam MS General Insurance",
    "19_Liberty": "Liberty General Insurance",
    "20_SBI_General": "SBI General Insurance",
    "21_Royal_Sundaram": "Royal Sundaram General Insurance",
    "22_Edelweiss": "Edelweiss General Insurance",
    "23_Raheja_QBE": "Raheja QBE General Insurance",
}

UIN_PATTERN = re.compile(
    r"(ICIHLIP|ICIHLGP|SHAHLIP|SHAHLGP|SHAHLIA|SHAHMIP|SHAHPAIP|SHAPAIP|"
    r"SHAPAGP|SHATIDP|SHATGDP|SHATGOP|SHAHGSP|"
    r"NIAHLIP|NIAHLGP|NBHHLIP|NBHHLGP|MAXHLIP|"
    r"UIIHLIP|UIIHLGP|UIIHCS|"
    r"OICHLIP|OICHLGP|BAJHLIP|BAJHLGP|"
    r"CHIHLIP|CHIHLIA|CHIHLGP|CHIHLGA|CHIHMGP|"
    r"CHIPAIP|CHIPAGP|CHITIOP|CHITIOA|CHITGBA|CHITGOA|"
    r"RHIHLIP|RHIHLIA|RHIHMGP|"
    r"HDFHLIP|HDFHLGP|HDFPAIP|HDHHLIP|HDHHLGP|"
    r"TATHLIP|TATHLGP|TATHLIA|ADIHLIP|ADIHLGP|ADIPAIP|"
    r"IFFHLIP|IFFHLGP|IFFHLIA|IFFHMGP|IFFHMIP|IFFPMIP|IFFPAGP|"
    r"FGIHLIP|FGIHLGP|"
    r"UNIHLIP|UNIHLGP|UNIPAIP|UNIPAGP|UNITGOP|"
    r"MAGHLIP|MAGHLGP|"
    r"KOTHLIP|KOTHLGP|KOTMHGP|ZUKHLGP|ZUKPAGP|ZUKPMGP|ZUKTGBP|ZUKTIOP|"
    r"RELHLIP|RELHLGP|LIBHLIP|LIBHLGP|LVGHLGP|LIBTGDP|"
    r"CHOHLIP|CHOHLGP|CHOPAGP|ICIPAIP|ICIPAGP|"
    r"SBIHLIP|SBIHLGP|SBIHMG|SBIHMI|SBIHIG|"
    r"RSAHLIP|RSAHLGP|RSAHMG|RSAHMI|RSAHMIP|RSAPAI|RSATIO|"
    r"RQBHLIP|RQBHLGP|RQBPAG|RQBPAGP|RQBPAI|RQBPAIP|RQBTIOP|"
    r"EDLHLGA|EDLHLGP|EDLHLIA|EDLHLIP|EDLPAG|EDLPAI|EDLPAIP|EDLTGO|"
    r"NAVIHLIP|GOIHLIP|NARHLIP|ACKHLIP)"
    r"\d{3,}(?:V?\d{2,})?"
)

OUTPUT_INDEX.parent.mkdir(parents=True, exist_ok=True)

# ── Load UIN lifecycle ──
uin_lifecycle = {}
uin_base_to_insurer = {}
if UIN_LIFECYCLE_PATH.exists():
    with open(UIN_LIFECYCLE_PATH) as f:
        ul = json.load(f)
    for uin_base, product in ul.get("products", {}).items():
        uin_base_to_insurer[uin_base] = product["insurer"]
        for v in product["versions"]:
            uin_lifecycle[v["uin"]] = {
                "insurer": product["insurer"],
                "product_name": product["product_name"],
                "version": v["version"],
                "status": v["status"],
                "uin_base": uin_base,
            }


def get_insurer_name(folder_name: str) -> str:
    return INSURER_MAP.get(folder_name, folder_name)


def get_pages_pdfinfo(filepath: Path) -> int:
    try:
        r = subprocess.run(
            ["pdfinfo", str(filepath)], capture_output=True, text=True, timeout=10
        )
        for line in r.stdout.splitlines():
            if "Pages" in line:
                return int(line.split(":")[1].strip())
    except Exception:
        pass
    return 0


def get_pages_pypdf(filepath: Path) -> int:
    try:
        reader = PdfReader(str(filepath))
        return len(reader.pages)
    except Exception:
        return 0


def extract_text_first_pages(filepath: Path, n: int = 3) -> str:
    if PdfReader is None:
        return ""
    try:
        reader = PdfReader(str(filepath))
        texts = []
        for i, page in enumerate(reader.pages):
            if i >= n:
                break
            t = page.extract_text() or ""
            texts.append(t)
        return "\n".join(texts)
    except Exception:
        return ""
    try:
        reader = PdfReader(str(filepath))
        texts = []
        for i, page in enumerate(reader.pages):
            if i >= n:
                break
            t = page.extract_text() or ""
            texts.append(t)
        result = "\n".join(texts)
        if not result.strip():
            print(
                f"  [DEBUG] extract_text_first_pages returned empty for {filepath.name}"
            )
        return result
    except Exception as e:
        print(f"  [DEBUG] extract_text_first_pages ERROR for {filepath.name}: {e}")
        return ""


def find_uin_in_text(text: str) -> str:
    m = UIN_PATTERN.search(text)
    if m:
        return m.group(0)
    return ""


def resolve_uin_status(uin: str) -> dict:
    """Look up a UIN in the lifecycle data and return status info."""
    if not uin:
        return {
            "status": None,
            "insurer": None,
            "version": None,
            "active_version": None,
        }
    # Try exact match first
    entry = uin_lifecycle.get(uin)
    if entry:
        product = uin_lifecycle.get(uin)
        # Check if newer version exists
        uin_base = entry["uin_base"]
        latest_version = 0
        for uin_key, e in uin_lifecycle.items():
            if e["uin_base"] == uin_base:
                latest_version = max(latest_version, e["version"])
        status = entry["status"]
        if status == "active" and entry["version"] < latest_version:
            status = "superseded"
        return {
            "status": status,
            "insurer": entry["insurer"],
            "version": entry["version"],
            "active_version": latest_version,
        }
    return {"status": None, "insurer": None, "version": None, "active_version": None}


def detect_source(filename: str, folder: str) -> str:
    fname_lower = filename.lower()
    if "irdai" in fname_lower:
        return "irdai"
    if (
        "_pw" in fname_lower
        or "policy_wording" in fname_lower
        or "policy wording" in fname_lower
    ):
        return "website_policy_wording"
    if "_kis" in fname_lower:
        return "website_kis"
    return "website"


def classify_file(filepath: Path, folder_name: str) -> dict:
    """Classify a single PDF file and return its entry dict."""
    fname = filepath.name
    fname_lower = fname.lower()
    size_kb = round(filepath.stat().st_size / 1024, 1)
    size_bytes = filepath.stat().st_size

    entry = {
        "folder": folder_name,
        "filename": fname,
        "path": str(filepath.relative_to(BASE)),
        "size_kb": size_kb,
        "size_bytes": size_bytes,
        "pages": 0,
        "uin": "",
        "source": detect_source(fname, folder_name),
        "category": None,
        "status": None,
        "is_canonical": False,
        "needs_prune": False,
        "prune_reason": None,
        "scanned_for_uin": False,
    }

    # Size check
    if size_bytes <= 51200:
        entry["category"] = "corrupt"
        entry["needs_prune"] = True
        entry["prune_reason"] = "file_size_less_than_50kb"
        return entry

    # Path-based classification
    if "circulars" in str(filepath).lower():
        entry["category"] = "circular"
        entry["source"] = "irdai"
        return entry
    if "regulations" in str(filepath).lower():
        entry["category"] = "circular"
        entry["source"] = "irdai"
        return entry
    if "reports" in str(filepath).lower():
        entry["category"] = "reference_data"
        entry["source"] = "irdai"
        return entry
    if "data" in str(filepath).lower() and "_irdai_reference" in str(filepath):
        entry["category"] = "reference_data"
        entry["source"] = "irdai"
        return entry

    # Filename keyword classification
    if any(
        kw in fname_lower
        for kw in [
            "brochure",
            "kis",
            "prospectus",
            "sales_literature",
            "sales literature",
        ]
    ):
        entry["category"] = "brochure"

    # Extract text for page count and UIN scanning
    pages = 0
    if PdfReader is not None:
        pages = get_pages_pypdf(filepath)
    else:
        pages = get_pages_pdfinfo(filepath)

    entry["pages"] = pages

    # Page count based classification
    if pages <= 3 and entry["category"] is None:
        if any(kw in fname_lower for kw in ["press", "pr_", "media", "news"]):
            entry["category"] = "press_release"
        else:
            entry["category"] = "brochure"

    # UIN scan
    text_first_pages = ""
    uin_found = ""
    if not entry.get("category") or entry["category"] in ("brochure", None):
        # Check filename first
        uin_found = find_uin_in_text(fname)
        # If not found, check text content
        if not uin_found:
            text_first_pages = extract_text_first_pages(filepath, 5)
            if text_first_pages:
                uin_found = find_uin_in_text(text_first_pages)
        entry["scanned_for_uin"] = True

    if uin_found:
        entry["uin"] = uin_found
        # Resolve status from UIN lifecycle
        status_info = resolve_uin_status(uin_found)
        entry["status"] = status_info["status"]

    # Finalize category
    if entry.get("category") is None:
        if uin_found:
            entry["category"] = "policy_wording"
        else:
            entry["category"] = "non_health"

    if entry["category"] == "brochure" and uin_found:
        entry["category"] = "brochure"

    # Prune decisions
    if entry["category"] in ("non_health", "corrupt"):
        entry["needs_prune"] = True
        entry["prune_reason"] = f"category_{entry['category']}"
    elif entry["category"] == "circular":
        # Keep circulars as reference, don't prune
        entry["needs_prune"] = False
    elif entry["category"] == "reference_data":
        entry["needs_prune"] = False
    elif entry["category"] == "policy_wording":
        entry["needs_prune"] = False

    return entry


def resolve_canonical(entries: list[dict]) -> list[dict]:
    """For files with the same UIN from different sources, mark one as canonical."""
    by_uin = {}
    for e in entries:
        uin = e.get("uin", "")
        if uin:
            by_uin.setdefault(uin, []).append(e)

    for uin, group in by_uin.items():
        sources = {e["source"] for e in group}
        if len(group) > 1 and "irdai" in sources:
            for e in group:
                e["is_canonical"] = e["source"] == "irdai"

    return entries


def scan_directory_structure() -> list[Path]:
    """Scan policy_data/ recursively and build list of all PDF files to classify."""
    files = []
    for entry in sorted(BASE.iterdir()):
        if not entry.is_dir():
            continue
        for f in sorted(entry.rglob("*.pdf")):
            files.append(f)
    return files


def format_size(sz: int) -> str:
    if sz < 1024:
        return f"{sz}B"
    elif sz < 1024 * 1024:
        return f"{sz / 1024:.1f}KB"
    else:
        return f"{sz / (1024 * 1024):.1f}MB"


def print_report(entries: list[dict], elapsed: str):
    """Print a rich classification report to terminal."""
    total = len(entries)
    cats = Counter(e["category"] for e in entries)
    statuses = Counter(e["status"] for e in entries if e.get("status"))
    sources = Counter(e["source"] for e in entries)
    pruned = [e for e in entries if e.get("needs_prune")]
    pruned_size = sum(e["size_bytes"] for e in pruned)
    with_uin = [e for e in entries if e.get("uin")]
    canonical = [e for e in entries if e.get("is_canonical")]

    print()
    print("=" * 70)
    print("CLASSIFICATION REPORT")
    print("=" * 70)
    print(f"  Total files:      {total}")
    print(f"  Time:             {elapsed}")
    print(f"  Total pages:      {sum(e['pages'] for e in entries)}")
    print(f"  Total size:       {format_size(sum(e['size_bytes'] for e in entries))}")
    print()
    print(f"  {'Category':<25s} {'Count':>6s}")
    print(f"  {'-' * 25} {'-' * 6}")
    for cat in sorted(cats.keys(), key=lambda c: -cats[c]):
        print(f"  {cat:<25s} {cats[cat]:>6d}")
    print()
    print(f"  {'Status':<25s} {'Count':>6s}")
    print(f"  {'-' * 25} {'-' * 6}")
    for st in sorted(statuses.keys(), key=lambda s: -statuses[s]):
        print(f"  {st:<25s} {statuses[st]:>6d}")
    print()
    print(f"  Files with UIN:   {len(with_uin)}")
    print(f"  Canonical (IRDAI source): {len(canonical)}")
    print(f"  To be pruned:     {len(pruned)} ({format_size(pruned_size)})")
    print()
    print(f"  {'Insurer':<40s} {'Files':>6s} {'Wording':>8s} {'Prune':>6s}")
    print(f"  {'-' * 40} {'-' * 6} {'-' * 8} {'-' * 6}")
    folder_counts = Counter(e["folder"] for e in entries)
    for folder in sorted(folder_counts.keys(), key=lambda f: -folder_counts[f]):
        total_n = folder_counts[folder]
        wordings = sum(
            1
            for e in entries
            if e["folder"] == folder and e["category"] == "policy_wording"
        )
        pruned_n = sum(
            1 for e in entries if e["folder"] == folder and e.get("needs_prune")
        )
        label = get_insurer_name(folder) if folder in INSURER_MAP else folder
        print(f"  {label:<40s} {total_n:>6d} {wordings:>8d} {pruned_n:>6d}")

    print()
    print(f"  Top 5 {pruned[0]['category'] if pruned else 'N/A'} files to prune:")
    for e in pruned[:5]:
        print(
            f"    - {e['path']} ({format_size(e['size_bytes'])}, {e['prune_reason']})"
        )
    if len(pruned) > 5:
        print(f"    ... and {len(pruned) - 5} more")
    print()


def main():
    t0 = datetime.now()
    # Limit to 50 files by default? No - process all.
    print("Scanning policy_data/ for PDF files...")
    all_files = scan_directory_structure()
    print(f"Found {len(all_files)} PDF files")

    entries = []
    for i, filepath in enumerate(all_files):
        folder_name = filepath.parent.name
        if (i + 1) % 100 == 0:
            print(f"  [{i + 1}/{len(all_files)}] classified...")
        entry = classify_file(filepath, folder_name)
        entries.append(entry)

    # Resolve canonical/alternate for duplicate UINs
    entries = resolve_canonical(entries)

    # Build report data
    cats = Counter(e["category"] for e in entries)
    statuses = Counter(e["status"] for e in entries if e.get("status"))
    pruned_list = [e for e in entries if e.get("needs_prune")]
    with_uin_list = [e for e in entries if e.get("uin")]
    canonical_list = [e for e in entries if e.get("is_canonical")]

    report = {
        "generated_at": datetime.now().isoformat(),
        "total_files": len(entries),
        "total_pages": sum(e["pages"] for e in entries),
        "total_bytes": sum(e["size_bytes"] for e in entries),
        "total_mb": round(sum(e["size_bytes"] for e in entries) / (1024 * 1024), 1),
        "categories": dict(cats),
        "statuses": dict(statuses),
        "files_with_uin": len(with_uin_list),
        "canonical_files": len(canonical_list),
        "to_be_pruned": len(pruned_list),
        "prune_size_mb": round(
            sum(e["size_bytes"] for e in pruned_list) / (1024 * 1024), 1
        ),
        "insurer_counts": {},
    }

    folder_counts = Counter(e["folder"] for e in entries)
    for folder in sorted(folder_counts.keys()):
        label = get_insurer_name(folder) if folder in INSURER_MAP else folder
        report["insurer_counts"][label] = folder_counts[folder]

    t1 = datetime.now()
    elapsed = str(t1 - t0).split(".")[0]

    print_report(entries, elapsed)

    OUTPUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_INDEX, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"Written: {OUTPUT_INDEX} ({len(entries)} entries)")

    with open(OUTPUT_REPORT, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Written: {OUTPUT_REPORT}")

    # ── Prune ──
    if pruned_list:
        print(f"\nPruning {len(pruned_list)} files to {PRUNE_DIR}...")
        PRUNE_DIR.mkdir(parents=True, exist_ok=True)
        moved = 0
        for e in pruned_list:
            src = BASE / e["path"]
            if not src.exists():
                continue
            dest = PRUNE_DIR / e["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            moved += 1
        print(f"Moved {moved} files to {PRUNE_DIR}")
    else:
        print("\nNothing to prune.")

    print(f"\nDone in {elapsed}")


if __name__ == "__main__":
    main()
