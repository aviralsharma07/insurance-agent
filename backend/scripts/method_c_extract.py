"""Method C: Gemini extraction from cached Docling markdown + 3-way comparison.

Reads markdown from data/docling_markdown/, sends to Gemini 2.5 Flash,
saves Method C results, then compares against existing A (Native PDF) and
B (Text-only) in extraction_comparison_results.json.

Usage:
    .venv/bin/python backend/scripts/method_c_extract.py
"""

import json, os, sys, time, re, random
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

BASE = Path(__file__).resolve().parent.parent.parent
MD_DIR = BASE / "data" / "docling_markdown"
RESULTS_PATH = BASE / "data" / "extraction_comparison_results.json"

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

# 4 test PDFs that have existing A & B results
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
]


# ─── Helpers ───


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


def features_to_dict(features):
    if features is None:
        return {}
    try:
        return json.loads(features.model_dump_json(exclude_none=True))
    except Exception:
        return {}


def reconstruct_features(fd: dict) -> PolicyFeatures:
    if not fd:
        return PolicyFeatures()
    try:
        return PolicyFeatures.model_validate(fd)
    except Exception:
        return PolicyFeatures()


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


def make_key(folder, fname):
    return f"{folder}/{fname}"


# ─── Retry ───


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


# ─── Gemini extraction from markdown ───


