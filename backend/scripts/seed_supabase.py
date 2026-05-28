"""Seed Supabase from uin_lifecycle.json and policy_index.json.

Usage:
    .venv/bin/python backend/scripts/seed_supabase.py

Requires: SUPABASE_URL and SUPABASE_SERVICE_KEY in .env
"""

import os, json, re, sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

BASE = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE / "data"
LIFECYCLE_PATH = DATA_DIR / "uin_lifecycle.json"
POLICY_INDEX_PATH = DATA_DIR / "policy_index.json"

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

# Name -> folder reverse lookup
NAME_TO_FOLDER = {v: k for k, v in INSURER_MAP.items()}

# Known 3-letter codes derived from UIN prefixes
NAME_TO_CODE = {
    "Acko General Insurance": "ACK",
    "Aditya Birla Health Insurance": "ADI",
    "Apollo Munich Health Insurance": "APH",
    "Bajaj Allianz General Insurance": "BAJ",
    "Bharti AXA General Insurance": "BAX",
    "CIGNA TTK Health Insurance": "CIG",
    "Care Health": "CHI",
    "Cholamandalam MS General Insurance": "CHO",
    "DHFL General Insurance": "DHF",
    "Edelweiss General Insurance": "EDL",
    "Future Generali India Insurance": "FGI",
    "Go Digit General Insurance": "GOI",
    "HDFC ERGO": "HDF",
    "ICICI Lombard": "ICI",
    "IFFCO Tokio General Insurance": "IFF",
    "Kotak Mahindra General Insurance": "KOT",
    "Liberty General Insurance": "LIB",
    "Magma HDI General Insurance": "MAG",
    "National Insurance": "NAT",
    "Navi General Insurance": "NAV",
    "New India Assurance": "NIA",
    "Niva Bupa": "NBH",
    "Oriental Insurance": "OIC",
    "Raheja QBE General Insurance": "RQB",
    "Reliance General Insurance": "REL",
    "Royal Sundaram General Insurance": "RSA",
    "SBI General Insurance": "SBI",
    "Shriram General Insurance": "SHR",
    "Star Health": "SHA",
    "Tata AIG General Insurance": "TAT",
    "United India Insurance": "UII",
    "Universal Sompo General Insurance": "UNI",
}


def extract_uin_code(uin_base: str) -> str:
    """Extract 3-letter company code from a UIN base like 'BAJHLIP23020'."""
    m = re.match(r"([A-Z]{3})", uin_base)
    return m.group(1) if m else ""


