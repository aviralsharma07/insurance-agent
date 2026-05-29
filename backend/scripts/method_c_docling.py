"""Method C: Docling -> Markdown -> Gemini 2.5 Flash extraction.

Adds Method C results to the existing extraction_comparison_results.json.

Usage:
    .venv/bin/python backend/scripts/method_c_docling.py 2>&1 | tee logs/docling_extraction.log
"""

import json, os, sys, time, re, random
from pathlib import Path
from datetime import datetime
from typing import Optional
import hashlib

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

BASE = Path(__file__).resolve().parent.parent.parent
PDF_BASE = Path("/Users/aviralsharma/Personal Projects/policy_data")
CACHE_DIR = BASE / "data" / "docling_cache"

sys.path.insert(0, str(BASE))
from backend.models.policy_features import PolicyFeatures

GEMINI_MODEL = "gemini-2.5-flash"
PROMPT_VERSION = "v1.0-test"

EXTRACTION_PROMPT = """Extract structured insurance policy features from this Indian health insurance policy document.

You must output valid JSON matching the provided schema exactly. Follow these rules strictly:

1. Extract ONLY information explicitly stated in the document — do not infer or guess
2. Use null for fields not found anywhere in the document
3. Pay special attention to TABLES, schedules, appendices, fine print, and footnotes — tables contain most of the critical data (sum insured options, room rent tiers, waiting period schedules, sub-limits, exclusions)
4. For arrays (exclusions, sub-limits, disease lists, general_exclusions, permanent_exclusions, waiting_period_exclusions), extract ALL items found — do not summarize or truncate
5. For monetary values, include the currency symbol when present
6. Read ALL sections of the document before producing output — do not stop at the first page

Key sections to examine in order:
- Policy Schedule / Policy Wordings (product_name, uin, sum insured, term, eligibility)
- Schedule of Benefits (room rent, ICU, domiciliary, co-pay, deductibles — look for tiered tables)
- Waiting Period Section / Schedule of Waiting Periods (disease-wise table — extract ALL diseases with their waiting periods)
- Maternity Benefit Section (waiting period, limits, newborn cover, delivery types)
- Table of Sub-limits / Specific Procedure Limits (extract ALL items — room rent sub-limits, disease sub-limits, surgical limits)
- Exclusions / General Exclusions (extract ALL items — permanent, waiting period, and general. Usually a long numbered list.)
- No Claim Bonus / Cumulative Bonus / Restoration Benefit (check for multiple rows/options)
- Portability Clause
- Free Look Period, Grace Period, Cancellation terms
- Claim Procedure / Intimation Requirements
- Additional Covers (AYUSH, OPD, health checkup, wellness, modern treatments)
"""

TEST_PDFS = [
    (
        "01_New_India_Assurance",
        "NewIndia_Floater_Mediclaim_IRDAI.pdf",
        "NIAHLIP21278V042021",
    ),
    (
        "02_Star_Health",
        "Star_Policy_POS_Accident_Care_Individual_Insurance_Policy.pdf",
        "SHAHPAIP18070V031718",
    ),
    (
        "09_HDFC_ERGO",
        "HDFC_ERGO_Arogya_Sanjeevani_Policy_HDFC_ERGO.pdf",
        "HDFHLIP20175V011920",
    ),
    ("04_ICICI_Lombard", "ICICI_Family_Shield_IRDAI.pdf", "ICIHLIP22092V032122"),
    ("03_Care_Health", "Care_Arogya_Sanjeevani_Older_IRDAI.pdf", "RHIHLIP20154V011920"),
    (
        "18_Cholamandalam",
        "Cholamandalam_ArogyaSanjeevani_PolicyChola_MS.pdf",
        "CHOHLIP20153V011920",
    ),
    ("10_Tata_AIG", "Tata_AIG_Arogya_Sanjeevani.pdf", "TATHLIP20169V011920"),
    (
        "14_Universal_Sompo",
        "Universal_Sompo_ArogyaSanjeevani_PolicyUniversal_Sompo_General_Insurance_Company.pdf",
        "UNIHLIP20171V011920",
    ),
]


# --- Field counting ---


def _count_model_fields(model_cls, model_instance):
    populated = 0
    total = 0
    for fn in model_cls.model_fields:
        fv = getattr(model_instance, fn)
        total += 1
        if fv is not None:
            if hasattr(type(fv), "model_fields") and type(fv) is not type(None):
                p, t = _count_model_fields(type(fv), fv)
                populated += p
                total += t
            elif isinstance(fv, list):
                if len(fv) > 0:
                    populated += 1
            else:
                populated += 1
    return populated, total