def extract_from_markdown(client, md_text: str) -> dict:
    result = {
        "success": False,
        "input_tokens": 0,
        "output_tokens": 0,
        "api_calls": 0,
        "features": None,
        "error": None,
    }

    if len(md_text) > 950000:
        print(f"    [TRUNCATE] Input {len(md_text)} chars > 950K limit")
        md_text = md_text[:950000] + "\n\n[CONTENT TRUNCATED]"

    response = with_retry(
        lambda: client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[md_text, EXTRACTION_PROMPT],
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

    return result


# ─── 3-way comparison ───


def three_way_compare(feat_a, feat_b, feat_c) -> dict:
    diff_report = []

    def _classify(a_val, b_val, c_val, path):
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

        s = {a_s, b_s, c_s}
        if len(s) == 2:
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
            s = _classify(a_val, b_val, c_val, path)
            if s not in ("all_match", "all_null"):
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
            s = _classify(a_val, b_val, c_val, path)
            if s not in ("all_match", "all_null"):
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
    c = feat_c or PolicyFeatures()

    for fn in PolicyFeatures.model_fields:
        _walk(getattr(a, fn), getattr(b, fn), getattr(c, fn), fn)

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


# ─── Report ───


def print_comparison_report(all_results):
    print(f"\n\n{'=' * 90}")
    print(f"  3-WAY EXTRACTION COMPARISON REPORT")
    print(f"  Model: {GEMINI_MODEL} | Prompt: {PROMPT_VERSION}")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 90}")

    # Aggregate across 4 PDFs
    total_a_pop = total_a_tot = 0
    total_b_pop = total_b_tot = 0
    total_c_pop = total_c_tot = 0
    total_a_in = total_a_out = 0
    total_b_in = total_b_out = 0
    total_c_in = total_c_out = 0
    total_a_lat = total_b_lat = total_c_lat = 0
    a_ok = b_ok = c_ok = 0

    agg_counts = {}

    for r in all_results:
        m = r.get("method_a", {})
        n = r.get("method_b", {})
        o = r.get("method_c", {})

        if m.get("success"):
            a_ok += 1
            total_a_pop += m.get("fields_populated", 0)
            total_a_tot += m.get("fields_total", 0)
            total_a_in += m.get("input_tokens", 0)
            total_a_out += m.get("output_tokens", 0)
            total_a_lat += m.get("latency_ms", 0)

        if n.get("success"):
            b_ok += 1
            total_b_pop += n.get("fields_populated", 0)
            total_b_tot += n.get("fields_total", 0)
            total_b_in += n.get("input_tokens", 0)
            total_b_out += n.get("output_tokens", 0)
            total_b_lat += n.get("latency_ms", 0)

        if o.get("success"):
            c_ok += 1
            total_c_pop += o.get("fields_populated", 0)
            total_c_tot += o.get("fields_total", 0)
            total_c_in += o.get("input_tokens", 0)
            total_c_out += o.get("output_tokens", 0)
            total_c_lat += o.get("latency_ms", 0)

        comp = r.get("comparison_3way")
        if comp and comp.get("counts"):
            for k, v in comp["counts"].items():
                agg_counts[k] = agg_counts.get(k, 0) + v

    n = 4
    a_pct = round(total_a_pop / max(total_a_tot, 1) * 100)
    b_pct = round(total_b_pop / max(total_b_tot, 1) * 100)
    c_pct = round(total_c_pop / max(total_c_tot, 1) * 100)

    print(f"""
┌─────────────────────────────────────┬─────────────┬──────────────┬──────────────┐
│ Metric                              │ Native PDF  │ Text-only    │ Docling+MD   │
│                                     │ (Method A)  │ (Method B)   │ (Method C)   │
├─────────────────────────────────────┼─────────────┼──────────────┼──────────────┤
│ Success rate                        │ {a_ok}/{n:<4}        │ {b_ok}/{n:<4}         │ {c_ok}/{n:<4}          │
│ Fields populated (total)            │ {total_a_pop:>3}/{total_a_tot:<3} ({a_pct}%) │ {total_b_pop:>3}/{total_b_tot:<3} ({b_pct}%) │ {total_c_pop:>3}/{total_c_tot:<3} ({c_pct}%) │
│ Input tokens (total)                │ {total_a_in:<11} │ {total_b_in:<11}  │ {total_c_in:<11}  │
│ Output tokens (total)               │ {total_a_out:<11} │ {total_b_out:<11}  │ {total_c_out:<11}  │
│ Avg latency per PDF                 │ {total_a_lat // max(a_ok, 1):<5}ms    │ {total_b_lat // max(b_ok, 1):<5}ms     │ {total_c_lat // max(c_ok, 1):<5}ms     │
└─────────────────────────────────────┴─────────────┴──────────────┴──────────────┘

Pricing (Gemini 2.5 Flash: $0.15/1M in, $0.60/1M out):
""")

    cost_a = (total_a_in / 1_000_000) * 0.15 + (total_a_out / 1_000_000) * 0.60
    cost_b = (total_b_in / 1_000_000) * 0.15 + (total_b_out / 1_000_000) * 0.60
    cost_c = (total_c_in / 1_000_000) * 0.15 + (total_c_out / 1_000_000) * 0.60
    print(f"  4-test cost: A=${cost_a:.4f}  B=${cost_b:.4f}  C=${cost_c:.4f}")
    print(
        f"  781-pdf projected: A=~${cost_a / 4 * 781:.2f}  B=~${cost_b / 4 * 781:.2f}  C=~${cost_c / 4 * 781:.2f}"
    )

    print(f"""
┌───────────────────────────────────────────────────────────────────────────┐
│  FIELD AGREEMENT (3-WAY)                                                  │
├───────────────────────────────────────────────────────────────────────────┤""")

    for k, v in sorted(agg_counts.items()):
        label = k.replace("_", " ")
        print(f"│  {label:35s} {v:>4}                                    │")

    print(
        f"└───────────────────────────────────────────────────────────────────────────┘"
    )

    # Per-PDF detail
    print(f"\n{'=' * 90}")
    print(f"  PER-PDF DETAILS")
    print(f"{'=' * 90}")

    for r in all_results:
        key = f"{r.get('folder', '?')}/{r.get('filename', '?')}"
        m = r.get("method_a", {})
        n = r.get("method_b", {})
        o = r.get("method_c", {})
        comp = r.get("comparison_3way")

        a_s = "OK" if m.get("success") else "FAIL"
        b_s = "OK" if n.get("success") else "FAIL"
        c_s = "OK" if o.get("success") else "FAIL"

        print(f"""
  {key}
    [{a_s}] Native:  {m.get("fields_populated", "?")}/{m.get("fields_total", "?")} ({m.get("fields_pct", "?")}%) | {m.get("input_tokens", "?")} in / {m.get("output_tokens", "?")} out | {m.get("latency_ms", "?")}ms
    [{b_s}] Text:    {n.get("fields_populated", "?")}/{n.get("fields_total", "?")} ({n.get("fields_pct", "?")}%) | {n.get("input_tokens", "?")} in / {n.get("output_tokens", "?")} out | {n.get("latency_ms", "?")}ms
    [{c_s}] Docling: {o.get("fields_populated", "?")}/{o.get("fields_total", "?")} ({o.get("fields_pct", "?")}%) | {o.get("input_tokens", "?")} in / {o.get("output_tokens", "?")} out | {o.get("latency_ms", "?")}ms""")

        if comp and comp.get("diffs"):
            cts = comp["counts"]
            print(
                f"    3-way: all_match={cts['all_match']} A_only={cts['a_only']} B_only={cts['b_only']} C_only={cts['c_only']} A+B≠C={cts['ab_match_c_diff']} A+C≠B={cts['ac_match_b_diff']} B+C≠A={cts['bc_match_a_diff']} all_diff={cts['all_diff']}"
            )

            # Show the most interesting diffs
            c_only_items = [d for d in comp["diffs"] if d["status"] == "c_only"]
            a_only_items = [d for d in comp["diffs"] if d["status"] == "a_only"]
            b_only_items = [d for d in comp["diffs"] if d["status"] == "b_only"]

            if c_only_items:
                print(f"    Fields only Docling found ({len(c_only_items)}):")
                for d in c_only_items[:8]:
                    print(f"      + {d['field']}: {d['c']}")
                if len(c_only_items) > 8:
                    print(f"      ... +{len(c_only_items) - 8} more")

            if a_only_items:
                print(f"    Fields only Native PDF found ({len(a_only_items)}):")
                for d in a_only_items[:5]:
                    print(f"      + {d['field']}: {d['a']}")

            if b_only_items:
                print(f"    Fields only Text-only found ({len(b_only_items)}):")
                for d in b_only_items[:5]:
                    print(f"      + {d['field']}: {d['b']}")

            ab_c_diff = [d for d in comp["diffs"] if d["status"] == "ab_match_c_diff"]
            if ab_c_diff:
                print(f"    A+B agree but C different ({len(ab_c_diff)}):")
                for d in ab_c_diff[:5]:
                    print(f"      ! {d['field']}: A=B={d['a']}  C={d['c']}")

        if r.get("method_c", {}).get("docling_time_s"):
            print(
                f"    (Docling conversion: {o.get('docling_time_s', '?')}s, markdown: {o.get('markdown_chars', '?')} chars)"
            )

    print(f"\n{'=' * 90}")
    print(f"  END REPORT")
    print(f"{'=' * 90}\n")


