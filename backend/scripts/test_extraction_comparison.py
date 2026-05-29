"""Compare Gemini 2.5 Flash extraction quality: Native PDF (File API) vs Text-only (PyMuPDF).

Runs both methods on 8 test policies and produces a side-by-side comparison.

Usage:
    .venv/bin/python backend/scripts/test_extraction_comparison.py
"""

import json, os, sys, time, re
from pathlib import Path
from datetime import datetime
from typing import Optional
import random

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

BASE = Path(__file__).resolve().parent.parent.parent
PDF_BASE = Path("/Users/aviralsharma/Personal Projects/policy_data")

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


# ─── Field counting ───


def _count_model_fields(model_cls, model_instance):
    """Count populated and total fields recursively using class model_fields."""
    populated = 0
    total = 0
    for fn in model_cls.model_fields:
        fv = getattr(model_instance, fn)
        total += 1
        if fv is not None:
            if hasattr(type(fv), "model_fields") and type(fv) is not type(None):
                if type(fv) is not type(None):
                    p, t = _count_model_fields(type(fv), fv)
                    populated += p
                    total += t
            elif isinstance(fv, list):
                if len(fv) > 0:
                    populated += 1
            else:
                populated += 1
    return populated, total


def count_populated(features: PolicyFeatures) -> tuple[int, int]:
    if features is None:
        return 0, 0
    return _count_model_fields(PolicyFeatures, features)


# ─── Text extraction ───


def extract_text_from_pdf(pdf_path: Path) -> Optional[str]:
    try:
        import fitz

        doc = fitz.open(pdf_path)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text("text"))
        doc.close()
        full_text = "\n\n--- PAGE BREAK ---\n\n".join(text_parts)

        if len(full_text) > 950000:
            print(f"    [TRUNCATE] Input {len(full_text)} chars > 950K limit")
            full_text = full_text[:950000] + "\n\n[CONTENT TRUNCATED]"

        return full_text
    except Exception as e:
        print(f"    [ERROR] PyMuPDF failed: {e}")
        return None


# ─── Retry helper ───


def with_retry(fn, max_retries=5, base_delay=5):
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            err_str = str(e)
            is_503 = "503" in err_str or "UNAVAILABLE" in err_str
            is_429 = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
            if (is_503 or is_429) and attempt < max_retries - 1:
                # Try to extract retryDelay from API error
                import re

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


# ─── Method A: Native PDF via File API ───