def count_populated(features: PolicyFeatures):
    if features is None:
        return 0, 0
    return _count_model_fields(PolicyFeatures, features)


# --- Retry ---


def with_retry(fn, max_retries=5, base_delay=5):
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            err_str = str(e)
            is_503 = "503" in err_str or "UNAVAILABLE" in err_str
            is_429 = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
            if (is_503 or is_429) and attempt < max_retries - 1:
                delay_match = re.search(r"retryDelay['\"]:\s*'(\d+)s'", err_str)
                if delay_match:
                    delay = int(delay_match.group(1)) + random.uniform(0, 2)
                else:
                    delay = base_delay * (2**attempt) + random.uniform(0, 2)
                print(
                    f"    [RETRY {attempt + 1}/{max_retries}] waiting {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                raise
    return fn()


# --- Docling conversion ---


def pdf_to_markdown(pdf_path: Path) -> Optional[str]:
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        doc = result.document
        return doc.export_to_markdown()
    except Exception as e:
        print(f"    [DOCLING ERROR] {e}")
        return None


def get_cached_markdown(pdf_path: Path, force: bool = False) -> Optional[str]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stat = pdf_path.stat()
    cache_key = f"{pdf_path.name}_{stat.st_size}_{int(stat.st_mtime)}"
    cache_file = CACHE_DIR / f"{hashlib.md5(cache_key.encode()).hexdigest()}.md"

    if cache_file.exists() and not force:
        with open(cache_file) as f:
            return f.read()

    print(f"    [DOCLING] Converting to markdown...")
    t0 = time.perf_counter()
    md = pdf_to_markdown(pdf_path)
    elapsed = time.perf_counter() - t0
    if md:
        with open(cache_file, "w") as f:
            f.write(md)
        print(f"    [DOCLING] Done in {elapsed:.0f}s, {len(md)} chars -> cached")
    return md


# --- Method C: Docling -> Gemini ---


def method_c_docling(client, pdf_path: Path) -> dict:
    result = {
        "success": False,
        "input_tokens": 0,
        "output_tokens": 0,
        "api_calls": 0,
        "latency_ms": 0,
        "features": None,
        "error": None,
        "markdown_chars": 0,
        "docling_time_s": 0,
    }
    t0 = time.perf_counter()

    try:
        t1 = time.perf_counter()
        md = get_cached_markdown(pdf_path)
        t2 = time.perf_counter()
        result["docling_time_s"] = round(t2 - t1, 1)
        if not md:
            result["error"] = "Docling conversion failed"
            return result

        result["markdown_chars"] = len(md)

        if len(md) > 950000:
            print(f"    [TRUNCATE] Markdown {len(md)} chars > 950K limit")
            md = md[:950000] + "\n\n[CONTENT TRUNCATED]"

        response = with_retry(
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[md, EXTRACTION_PROMPT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=PolicyFeatures,
                ),
            )
        )
        result["api_calls"] += 1

        if response.usage_metadata:
            result["input_tokens"] = (
                getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            )
            result["output_tokens"] = (
                getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            )

        if response.parsed:
            result["features"] = response.parsed
            result["success"] = True
        elif response.text:
            result["features"] = PolicyFeatures.model_validate_json(response.text)
            result["success"] = True
        else:
            result["error"] = "Empty response"

    except Exception as e:
        result["error"] = str(e)
        print(f"    [FAIL] Method C: {e}")

    result["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


# --- Helpers ---


def _summarize(val) -> str:
    if val is None:
        return "null"
    if isinstance(val, str):
        return val[:80] + "..." if len(val) > 80 else val
    if isinstance(val, (bool, int, float)):
        return str(val)
    if isinstance(val, list):
        if not val:
            return "[]"
        if len(val) <= 3:
            items = [_summarize(v) for v in val]
            return "[" + ", ".join(items) + "]"
        return f"[{_summarize(val[0])} ... +{len(val) - 1}]"
    if hasattr(val, "model_dump"):
        d = val.model_dump(exclude_none=True)
        items = list(d.items())
        if len(items) <= 5:
            return json.dumps(d, ensure_ascii=False)
        return (
            json.dumps(dict(items[:5]), ensure_ascii=False)
            + f" ... +{len(items) - 5} fields"
        )
    return str(val)[:80]


def features_to_dict(features):
    if features is None:
        return {}
    try:
        return json.loads(features.model_dump_json(exclude_none=True))
    except Exception:
        return {}


def reconstruct_features(fd: dict) -> Optional[PolicyFeatures]:
    if not fd:
        return None
    try:
        return PolicyFeatures.model_validate(fd)
    except Exception:
        return None


def three_way_compare(feat_a, feat_b, feat_c) -> dict:
    diff_report = []

    def _compare_three(a_val, b_val, c_val, path):
        has_a = a_val is not None
        has_b = b_val is not None
        has_c = c_val is not None
        if not has_a and not has_b and not has_c:
            return "all_null"
        if has_a and not has_b and not has_c:
            return "a_only"
        if not has_a and has_b and not has_c:
            return "b_only"
        if not has_a and not has_b and has_c:
            return "c_only"
        a_s = _summarize(a_val)
        b_s = _summarize(b_val)
        c_s = _summarize(c_val)
        if a_s == b_s == c_s:
            return "all_match"
        all_vals = {a_s, b_s, c_s}
        if len(all_vals) == 2:
            if a_s == b_s:
                return "ab_match_c_diff"
            if a_s == c_s:
                return "ac_match_b_diff"
            if b_s == c_s:
                return "bc_match_a_diff"
        return "all_diff"

    def _walk(a_val, b_val, c_val, path):
        if (
            isinstance(a_val, BaseModel)
            and isinstance(b_val, BaseModel)
            and isinstance(c_val, BaseModel)
        ):
            cls = type(a_val)
            for sub_fn in cls.model_fields:
                _walk(
                    getattr(a_val, sub_fn, None),
                    getattr(b_val, sub_fn, None),
                    getattr(c_val, sub_fn, None),
                    f"{path}.{sub_fn}",
                )
        elif (
            isinstance(a_val, list)
            and isinstance(b_val, list)
            and isinstance(c_val, list)
        ):
            s = _compare_three(a_val, b_val, c_val, path)
            if s != "all_match" and s != "all_null":
                diff_report.append(
                    {
                        "field": path,
                        "status": s,
                        "a": _summarize(a_val) if a_val else None,
                        "b": _summarize(b_val) if b_val else None,
                        "c": _summarize(c_val) if c_val else None,
                    }
                )
        else:
            s = _compare_three(a_val, b_val, c_val, path)
            if s != "all_match" and s != "all_null":
                diff_report.append(
                    {
                        "field": path,
                        "status": s,
                        "a": _summarize(a_val) if a_val is not None else None,
                        "b": _summarize(b_val) if b_val is not None else None,
                        "c": _summarize(c_val) if c_val is not None else None,
                    }
                )

    a = feat_a or PolicyFeatures()
    b = feat_b or PolicyFeatures()
    c_ = feat_c or PolicyFeatures()

    for fn in PolicyFeatures.model_fields:
        _walk(getattr(a, fn), getattr(b, fn), getattr(c_, fn), fn)

    counts = {
        "all_match": 0,
        "all_null": 0,
        "a_only": 0,
        "b_only": 0,
        "c_only": 0,
        "ab_match_c_diff": 0,
        "ac_match_b_diff": 0,
        "bc_match_a_diff": 0,
        "all_diff": 0,
    }
    for d in diff_report:
        s = d["status"]
        if s in counts:
            counts[s] += 1

    return {"counts": counts, "diffs": diff_report}


# --- Main ---


def make_skip_key(folder, fname):
    return f"{folder}/{fname}"


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set in .env")
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    out_path = BASE / "data" / "extraction_comparison_results.json"
    if not out_path.exists():
        print(f"ERROR: Results file not found at {out_path}")
        sys.exit(1)

    with open(out_path) as f:
        all_results = json.load(f)

    # Determine which PDFs have A & B and need C
    to_process = []
    for folder, fname, expected_uin in TEST_PDFS:
        key = make_skip_key(folder, fname)
        existing = None
        for r in all_results:
            if make_skip_key(r.get("folder", ""), r.get("filename", "")) == key:
                existing = r
                break
        if not existing:
            print(f"  [SKIP] {key} - no A/B results yet")
            continue
        if existing.get("method_c", {}).get("success"):
            print(f"  [SKIP] {key} - Method C already done")
            continue
        to_process.append((folder, fname, expected_uin, existing))

    print(f"Method C (Docling -> Gemini) on {len(to_process)} PDFs")
    if not to_process:
        print("Nothing to do!")
        return

    for folder, fname, expected_uin, existing in to_process:
        pdf_path = PDF_BASE / folder / fname
        label = f"{folder}/{fname}"
        print(f"\n{'=' * 70}")
        print(f"  {label}")
        print(f"{'=' * 70}")

        if not pdf_path.exists():
            print(f"  [SKIP] File not found: {pdf_path}")
            continue

        print(f"\n  -- C: Docling -> Markdown -> Gemini --")
        res_c = method_c_docling(client, pdf_path)

        if res_c["success"]:
            p_c, t_c = count_populated(res_c["features"])
            pc_c = round(p_c / max(t_c, 1) * 100)
            print(
                f"    OK {p_c}/{t_c} fields ({pc_c}%) | {res_c['input_tokens']} in / {res_c['output_tokens']} out | {res_c['docling_time_s']}s docling | {res_c['latency_ms']}ms total"
            )
        else:
            p_c, t_c, pc_c = 0, 0, 0
            print(f"    FAIL {res_c['error']}")

        method_c_data = {
            "success": res_c["success"],
            "input_tokens": res_c["input_tokens"],
            "output_tokens": res_c["output_tokens"],
            "api_calls": res_c["api_calls"],
            "latency_ms": res_c["latency_ms"],
            "fields_populated": p_c,
            "fields_total": t_c,
            "fields_pct": pc_c,
            "markdown_chars": res_c["markdown_chars"],
            "docling_time_s": res_c["docling_time_s"],
            "error": res_c["error"],
            "features": features_to_dict(res_c["features"]),
        }

        for i, r in enumerate(all_results):
            if make_skip_key(
                r.get("folder", ""), r.get("filename", "")
            ) == make_skip_key(folder, fname):
                all_results[i]["method_c"] = method_c_data

                a_succ = r["method_a"].get("success", False)
                b_succ = r["method_b"].get("success", False)
                if a_succ and b_succ and res_c["success"]:
                    feat_a = reconstruct_features(r["method_a"].get("features", {}))
                    feat_b = reconstruct_features(r["method_b"].get("features", {}))
                    feat_c = reconstruct_features(method_c_data.get("features", {}))
                    comp = three_way_compare(feat_a, feat_b, feat_c)
                    all_results[i]["comparison_3way"] = comp
                    print(f"\n  -- 3-Way Comparison --")
                    cts = comp["counts"]
                    total_n = sum(cts.values())
                    match_pct = round(cts["all_match"] / max(total_n, 1) * 100)
                    print(f"    Total fields checked: {total_n}")
                    print(f"    All 3 match: {cts['all_match']} ({match_pct}%)")
                    print(f"    C-only (found by Docling): {cts['c_only']}")
                    print(f"    A-only (found by Native PDF): {cts['a_only']}")
                    print(f"    B-only (found by Text-only): {cts['b_only']}")
                    print(f"    A+B agree, C differs: {cts['ab_match_c_diff']}")
                    print(f"    A+C agree, B differs: {cts['ac_match_b_diff']}")
                    print(f"    B+C agree, A differs: {cts['bc_match_a_diff']}")
                    print(f"    All 3 differ: {cts['all_diff']}")
                    for d in comp["diffs"][:20]:
                        print(
                            f"      [{d['status']}] {d['field']}: A={d['a']} B={d['b']} C={d['c']}"
                        )
                    if len(comp["diffs"]) > 20:
                        print(f"      ... and {len(comp['diffs']) - 20} more")
                else:
                    all_results[i]["comparison_3way"] = None
                break

        with open(out_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str, ensure_ascii=False)
        print(f"\n  [SAVED] {out_path}")

    # Summary
    c_ok = sum(1 for r in all_results if r.get("method_c", {}).get("success"))
    c_done = sum(1 for r in all_results if "method_c" in r)
    print(f"\n{'=' * 60}")
    print(f"Method C summary: {c_ok}/{c_done} successful")
    for r in all_results:
        mc = r.get("method_c", {})
        if mc.get("success"):
            print(
                f"  OK {r['folder']}/{r['filename']}: {mc['fields_populated']}/{mc['fields_total']} ({mc['fields_pct']}%) | {mc['input_tokens']} in / {mc['output_tokens']} out | {mc['docling_time_s']}s docling"
            )
        elif mc:
            print(f"  FAIL {r['folder']}/{r['filename']}: {mc.get('error', '?')}")


if __name__ == "__main__":
    main()