# ─── Main ───


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set in .env")
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    if not RESULTS_PATH.exists():
        print(f"ERROR: {RESULTS_PATH} not found")
        sys.exit(1)

    with open(RESULTS_PATH) as f:
        all_results = json.load(f)

    print(f"METHOD C: Gemini extraction from Docling markdown")
    print(f"Model: {GEMINI_MODEL}")
    print(f"Cached markdown: {MD_DIR}")
    print()

    # Process each PDF
    for i, (folder, fname, uin) in enumerate(TEST_PDFS, 1):
        key = make_key(folder, fname)
        md_path = MD_DIR / folder / f"{fname}.md"

        # Check if method_c already done in results
        existing_entry = None
        for r in all_results:
            if make_key(r.get("folder", ""), r.get("filename", "")) == key:
                existing_entry = r
                break

        if not existing_entry:
            print(f"  [{i}/4] {key} — SKIP (no existing A/B results)")
            continue

        if existing_entry.get("method_c", {}).get("success"):
            print(f"  [{i}/4] {key} — SKIP (already done)")
            continue

        if not md_path.exists():
            print(f"  [{i}/4] {key} — SKIP (markdown not found at {md_path})")
            continue

        print(f"  [{i}/4] {key}")
        print(f"         Reading markdown: {md_path}")

        with open(md_path) as f:
            md_text = f.read()
        print(f"         {len(md_text):,} chars loaded")

        t0 = time.perf_counter()
        print(f"         Calling Gemini...", end=" ", flush=True)
        res = extract_from_markdown(client, md_text)
        elapsed = time.perf_counter() - t0

        if res["success"]:
            p, t = count_populated(res["features"])
            pc = round(p / max(t, 1) * 100)
            print(
                f"OK  {p}/{t} fields ({pc}%) | {res['input_tokens']} in / {res['output_tokens']} out | {elapsed:.0f}s"
            )
        else:
            p, t, pc = 0, 0, 0
            print(f"FAIL  {res['error']}")

        # Build method_c data
        method_c_data = {
            "success": res["success"],
            "input_tokens": res["input_tokens"],
            "output_tokens": res["output_tokens"],
            "api_calls": res["api_calls"],
            "latency_ms": int(elapsed * 1000),
            "fields_populated": p,
            "fields_total": t,
            "fields_pct": pc,
            "markdown_chars": len(md_text),
            "error": res["error"],
            "features": features_to_dict(res["features"]),
        }

        # Update the entry in all_results
        for j, r in enumerate(all_results):
            if make_key(r.get("folder", ""), r.get("filename", "")) == key:
                all_results[j]["method_c"] = method_c_data

                # 3-way comparison if all methods succeeded
                a_succ = r.get("method_a", {}).get("success", False)
                b_succ = r.get("method_b", {}).get("success", False)
                if a_succ and b_succ and res["success"]:
                    feat_a = reconstruct_features(r["method_a"].get("features", {}))
                    feat_b = reconstruct_features(r["method_b"].get("features", {}))
                    feat_c = reconstruct_features(method_c_data.get("features", {}))
                    comp = three_way_compare(feat_a, feat_b, feat_c)
                    all_results[j]["comparison_3way"] = comp
                    cts = comp["counts"]
                    print(
                        f"         3-way: all_match={cts['all_match']} c_only={cts['c_only']} a_only={cts['a_only']} b_only={cts['b_only']}"
                    )
                else:
                    all_results[j]["comparison_3way"] = None
                break

        # Save after each PDF (resume-safe)
        with open(RESULTS_PATH, "w") as f:
            json.dump(all_results, f, indent=2, default=str, ensure_ascii=False)
        print(f"         Saved to {RESULTS_PATH}")

    # Print final comparison report
    print_comparison_report(all_results)


if __name__ == "__main__":
    main()