def method_a_native_pdf(client, pdf_path: Path) -> dict:
    result = {
        "success": False,
        "input_tokens": 0,
        "output_tokens": 0,
        "api_calls": 0,
        "latency_ms": 0,
        "features": None,
        "error": None,
    }
    uploaded = None
    t0 = time.perf_counter()

    try:
        uploaded = client.files.upload(file=str(pdf_path))
        result["api_calls"] += 1
        print(f"    [UPLOAD] {uploaded.name} state={uploaded.state}")

        wait_start = time.perf_counter()
        while uploaded.state != "ACTIVE":
            if time.perf_counter() - wait_start > 60:
                raise TimeoutError("File upload wait timed out (60s)")
            time.sleep(1)
            uploaded = client.files.get(name=uploaded.name)
            result["api_calls"] += 1

        response = with_retry(
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[uploaded, EXTRACTION_PROMPT],
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
        print(f"    [FAIL] Method A: {e}")

    finally:
        if uploaded:
            try:
                client.files.delete(name=uploaded.name)
                result["api_calls"] += 1
            except Exception:
                pass

    result["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


# ─── Method B: Text-only ───


def method_b_text_only(client, pdf_path: Path) -> dict:
    result = {
        "success": False,
        "input_tokens": 0,
        "output_tokens": 0,
        "api_calls": 0,
        "latency_ms": 0,
        "features": None,
        "error": None,
    }
    t0 = time.perf_counter()

    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        if not pdf_text or not pdf_text.strip():
            result["error"] = "Text extraction failed or empty"
            return result

        print(f"    [TEXT] Extracted {len(pdf_text)} chars")

        response = with_retry(
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[pdf_text, EXTRACTION_PROMPT],
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
        print(f"    [FAIL] Method B: {e}")

    result["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


# ─── Comparison ───


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


def compare_features(feat_a, feat_b) -> dict:
    diffs = []
    matches = 0
    a_only = 0
    b_only = 0

    def _compare(a_val, b_val, path):
        nonlocal matches, a_only, b_only

        if a_val is None and b_val is None:
            return
        if a_val is None:
            b_only += 1
            diffs.append({"field": path, "a": None, "b": _summarize(b_val)})
            return
        if b_val is None:
            a_only += 1
            diffs.append({"field": path, "a": _summarize(a_val), "b": None})
            return

        if hasattr(type(a_val), "model_fields") and hasattr(
            type(b_val), "model_fields"
        ):
            a_cls = type(a_val)
            for sub_fn in a_cls.model_fields:
                _compare(
                    getattr(a_val, sub_fn), getattr(b_val, sub_fn), f"{path}.{sub_fn}"
                )
        elif isinstance(a_val, list) and isinstance(b_val, list):
            a_s = _summarize(a_val)
            b_s = _summarize(b_val)
            if a_s != b_s:
                diffs.append({"field": path, "a": a_s, "b": b_s})
        elif a_val != b_val:
            diffs.append(
                {"field": path, "a": _summarize(a_val), "b": _summarize(b_val)}
            )

    for fn in PolicyFeatures.model_fields:
        a_val = getattr(feat_a, fn)
        b_val = getattr(feat_b, fn)
        matches += 1
        _compare(a_val, b_val, fn)

    return {"matches": matches, "a_only": a_only, "b_only": b_only, "diffs": diffs}


def features_to_dict(features):
    if features is None:
        return {}
    try:
        return json.loads(features.model_dump_json(exclude_none=True))
    except Exception:
        return {}


# ─── Single PDF processing ───


def process_single_pdf(client, folder, fname, expected_uin) -> dict:
    pdf_path = PDF_BASE / folder / fname
    label = f"{folder}/{fname}"
    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"  UIN: {expected_uin}")
    print(f"{'=' * 70}")

    if not pdf_path.exists():
        print(f"  [SKIP] File not found: {pdf_path}")
        return {"label": label, "error": "file_not_found"}

    print(f"\n  ── A: Native PDF (File API) ──")
    res_a = method_a_native_pdf(client, pdf_path)
    if res_a["success"]:
        p_a, t_a = count_populated(res_a["features"])
        pc_a = round(p_a / max(t_a, 1) * 100)
        print(
            f"    ✓ {p_a}/{t_a} fields ({pc_a}%) | {res_a['input_tokens']} in / {res_a['output_tokens']} out | {res_a['api_calls']} calls | {res_a['latency_ms']}ms"
        )
    else:
        p_a, t_a, pc_a = 0, 0, 0
        print(f"    ✗ {res_a['error']}")

    print(f"\n  ── B: Text-only (PyMuPDF) ──")
    res_b = method_b_text_only(client, pdf_path)
    if res_b["success"]:
        p_b, t_b = count_populated(res_b["features"])
        pc_b = round(p_b / max(t_b, 1) * 100)
        print(
            f"    ✓ {p_b}/{t_b} fields ({pc_b}%) | {res_b['input_tokens']} in / {res_b['output_tokens']} out | {res_b['api_calls']} calls | {res_b['latency_ms']}ms"
        )
    else:
        p_b, t_b, pc_b = 0, 0, 0
        print(f"    ✗ {res_b['error']}")

    comparison = None
    if res_a["success"] and res_b["success"]:
        comparison = compare_features(res_a["features"], res_b["features"])
        print(f"\n  ── Comparison ──")
        print(
            f"    Matching: {comparison['matches']} | A-only: {comparison['a_only']} | B-only: {comparison['b_only']} | Conflicts: {len(comparison['diffs'])}"
        )
        for d in comparison["diffs"][:10]:
            print(f"      ⚠ {d['field']}: A={d['a']} | B={d['b']}")
        if len(comparison["diffs"]) > 10:
            print(f"      ... and {len(comparison['diffs']) - 10} more")

    return {
        "folder": folder,
        "filename": fname,
        "expected_uin": expected_uin,
        "file_size_bytes": pdf_path.stat().st_size if pdf_path.exists() else None,
        "method_a": {
            "success": res_a["success"],
            "input_tokens": res_a["input_tokens"],
            "output_tokens": res_a["output_tokens"],
            "api_calls": res_a["api_calls"],
            "latency_ms": res_a["latency_ms"],
            "fields_populated": p_a,
            "fields_total": t_a,
            "fields_pct": pc_a,
            "error": res_a["error"],
            "features": features_to_dict(res_a["features"]),
        },
        "method_b": {
            "success": res_b["success"],
            "input_tokens": res_b["input_tokens"],
            "output_tokens": res_b["output_tokens"],
            "api_calls": res_b["api_calls"],
            "latency_ms": res_b["latency_ms"],
            "fields_populated": p_b,
            "fields_total": t_b,
            "fields_pct": pc_b,
            "error": res_b["error"],
            "features": features_to_dict(res_b["features"]),
        },
        "comparison": {
            "matches": comparison["matches"] if comparison else None,
            "a_only": comparison["a_only"] if comparison else None,
            "b_only": comparison["b_only"] if comparison else None,
            "diffs": comparison["diffs"] if comparison else [],
        },
    }


# ─── Report ───


def print_report(results):
    print(f"\n\n{'=' * 80}")
    print(f"  EXTRACTION METHOD COMPARISON — SUMMARY REPORT")
    print(f"  Model: {GEMINI_MODEL} | Prompt: {PROMPT_VERSION}")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}")

    n = len(results)
    a_ok = sum(1 for r in results if r["method_a"]["success"])
    b_ok = sum(1 for r in results if r["method_b"]["success"])
    total_a_api = sum(r["method_a"]["api_calls"] for r in results)
    total_b_api = sum(r["method_b"]["api_calls"] for r in results)
    total_a_in = sum(r["method_a"]["input_tokens"] for r in results)
    total_b_in = sum(r["method_b"]["input_tokens"] for r in results)
    total_a_out = sum(r["method_a"]["output_tokens"] for r in results)
    total_b_out = sum(r["method_b"]["output_tokens"] for r in results)

    def sum_pop(rs, key):
        return sum(r[key]["fields_populated"] for r in rs if r[key]["success"])

    def sum_tot(rs, key):
        return sum(r[key]["fields_total"] for r in rs if r[key]["success"])

    total_a_p = sum_pop(results, "method_a")
    total_a_t = sum_tot(results, "method_a")
    total_b_p = sum_pop(results, "method_b")
    total_b_t = sum_tot(results, "method_b")
    a_pct = round(total_a_p / max(total_a_t, 1) * 100)
    b_pct = round(total_b_p / max(total_b_t, 1) * 100)
    total_m = sum(r["comparison"]["matches"] or 0 for r in results)
    total_ao = sum(r["comparison"]["a_only"] or 0 for r in results)
    total_bo = sum(r["comparison"]["b_only"] or 0 for r in results)
    total_ds = sum(len(r["comparison"].get("diffs", [])) for r in results)
    total_la = sum(
        r["method_a"]["latency_ms"] for r in results if r["method_a"]["success"]
    )
    total_lb = sum(
        r["method_b"]["latency_ms"] for r in results if r["method_b"]["success"]
    )

    print(f"""
╔════════════════════════════════════════╤══════════════╤═══════════════╗
║ Metric                                 │ Native PDF   │ Text-only     ║
╠════════════════════════════════════════╪══════════════╪═══════════════╣
║ Processed successfully                 │ {a_ok}/{n:<4}          │ {b_ok}/{n:<4}            ║
║ API calls                              │ {total_a_api:<4}           │ {total_b_api:<4}             ║
║ Input tokens                           │ {total_a_in:<11} │ {total_b_in:<11}  │
║ Output tokens                          │ {total_a_out:<11} │ {total_b_out:<11}  │
║ Fields populated                       │ {total_a_p:<3}/{total_a_t:<3} ({a_pct}%)       │ {total_b_p:<3}/{total_b_t:<3} ({b_pct}%)         ║
║ Avg latency                            │ {total_la // max(a_ok, 1):<5}ms       │ {total_lb // max(b_ok, 1):<5}ms          ║
╚════════════════════════════════════════╧══════════════╧═══════════════╝

╔══════════════════════════════════════════════════════════════════════╗
║  FIELD AGREEMENT                                                    ║
╠══════════════════════════════════════════════════════════════════════╣
║ Matching values: {total_m:<4} (both methods found same non-null value)          ║
║ Only in Native PDF: {total_ao:<4}                                       ║
║ Only in Text-only: {total_bo:<4}                                        ║
║ Conflicting values: {total_ds:<4}                                       ║
╚══════════════════════════════════════════════════════════════════════╝

PRICING (Gemini 2.5 Flash: $0.15/1M in, $0.60/1M out):
""")

    cost_a = (total_a_in / 1_000_000) * 0.15 + (total_a_out / 1_000_000) * 0.60
    cost_b = (total_b_in / 1_000_000) * 0.15 + (total_b_out / 1_000_000) * 0.60
    print(f"  8-test cost: A=${cost_a:.4f}  B=${cost_b:.4f}")
    proj_a = cost_a / max(n, 1) * 781
    proj_b = cost_b / max(n, 1) * 781
    print(f"  781-pdf cost: A=~${proj_a:.2f}  B=~${proj_b:.2f}")

    print(f"\n{'=' * 80}")
    print(f"  PER-PDF DETAILS")
    print(f"{'=' * 80}")
    for r in results:
        m = r["method_a"]
        n_ = r["method_b"]
        c_ = r["comparison"]
        a_s = "✓" if m["success"] else "✗"
        b_s = "✓" if n_["success"] else "✗"
        print(f"""
  {r["folder"]}/{r["filename"]}
    UIN: {r["expected_uin"]}
    [{a_s}] Native: {m["fields_populated"]}/{m["fields_total"]} ({m["fields_pct"]}%) | {m["input_tokens"]} in / {m["output_tokens"]} out | {m["api_calls"]}c | {m["latency_ms"]}ms
    [{b_s}] Text:   {n_["fields_populated"]}/{n_["fields_total"]} ({n_["fields_pct"]}%) | {n_["input_tokens"]} in / {n_["output_tokens"]} out | {n_["api_calls"]}c | {n_["latency_ms"]}ms
    Agreement: matches={c_["matches"]} A-only={c_["a_only"]} B-only={c_["b_only"]} conflicts={len(c_.get("diffs", []))}""")
        for d in c_.get("diffs", [])[:8]:
            print(f"      ⚠ {d['field']}: A={d['a']}  B={d['b']}")
        if len(c_.get("diffs", [])) > 8:
            print(f"      ... +{len(c_['diffs']) - 8} more")
        if m.get("error"):
            print(f"    Native error: {m['error']}")
        if n_.get("error"):
            print(f"    Text error: {n_['error']}")

    print(f"\n{'=' * 80}")
    print(f"  END REPORT")
    print(f"{'=' * 80}\n")


# ─── Main ───


def load_existing_results(path: Path) -> list:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def make_skip_key(folder, fname):
    return f"{folder}/{fname}"


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set in .env")
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    out_path = BASE / "data" / "extraction_comparison_results.json"
    existing = load_existing_results(out_path)
    skip_keys = set()
    for r in existing:
        skip_keys.add(make_skip_key(r.get("folder", ""), r.get("filename", "")))
        # Re-process if either method failed (likely rate limit)
        if r["method_a"]["success"] and r["method_b"]["success"]:
            pass  # keep in skip set
        else:
            skip_keys.discard(make_skip_key(r.get("folder", ""), r.get("filename", "")))

    print(f"Extraction Comparison Test (resume mode)")
    print(f"Model: {GEMINI_MODEL}")
    print(
        f"Total: {len(TEST_PDFS)} policies, {len(existing)} already started, {len(TEST_PDFS) - len(skip_keys)} remaining"
    )

    all_results = list(existing)
    existing_by_key = {
        make_skip_key(r.get("folder", ""), r.get("filename", "")): r for r in existing
    }

    for folder, fname, expected_uin in TEST_PDFS:
        key = make_skip_key(folder, fname)
        if key in skip_keys:
            existing_r = existing_by_key.get(key, {})
            a_ok = existing_r.get("method_a", {}).get("success", False)
            b_ok = existing_r.get("method_b", {}).get("success", False)
            print(
                f"\n  [SKIP] {key} (A={'OK' if a_ok else 'FAIL'}, B={'OK' if b_ok else 'FAIL'}, existing)"
            )
            continue

        result = process_single_pdf(client, folder, fname, expected_uin)
        # Remove old entry for same key and append new
        all_results = [
            r
            for r in all_results
            if make_skip_key(r.get("folder", ""), r.get("filename", "")) != key
        ]
        all_results.append(result)

        with open(out_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str, ensure_ascii=False)
        print(f"\n  [SAVED] {out_path}")

    print_report(all_results)


if __name__ == "__main__":
    main()