def main():
    print("Loading lifecycle data...")
    with open(LIFECYCLE_PATH) as f:
        lifecycle = json.load(f)

    products_data = lifecycle.get("products", {})
    print(f"  {len(products_data)} UIN bases loaded")

    # Load policy index for pdf_path and source info
    policy_index = {}
    if POLICY_INDEX_PATH.exists():
        with open(POLICY_INDEX_PATH) as f:
            for e in json.load(f):
                if e.get("uin"):
                    policy_index.setdefault(e["uin"], []).append(e)

    # ── Connect to Supabase ──
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be in .env")
        sys.exit(1)

    supabase = create_client(url, key)
    print("Connected to Supabase")

    PAGE_SIZE = 1000

    # ── Step 1: Build all rows in memory ──
    print("\n── Building data rows ──")

    # Build insurer rows (deduplicate by code)
    insurer_rows_dict = {}
    for uin_base, product in products_data.items():
        name = product["insurer"]
        code = NAME_TO_CODE.get(name) or extract_uin_code(uin_base)
        if not code or code in insurer_rows_dict:
            continue
        folder = NAME_TO_FOLDER.get(name)
        insurer_rows_dict[code] = {"code": code, "name": name, "folder_name": folder}
    insurer_rows = list(insurer_rows_dict.values())
    print(f"  Insurer rows: {len(insurer_rows)}")

    # Fetch existing insurers
    existing_insurers = {}
    for row in supabase.table("insurers").select("code, id").execute().data:
        existing_insurers[row["code"]] = row["id"]

    # Separate new vs existing
    new_insurers = [r for r in insurer_rows if r["code"] not in existing_insurers]
    if new_insurers:
        result = supabase.table("insurers").insert(new_insurers).execute()
        for r in result.data:
            existing_insurers[r["code"]] = r["id"]
        print(f"  Inserted {len(new_insurers)} insurers")

    # Build product rows (handle pagination)
    all_products_data = []
    offset = 0
    while True:
        batch = (
            supabase.table("products")
            .select("uin_base, id")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        if not batch.data:
            break
        all_products_data.extend(batch.data)
        offset += PAGE_SIZE
        if len(batch.data) < PAGE_SIZE:
            break
    existing_products = {p["uin_base"]: p["id"] for p in all_products_data}
    new_products = []
    for uin_base, product in products_data.items():
        if uin_base in existing_products:
            continue
        code = NAME_TO_CODE.get(product["insurer"]) or extract_uin_code(uin_base)
        insurer_id = existing_insurers.get(code)
        if not insurer_id:
            continue
        new_products.append(
            {
                "uin_base": uin_base,
                "insurer_id": insurer_id,
                "product_name": product["product_name"],
                "line_of_business": "health",
                "product_type": product.get("product_type"),
            }
        )

    if new_products:
        # Batch insert in chunks of 100
        for i in range(0, len(new_products), 100):
            chunk = new_products[i : i + 100]
            supabase.table("products").insert(chunk).execute()
        # Refresh map (handle pagination)
        all_refreshed = []
        offset = 0
        while True:
            batch = (
                supabase.table("products")
                .select("uin_base, id")
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
            )
            if not batch.data:
                break
            all_refreshed.extend(batch.data)
            offset += PAGE_SIZE
            if len(batch.data) < PAGE_SIZE:
                break
        for p in all_refreshed:
            existing_products[p["uin_base"]] = p["id"]
        print(f"  Inserted {len(new_products)} products")

    # Build product_version rows (handle pagination — Supabase REST returns max 1000)
    all_existing = []
    PAGE_SIZE = 1000
    offset = 0
    while True:
        batch = (
            supabase.table("product_versions")
            .select("uin")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        if not batch.data:
            break
        all_existing.extend(batch.data)
        offset += PAGE_SIZE
        if len(batch.data) < PAGE_SIZE:
            break
    existing_uins = {v["uin"] for v in all_existing}
    new_versions = []
    for uin_base, product in products_data.items():
        product_id = existing_products.get(uin_base)
        if not product_id:
            continue
        for version in product["versions"]:
            uin = version["uin"]
            if uin in existing_uins:
                continue
            irdai_path = None
            website_path = None
            is_canonical = False
            page_count = None
            file_size = None
            for entry in policy_index.get(uin, []):
                source = entry.get("source", "")
                path = entry.get("path", "")
                if source == "irdai":
                    irdai_path = path
                    is_canonical = True
                elif "website" in source:
                    website_path = path
                if not file_size and entry.get("size_bytes"):
                    file_size = entry["size_bytes"]
                if not page_count and entry.get("pages"):
                    page_count = entry["pages"]
            new_versions.append(
                {
                    "product_id": product_id,
                    "uin": uin,
                    "version": version["version"],
                    "status": version["status"],
                    "irdai_source_path": irdai_path,
                    "website_source_path": website_path,
                    "is_canonical": is_canonical,
                    "page_count": page_count,
                    "file_size_bytes": file_size,
                }
            )

    if new_versions:
        # Deduplicate by UIN (lifecycle data has 13 duplicate UINs across bases)
        seen_uins = set(existing_uins)
        deduped = []
        for v in new_versions:
            if v["uin"] not in seen_uins:
                seen_uins.add(v["uin"])
                deduped.append(v)
        for i in range(0, len(deduped), 100):
            chunk = deduped[i : i + 100]
            supabase.table("product_versions").insert(chunk).execute()
        print(
            f"  Inserted {len(deduped)} product versions ({len(new_versions) - len(deduped)} duplicates skipped)"
        )

    # ── Summary ──
    print("\n═══ Seed Summary ═══")
    for table in ["insurers", "products", "product_versions"]:
        r = supabase.table(table).select("*", count="exact").execute()
        print(f"  {table}: {r.count} rows")

    print("\nDone.")


if __name__ == "__main__":
    main()
