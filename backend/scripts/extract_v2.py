"""Multi-pass extraction with detailed tracking.

Runs 4 focused passes per PDF using two methods (Native PDF, Docling+Markdown),
then compares fill rates against the old single-pass results.

Usage:
    .venv/bin/python backend/scripts/extract_v2.py [--methods a] [--resume]

Options:
    --methods a|c|ac    Methods to run: a=Native PDF, c=Docling (default: ac)
    --resume            Resume from last saved state

Output:
    - Updates extraction_comparison_results.json with multi_pass results
    - Creates data/extraction_v2_tracking.json with per-pass telemetry
"""

import json, os, sys, time, re, random, argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

BASE = Path(__file__).resolve().parent.parent.parent
PDF_BASE = Path("/Users/aviralsharma/Personal Projects/policy_data")
MD_DIR = BASE / "data" / "docling_markdown"
RESULTS_PATH = BASE / "data" / "extraction_comparison_results.json"
TRACKING_PATH = BASE / "data" / "extraction_v2_tracking.json"

sys.path.insert(0, str(BASE))
from backend.models.policy_features import PolicyFeatures, TOTAL_FIELDS
from backend.prompts.pass_config import PASS_CONFIG, get_pass_for_field
from backend.prompts.prompts import PASS_PROMPTS, PROMPT_VERSION

GEMINI_MODEL = "gemini-2.5-flash-lite"

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
    (
        "03_Care_Health",
        "Care_Health_Care.pdf",
        "CHIHLIP22184V062122",
    ),
]


# ─── Helpers ───────────────────────────────────────────


def _unwrap_optional(ftype):
    """If ftype is Optional[X], return X; else return ftype."""
    from typing import Union as TypingUnion

    origin = getattr(ftype, "__origin__", None)
    if origin is TypingUnion:
        for arg in ftype.__args__:
            if arg is not type(None):
                return arg
    return ftype


def _count_leaf_fields(model_cls) -> int:
    """Count all leaf fields for a model class (handles Optional/Union wrappers)."""
    total = 0
    for fn, fi in model_cls.model_fields.items():
        if fn == "confirmed_absent":
            continue
        ftype = _unwrap_optional(fi.annotation)
        if getattr(ftype, "__origin__", None) is list:
            total += 1
        elif hasattr(ftype, "model_fields"):
            total += _count_leaf_fields(ftype)
        else:
            total += 1
    return total


def _count_model_fields(model_cls, model_instance):
    populated = 0
    for fn in model_cls.model_fields:
        if fn == "confirmed_absent":
            continue
        fv = getattr(model_instance, fn)
        if fv is not None:
            if hasattr(type(fv), "model_fields") and type(fv) is not type(None):
                populated += _count_model_fields(type(fv), fv)[0]
            elif isinstance(fv, list):
                if len(fv) > 0:
                    populated += 1
            else:
                populated += 1
    return populated, _count_leaf_fields(model_cls)


def count_populated(features: PolicyFeatures):
    if features is None:
        return 0, _count_leaf_fields(PolicyFeatures)
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


def make_key(folder, fname):
    return f"{folder}/{fname}"


# ─── Retry ─────────────────────────────────────────────


