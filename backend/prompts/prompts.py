"""Prompt templates for multi-pass extraction.

Each pass has a focused prompt targeting a specific section of the policy.
Base instructions and terminology aliases are shared across all passes.
"""

from .field_aliases import FIELD_ALIASES
from .pass_config import PASS_CONFIG


PROMPT_VERSION = "v2.2-multipass"


def _build_aliases_section(field_paths: list[str]) -> str:
    """Build a terminology aliases reference for the given fields."""
    lines = ["\n=== TERMINOLOGY ALIASES ==="]
    lines.append("Indian insurers use varied terms for the same thing.")
    lines.append("Watch for these synonyms for the fields in this pass:\n")
    for fp in field_paths:
        aliases = FIELD_ALIASES.get(fp)
        if aliases:
            short_name = fp.split(".")[-1]
            lines.append(f"  {short_name}: {', '.join(aliases[:6])}")
    lines.append("")
    return "\n".join(lines)


def _section_search_hint(keywords: list[str]) -> str:
    hints = ", ".join(f'"{k}"' for k in keywords)
    return (
        f"\n=== SECTION FOCUS ===\n"
        f"Search for these section headings: {hints}\n"
        f"Read ALL text under these sections before extracting.\n"
        f"Do not skip tables, footnotes, fine print, or appendices.\n"
    )


DOCUMENT_STRUCTURE = """\
=== DOCUMENT STRUCTURE (Indian IRDAI-regulated health insurance) ===
Policy Schedule (1st page): UIN, sum insured, premium, insurer, product name,
    policyholder, nominee, policy period, entry/renewal ages
Section 1: What We Cover — Coverage intent, scope of benefits
Section 2: Definitions — Key terms (Cumulative Bonus in 2.12, Day Care in 2.X)
Section 3: How Much We Reimburse — Room rent (3.1), AYUSH (3.4), Maternity (3.5-3.7),
    Cumulative Bonus/NCB (3.10), Restoration (3.11), Optional Covers (3.12-3.13),
    Modern Treatments (3.15)
Section 4: Exclusions — PED (4.1), Initial waiting (4.2), Specific disease waiting (4.3),
    Permanent exclusions (4.4)
Section 5: Conditions — Portability (5.15), Cancellation (5.12), Claims (5.5-5.17),
    Free look (5.13), Grace period (5.11)
Annexures — Day care list, claim forms, network hospital list

CRITICAL: Cumulative Bonus (Section 3.10 / Definition 2.12) IS the No Claim Bonus (NCB).
Policy Schedule has priority for identity/eligibility fields.
Optional Cover sections (3.11-3.13) contain hidden benefits.
Sub-limits are often "% of Sum Insured" — map to percentage strings.
"""


BASE_RULES = """\
You must output valid JSON matching the provided schema exactly.

=== EXTRACTION RULES ===
1. Extract ONLY information explicitly stated in the document — do not infer or guess
2. Use null for fields not found anywhere in the document
3. Pay special attention to TABLES, schedules, appendices, fine print, and footnotes
4. For arrays (exclusions, disease lists, sub-limits, benefit lists): extract EVERY individual item as a separate array element. Do not summarize or write "and others" or "etc." If a table has 15 rows, the array must have 15 items.
5. For monetary values, include the currency symbol (₹) when present
6. Read ALL content under the relevant sections before producing output
7. If the same field appears in multiple places with different values, prefer the value in the Schedule of Benefits or Summary of Coverage table over the value in general conditions or definitions sections.
8. For boolean fields: set to false if explicitly stated as excluded/not-covered, not null
9. If a field value is stated as "as per IRDAI guidelines" or "as per applicable circular" without specifying an actual value, extract the string "as_per_irdai" rather than null. This distinguishes regulatory references from genuinely absent fields.
10. For fields you explicitly searched for but confirmed are genuinely absent from this document (not just hard to find), add the field path to the confirmed_absent list. Example: if this policy has no deductible clause anywhere, add 'deductibles.deductible_amount' to confirmed_absent. Only add a field here if you are certain it does not exist in the document.
11. Indian insurance rule — "Cumulative Bonus" is synonymous with "No Claim Bonus" (NCB). When you find Cumulative Bonus in Section 3.10 or Definition 2.12, map its values (increase %, cap %, type) directly to the no_claim_bonus.* fields. Do not leave these fields null because the document uses "Cumulative Bonus" instead of "NCB".
12. Sub-limits are frequently expressed as a percentage of Sum Insured (e.g. "10% of Sum Insured for Cataract", "20% of SI for Joint Replacement"). Extract these in "{X}% of SI" format. Do not skip them because they reference a percentage rather than a fixed rupee amount.
13. The Policy Schedule (first/cover page) contains critical identity and eligibility data (UIN, product name, sum insured, insurer name, entry/renewal ages, dependent definitions). Check the Policy Schedule first before looking in body text for these fields.
14. Optional Cover sections (3.11-3.13) and tables labeled "Optional Cover I / II / III" contain benefits NOT listed in main coverage sections. Always check Optional Cover for: maternity, restoration benefit, consumables cover, no proportionate deduction (co-pay waiver). These are easy to miss.
15. When a field value references a regulation without stating the actual number (e.g. "as per IRDAI guidelines", "as per applicable circular"), extract "as_per_irdai" rather than null. This distinguishes regulatory-reference values from genuinely missing data.
"""


def build_pass_prompt(pass_idx: int) -> str:
    """Generate the extraction prompt for a given pass index (0-3)."""
    config = PASS_CONFIG[pass_idx]

    prompt_parts = [
        f"Extract structured insurance policy features from this Indian health insurance policy document.",
        f"\n=== FOCUS: {config['label']} ===",
        f"{config['description']}.",
    ]

    # Add section search hints
    prompt_parts.append(_section_search_hint(config["section_keywords"]))

    # Add document structure reference
    prompt_parts.append(DOCUMENT_STRUCTURE)

    # Add base rules
    prompt_parts.append(BASE_RULES)

    # Add terminology aliases for owned fields
    prompt_parts.append(_build_aliases_section(config["owned_fields"]))

    # Add focused field checklist
    prompt_parts.append("\n=== FIELDS TO EXTRACT IN THIS PASS ===")
    for fp in config["owned_fields"]:
        aliases = FIELD_ALIASES.get(fp, [])
        short = fp.split(".")[-1]
        alias_str = f"  (a.k.a. {', '.join(aliases[:3])})" if aliases else ""
        prompt_parts.append(f"  - {short}{alias_str}")

    # Closing instruction
    prompt_parts.append(
        f"\n\nFor fields not in this pass's scope, leave them as null in the output."
        f"\nOnly populate the fields listed above."
    )

    return "\n".join(prompt_parts)


# Pre-build prompts for all passes
PASS_PROMPTS = [build_pass_prompt(i) for i in range(len(PASS_CONFIG))]
