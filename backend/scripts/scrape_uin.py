"""Scrape IRDAI health products listing for UIN lifecycle data.

IRDAI intranet (per-insurer XLSX) is behind firewall (403).
Fallback: public health products listing page on irdai.gov.in.

Output: data/uin_lifecycle.json
"""

import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

BASE_URL = "https://irdai.gov.in/health-insurance-products"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}
ITEMS_PER_PAGE = 100
MAX_PAGES = 19
OUTPUT_PATH = Path("data/uin_lifecycle.json")
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def make_params(page: int, delta: int = ITEMS_PER_PAGE) -> dict:
    portlet = "com_irdai_document_media_IRDAIDocumentMediaPortlet"
    return {
        f"_{portlet}_cur": page,
        f"_{portlet}_delta": delta,
        "p_p_id": portlet,
        "p_p_lifecycle": 0,
        "p_p_mode": "view",
        "p_p_state": "normal",
    }


def clean_cell(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def parse_table_rows(html: str) -> list[dict]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    records = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 8:
            continue
        uin = clean_cell(cells[4])
        if not uin or not re.match(r"^[A-Z0-9]{3,}V\d{2}", uin):
            continue
        records.append(
            {
                "uin": uin,
                "insurer": clean_cell(cells[3]),
                "product_name": clean_cell(cells[5]),
                "approval_date": clean_cell(cells[6]),
                "product_type": clean_cell(cells[8]),
                "financial_year": clean_cell(cells[2]),
                "archive_status": clean_cell(cells[1]),
            }
        )
    return records


def fetch_page(page: int) -> Optional[str]:
    for attempt in range(3):
        try:
            resp = httpx.get(
                BASE_URL,
                params=make_params(page),
                headers=HEADERS,
                timeout=60,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as e:
            if attempt < 2:
                time.sleep(2)
                continue
            print(f"  Failed page {page} after 3 attempts: {e}")
    return None


def estimate_pages(first_html: str) -> int:
    match = re.search(r"of\s+([\d,]+)\s+results", first_html)
    if match:
        total = int(match.group(1).replace(",", ""))
        return max(1, math.ceil(total / ITEMS_PER_PAGE))
    return MAX_PAGES


def build_lifecycle(records: list[dict]) -> dict:
    products = {}
    for r in records:
        uin = r["uin"]
        base = re.sub(r"V\d{2}\d{4}$", "", uin)
        vm = re.search(r"V(\d{2})", uin)
        ver = int(vm.group(1)) if vm else 0
        if base not in products:
            products[base] = {
                "uin_base": base,
                "insurer": r["insurer"],
                "product_name": r["product_name"],
                "product_type": r["product_type"],
                "versions": [],
            }
        products[base]["versions"].append(
            {
                "uin": uin,
                "version": ver,
                "approval_date": r["approval_date"],
                "financial_year": r["financial_year"],
                "status": "pending",
            }
        )
    for p in products.values():
        p["versions"].sort(key=lambda v: v["version"], reverse=True)
        if p["versions"]:
            p["versions"][0]["status"] = "active"
            for v in p["versions"][1:]:
                v["status"] = "superseded"
    return products


def main():
    print("Fetching page 1...")
    first_html = fetch_page(1)
    if not first_html:
        print("FAILED: could not fetch first page")
        return

    total_pages = estimate_pages(first_html)
    print(f"Estimated pages: {total_pages}")

    all_records = parse_table_rows(first_html)
    print(f"Page 1: {len(parse_table_rows(first_html))} records")

    for page in range(2, total_pages + 1):
        html = fetch_page(page)
        if html:
            records = parse_table_rows(html)
            all_records.extend(records)
        print(f"Page {page}/{total_pages}: {len(records) if html else 0} records")
        time.sleep(1)

    print(f"\nTotal records scraped: {len(all_records)}")
    products = build_lifecycle(all_records)

    output = {
        "generated_at": datetime.now().isoformat(),
        "source": "irdai_health_products_listing",
        "total_records": len(all_records),
        "total_uin_bases": len(products),
        "insurers": sorted(set(r["insurer"] for r in all_records)),
        "products": products,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Written to {OUTPUT_PATH}")
    print(f"Unique UIN bases: {len(products)}")
    print(f"Unique insurers: {len(output['insurers'])}")
    active = sum(
        1
        for p in products.values()
        if any(v["status"] == "active" for v in p["versions"])
    )
    print(f"Active products: {active}")


if __name__ == "__main__":
    main()