def with_retry(fn, max_retries=5, base_delay=5):
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            err_str = str(e)
            is_503 = "503" in err_str or "UNAVAILABLE" in err_str
            is_429 = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
            is_retryable = (
                is_503
                or is_429
                or "timeout" in err_str.lower()
                or "connection" in err_str.lower()
            )
            if is_retryable and attempt < max_retries - 1:
                delay_match = re.search(r"retryDelay['\"]:\s*'(\d+)s'", err_str)
                if delay_match:
                    delay = int(delay_match.group(1)) + random.uniform(0, 2)
                else:
                    delay = base_delay * (2**attempt) + random.uniform(0, 2)
                print(
                    f"      [RETRY {attempt + 1}/{max_retries}] waiting {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                raise
    return fn()


# ─── Dedicated field counter for owned fields ──────────

FIELD_COUNTS_CACHE = {}


def count_owned_populated(features: PolicyFeatures, owned_fields: list[str]) -> int:
    """Count how many of the given owned fields are populated (not None) in features."""
    cls = PolicyFeatures
    count = 0
    for fp in owned_fields:
        parts = fp.split(".")
        val = getattr(features, parts[0], None)
        if val is None:
            continue
        if len(parts) == 2 and isinstance(val, BaseModel):
            sub_val = getattr(val, parts[1], None)
            if sub_val is not None:
                count += 1
        elif len(parts) == 1 and val is not None:
            count += 1
    return count


# ─── Gemini extraction ──────────────────────────────────


def extract_single_pass(client, content, pass_index: int) -> dict:
    """Run one extraction pass. `content` is either a File API object or text string."""
    result = {
        "success": False,
        "input_tokens": 0,
        "output_tokens": 0,
        "api_calls": 0,
        "features": None,
        "error": None,
    }

    prompt = PASS_PROMPTS[pass_index]
    contents = [content, prompt]

    response = with_retry(
        lambda: client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
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
        result["features"] = _safe_parse(response.text)
        if result["features"] is not None:
            result["success"] = True
        else:
            result["error"] = "Parse failed"
    else:
        result["error"] = "Empty response"

    return result


# ─── Merge multiple passes ──────────────────────────────


def merge_pass_results(pass_results: list[dict]) -> PolicyFeatures:
    """Merge N pass results into one PolicyFeatures. Earlier passes take priority."""
    merged = PolicyFeatures()
    seen_absent = set()

    for pr in pass_results:
        if not pr["success"] or pr["features"] is None:
            continue
        src = reconstruct_features(pr["features"])

        for fn in PolicyFeatures.model_fields:
            existing = getattr(merged, fn)
            incoming = getattr(src, fn)

            # confirmed_absent: UNION across all passes
            if fn == "confirmed_absent":
                for item in incoming:
                    seen_absent.add(item)
                continue

            if existing is None or (
                isinstance(existing, BaseModel)
                and all(getattr(existing, sf) is None for sf in existing.model_fields)
            ):
                if incoming is not None:
                    setattr(merged, fn, incoming)
                continue

            # Nested models: merge fields individually (incoming fills nulls)
            if isinstance(existing, BaseModel) and isinstance(incoming, BaseModel):
                for sf in existing.model_fields:
                    if getattr(existing, sf) is None:
                        setattr(existing, sf, getattr(incoming, sf))
                setattr(merged, fn, existing)

    merged.confirmed_absent = sorted(seen_absent)
    return merged


# ─── Run all 4 passes for one method on one PDF ────────


def run_method(client, pdf_path: Path, method: str, md_path: Path = None) -> dict:
    """Run all 4 passes for a given method on a PDF.

    method='a': Native PDF via File API
    method='c': Docling markdown
    """
    method_name = "Native PDF" if method == "a" else "Docling+MD"
    token_type = "image_frames" if method == "a" else "text"
    total_result = {
        "method": method,
        "method_name": method_name,
        "token_type": token_type,
        "success": False,
        "passes": [],
        "latency_ms": 0,
        "api_calls_total": 0,
        "input_tokens_total": 0,
        "output_tokens_total": 0,
        "features": None,
        "merged_fields": 0,
        "merged_total": 0,
        "merged_pct": 0,
        "error": None,
    }

    t0 = time.perf_counter()
    uploaded = None

    try:
        # Prepare content: upload for Native PDF, or read markdown
        if method == "a":
            print(f"    [UPLOAD]...", end=" ", flush=True)
            uploaded = client.files.upload(file=str(pdf_path))
            total_result["api_calls_total"] += 1
            wait_start = time.perf_counter()
            while uploaded.state != "ACTIVE":
                if time.perf_counter() - wait_start > 60:
                    raise TimeoutError("File upload wait timed out (60s)")
                time.sleep(1)
                uploaded = client.files.get(name=uploaded.name)
                total_result["api_calls_total"] += 1
            print(f"OK ({uploaded.name})")
            content = uploaded
        else:
            if not md_path or not md_path.exists():
                raise FileNotFoundError(f"Markdown not found: {md_path}")
            with open(md_path) as f:
                content = f.read()
            print(f"    [MARKDOWN] {len(content):,} chars loaded")

        # Run all passes
        pass_results = []
        for pi in range(len(PASS_CONFIG)):
            pass_config = PASS_CONFIG[pi]
            print(f"    [{pass_config['name']}] Calling Gemini...", end=" ", flush=True)
            t1 = time.perf_counter()
            pr = extract_single_pass(client, content, pi)
            elapsed = time.perf_counter() - t1

            # Count owned fields populated
            owned_pop = 0
            owned_total = len(pass_config["owned_fields"])
            if pr["success"] and pr["features"] is not None:
                owned_pop = count_owned_populated(
                    pr["features"], pass_config["owned_fields"]
                )

            pass_record = {
                "pass_index": pi,
                "pass_name": pass_config["name"],
                "token_type": token_type,
                "success": pr["success"],
                "error": pr.get("error"),
                "latency_ms": int(elapsed * 1000),
                "api_calls": pr["api_calls"],
                "input_tokens": pr["input_tokens"],
                "output_tokens": pr["output_tokens"],
                "features": features_to_dict(pr["features"]),
                "owned_populated": owned_pop,
                "owned_total": owned_total,
            }
            total_result["api_calls_total"] += pr["api_calls"]
            total_result["input_tokens_total"] += pr["input_tokens"]
            total_result["output_tokens_total"] += pr["output_tokens"]

            if pr["success"]:
                print(
                    f"OK {owned_pop}/{owned_total} owned fields | {pr['input_tokens']} in / {pr['output_tokens']} out | {elapsed:.0f}s"
                )
            else:
                print(f"FAIL {pr.get('error', '')}")

            pass_results.append(pass_record)

        # If all passes failed, mark as fail
        if not any(pr["success"] for pr in pass_results):
            total_result["error"] = "All passes failed"
            return total_result

        # Merge passes
        total_result["passes"] = pass_results
        merged = merge_pass_results([p for p in pass_results if p["success"]])
        total_result["features"] = features_to_dict(merged)
        mp, mt = count_populated(merged)
        total_result["merged_fields"] = mp
        total_result["merged_total"] = mt
        total_result["merged_pct"] = round(mp / max(mt, 1) * 100)
        total_result["success"] = True

    except Exception as e:
        total_result["error"] = str(e)
        print(f"    [FAIL] {e}")

    finally:
        if uploaded is not None:
            try:
                client.files.delete(name=uploaded.name)
                total_result["api_calls_total"] += 1
            except Exception:
                pass

    total_result["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return total_result


# ─── Compare with old single-pass results ──────────────


def compare_new_vs_old(new_features_dict: dict, old_features_dict: dict) -> dict:
    """Compare multi-pass merged result against old single-pass result."""
    new_f = reconstruct_features(new_features_dict)
    old_f = reconstruct_features(old_features_dict)

    n_pop, n_tot = count_populated(new_f)
    o_pop, o_tot = count_populated(old_f)

    # Find what's new
    new_found = []
    for fn in PolicyFeatures.model_fields:
        nv = getattr(new_f, fn)
        ov = getattr(old_f, fn)
        if nv is not None and ov is None:
            if isinstance(nv, list) and len(nv) > 0:
                new_found.append(fn)
            elif isinstance(nv, BaseModel):
                # Check if any subfield was null before
                for sf in nv.model_fields:
                    if (
                        getattr(nv, sf) is not None and getattr(ov, sf) is None
                        if ov is not None
                        else True
                    ):
                        new_found.append(f"{fn}.{sf}")
            elif not isinstance(nv, BaseModel):
                new_found.append(fn)

    return {
        "new_total": n_pop,
        "old_total": o_pop,
        "delta": n_pop - o_pop,
        "new_pct": round(n_pop / max(n_tot, 1) * 100),
        "old_pct": round(o_pop / max(o_tot, 1) * 100),
        "new_fields_count": len(new_found),
        "new_fields_sample": new_found[:30],
    }


# ─── Tracking file management ──────────────────────────


def load_tracking() -> dict:
    if TRACKING_PATH.exists():
        with open(TRACKING_PATH) as f:
            return json.load(f)
    return {"version": PROMPT_VERSION, "model": GEMINI_MODEL, "pdfs": {}, "summary": {}}


def save_tracking(tracking: dict):
    with open(TRACKING_PATH, "w") as f:
        json.dump(tracking, f, indent=2, default=str, ensure_ascii=False)


def print_summary(tracking: dict):
    print(f"\n{'=' * 90}")
    print(f"  MULTI-PASS EXTRACTION — SUMMARY")
    print(f"  V2 Prompt: {PROMPT_VERSION} | Model: {GEMINI_MODEL}")
    print(f"{'=' * 90}")

    for pdf_key, pdf_data in tracking["pdfs"].items():
        print(f"\n  {pdf_key}")
        for meth_data in pdf_data.get("methods", []):
            mn = meth_data["method_name"]
            if not meth_data["success"]:
                print(f"    [{mn}] FAILED: {meth_data.get('error', '?')}")
                continue
            mp = meth_data["merged_fields"]
            mt = meth_data["merged_total"]
            pct = meth_data["merged_pct"]
            inp = meth_data["input_tokens_total"]
            out = meth_data["output_tokens_total"]
            api = meth_data["api_calls_total"]
            lat = meth_data["latency_ms"]

            tt = meth_data.get("token_type", "?")
            print(
                f"    [{mn}] {mp}/{mt} fields ({pct}%) | {inp} in ({tt}) / {out} out | {api} calls | {lat}ms"
            )

            for pr in meth_data["passes"]:
                pn = pr["pass_name"].ljust(30)
                pt = pr.get("token_type", "?")
                if pr["success"]:
                    print(
                        f"      + {pn} {pr['owned_populated']}/{pr['owned_total']} owned | {pr['input_tokens']} in ({pt}) / {pr['output_tokens']} out | {pr['latency_ms']}ms"
                    )
                else:
                    print(f"      ! {pn} FAIL: {pr.get('error', '?')}")

            comp = meth_data.get("vs_old", {})
            if comp:
                delta_s = (
                    f"+{comp['delta']}" if comp["delta"] > 0 else str(comp["delta"])
                )
                print(
                    f"      vs single-pass: {comp['old_total']} -> {comp['new_total']} ({delta_s}) | {comp['new_fields_count']} new fields"
                )
                if comp.get("new_fields_sample"):
                    for f in comp["new_fields_sample"][:8]:
                        print(f"        + {f}")

    # Total across all PDFs
    total_new = 0
    total_old = 0
    for pdf_data in tracking["pdfs"].values():
        for meth_data in pdf_data.get("methods", []):
            comp = meth_data.get("vs_old", {})
            if comp:
                total_new += comp["new_total"]
                total_old += comp["old_total"]

    if total_old > 0:
        total_delta = total_new - total_old
        total_pct = round(total_new / max(total_old, 1) * 100, 1)
        print(f"\n  {'=' * 60}")
        print(f"  AGGREGATE: {total_old} -> {total_new} ({total_pct}% of old)")
        print(
            f"  Improvement: +{total_delta} fields ({round(total_delta / max(total_old, 1) * 100)}%)"
        )
        print(f"{'=' * 90}\n")


# ─── Main ───────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--methods",
        default="ac",
        choices=["a", "c", "ac"],
        help="Methods to run: a=Native PDF, c=Docling, ac=both",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from saved state")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    # Load existing results for comparison
    if not RESULTS_PATH.exists():
        print(f"ERROR: {RESULTS_PATH} not found (no old results for comparison)")
        sys.exit(1)
    with open(RESULTS_PATH) as f:
        old_results = json.load(f)

    def get_old_features(folder, fname, method_key):
        """Get old single-pass features from results file."""
        for r in old_results:
            if r.get("folder") == folder and r.get("filename") == fname:
                return r.get(method_key, {}).get("features", {})
        return {}

    # Load tracking state
    tracking = load_tracking()

    methods_to_run = list(args.methods)  # ['a'], ['c'], or ['a','c']

    for folder, fname, uin in TEST_PDFS:
        key = make_key(folder, fname)
        pdf_path = PDF_BASE / folder / fname
        md_path = MD_DIR / folder / f"{fname}.md"

        print(f"\n{'=' * 70}")
        print(f"  {key}")
        print(f"  UIN: {uin}")
        print(f"{'=' * 70}")

        if not pdf_path.exists():
            print(f"  SKIP — PDF not found")
            continue

        if key not in tracking["pdfs"]:
            tracking["pdfs"][key] = {"uin": uin, "pdf": str(pdf_path), "methods": []}

        for method in methods_to_run:
            method_name = "Native PDF" if method == "a" else "Docling+MD"

            # Skip if already done (resume mode)
            already_done = False
            for m in tracking["pdfs"][key]["methods"]:
                if m["method"] == method and m["success"]:
                    already_done = True
                    break
            if args.resume and already_done:
                print(f"\n  [{method_name}] SKIP (already done, resume mode)")
                continue

            if method == "c" and not md_path.exists():
                print(f"\n  [{method_name}] SKIP — no cached markdown at {md_path}")
                continue

            print(f"\n  [{method_name}] Running {len(PASS_CONFIG)} passes...")
            result = run_method(client, pdf_path, method, md_path)

            # Compare with old single-pass results
            old_method_key = "method_a" if method == "a" else "method_c"
            old_features = get_old_features(folder, fname, old_method_key)
            if old_features and result["success"]:
                comparison = compare_new_vs_old(result["features"], old_features)
                result["vs_old"] = comparison

                mp = result["merged_fields"]
                mt = result["merged_total"]
                pct = result["merged_pct"]
                delta_s = (
                    f"+{comparison['delta']}"
                    if comparison["delta"] > 0
                    else str(comparison["delta"])
                )
                print(
                    f"    Merged: {mp}/{mt} ({pct}%) | vs single-pass: {comparison['old_total']} -> {comparison['new_total']} ({delta_s})"
                )
                if comparison["new_fields_sample"]:
                    print(
                        f"    New fields: {', '.join(comparison['new_fields_sample'][:12])}"
                    )
            else:
                result["vs_old"] = None
                if result["success"]:
                    mp = result["merged_fields"]
                    mt = result["merged_total"]
                    print(f"    Merged: {mp}/{mt} ({round(mp / max(mt, 1) * 100)}%)")
                else:
                    print(f"    FAILED: {result.get('error', '?')}")

            # Add to tracking
            tracking["pdfs"][key]["methods"].append(result)
            save_tracking(tracking)

        # Compare Native PDF vs Docling for this PDF
        methods = tracking["pdfs"][key]["methods"]
        a_data = next(
            (m for m in methods if m["method"] == "a" and m.get("vs_old")), None
        )
        c_data = next(
            (m for m in methods if m["method"] == "c" and m.get("vs_old")), None
        )
        if a_data and c_data:
            a_comp = a_data["vs_old"]
            c_comp = c_data["vs_old"]
            print(
                f"\n    Method comparison: Native={a_comp['new_total']} fields vs Docling={c_comp['new_total']} fields"
            )
            print(
                f"    Improvement over single-pass: Native +{a_comp['delta']} vs Docling +{c_comp['delta']}"
            )

    # Print final summary
    print_summary(tracking)
    print(f"\nTracking data: {TRACKING_PATH}")
    print(f"Done.")


if __name__ == "__main__":
    main()
