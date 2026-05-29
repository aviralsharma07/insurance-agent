"""Multi-pass extraction configuration.

Defines 5 focused passes, each targeting a specific section of the policy.
Each pass "owns" certain fields — its values take priority during merge.

The merge follows this priority order:
  Pass 1A (Core Coverage) > Pass 1B (Financial) > Pass 2 (Wait/Excl) > Pass 3 (Mat/Sub) > Pass 4 (Terms)

DOCUMENT STRUCTURE (Indian IRDAI-regulated health insurance):
  Policy Schedule (1st page) — UIN, sum insured, premium, insurer, ages
  Section 1: What We Cover       — Coverage intent
  Section 2: Definitions         — Key terms, including Cumulative Bonus (2.12)
  Section 3: How Much We Reimburse — Limits, NCB, sub-limits, maternity, modern treatments
  Section 4: Exclusions          — Waiting periods (4.1-4.3), permanent exclusions (4.4)
  Section 5: Conditions          — Portability (5.15), cancellation (5.12), claims (5.5-5.17), free look (5.13)
  Annexures                      — Day care procedures, claim forms

IMPORTANT: In Indian insurance, "Cumulative Bonus" (Section 3.10 / Definition 2.12)
IS the No Claim Bonus (NCB). Map it to no_claim_bonus.* fields.
"""

PASS_CONFIG = [
    {
        "name": "core_coverage",
        "label": "Pass 1A: Core Coverage & Policy Identity",
        "description": "Extract policy identity (UIN, product_name, insurer_name from Policy Schedule first page) and core coverage benefits (Section 3: How Much We Reimburse). Check Section 3.1(a-g) for room rent limit (1% of SI/day), ICU limit (2% of SI/day), ambulance (1% of SI). Day care procedures in Annexure I. Domiciliary cover is often explicitly excluded in Section 4.4.17. Also check Optional Cover sections (3.11-3.13) for hidden benefits like No Proportionate Deduction.",
        "section_keywords": [
            "schedule of benefits",
            "summary of coverage",
            "policy schedule",
            "what we cover",
            "section 1",
            "section 3",
            "coverage",
            "benefits",
            "sum insured",
            "sum insured range",
            "room rent",
            "room rent limit",
            "1% of sum insured",
            "ICU",
            "intensive care",
            "ICCU",
            "domiciliary",
            "day care",
            "ambulance",
            "pre hospitalisation",
            "post hospitalisation",
            "network hospital",
            "annexure I",
            "optional cover",
        ],
        "owned_fields": [
            "uin",
            "product_name",
            "insurer_name",
            "network_hospital_count",
            "coverage.sum_insured_range",
            "coverage.sum_insured_type",
            "coverage.room_rent_type",
            "coverage.room_rent_limit",
            "coverage.icu_limit",
            "coverage.domiciliary_cover",
            "coverage.day_care_procedures_included",
            "coverage.ambulance_cover",
            "coverage.pre_hospitalization_days",
            "coverage.post_hospitalization_days",
        ],
    },
    {
        "name": "financial_mechanics",
        "label": "Pass 1B: Financial Mechanics & Eligibility",
        "description": "Extract deductibles (check Section 3 definitions/Schedule — 'insured shall bear' indicates deductible; mark null if policy states 'No Deductible'), co-pay (Section 3.2 — age-based/zone-based/room-differential; mark null if absent), no-claim bonus (Section 3.10 Cumulative Bonus IS the NCB — look for % increase per claim-free year and max cap), restoration benefit (Section 3.11/Optional Cover — sum insured reinstatement on exhaustion), eligibility (Policy Schedule first page — entry/renewal ages, dependent ages and relationships)",
        "section_keywords": [
            "schedule",
            "policy schedule",
            "declaration page",
            "cumulative bonus",
            "deductible",
            "deductible amount",
            "deductible type",
            "co-pay",
            "copayment",
            "co-pay conditions",
            "no claim bonus",
            "NCB",
            "restoration benefit",
            "sum reinstatement",
            "eligibility",
            "who can be covered",
            "entry age",
            "renewal age",
            "maximum age",
            "dependent",
            "family definition",
        ],
        "owned_fields": [
            "deductibles.deductible_amount",
            "deductibles.deductible_type",
            "deductibles.copay_percentage",
            "deductibles.copay_applies_to",
            "deductibles.copay_conditions",
            "no_claim_bonus.ncb_type",
            "no_claim_bonus.increase_percentage_per_year",
            "no_claim_bonus.max_ncb_percentage",
            "no_claim_bonus.restoration_benefit",
            "no_claim_bonus.restoration_details",
            "no_claim_bonus.cumulative_bonus_type",
            "eligibility.min_entry_age_main",
            "eligibility.max_entry_age_main",
            "eligibility.max_renewal_age",
            "eligibility.min_entry_age_dependent",
            "eligibility.max_entry_age_dependent",
            "eligibility.max_number_of_dependents",
            "eligibility.dependent_relationship_types",
        ],
    },
    {
        "name": "waiting_periods_and_exclusions",
        "label": "Pass 2: Waiting Periods & Exclusions",
        "description": "Extract PED waiting (Section 4.1 — typically 24-48 months for pre-existing diseases; check if continuous insurance coverage from previous policy reduces this with proof; unqualified 'PED waiting period' means first 48 months from inception), initial waiting (Section 4.2 — typically 30-90 days from policy inception during which illness not covered; accident/trauma is ALWAYS exempt from initial waiting; verify accident waiting is 0 days), specific disease waiting (Section 4.3 — disease table with multiple tiers: 90-day list includes diabetes/hypertension/cardiac conditions, 24-month list includes cataract/hernia/sinusitis/tonsillitis/gallstone/varicose veins/hydrocele/piles/fistula, 48-month list includes joint replacement/kidney stone/benign prostate hypertrophy; extract EVERY row of this table as a separate array element), moratorium (Section 4.4 or separate clause — IRDAI standard: after 8 continuous years, policy cannot be contested except for fraud/moral hazard/permanent exclusions like war/nuclear; note if moratorium clause is present even if it references IRDAI standard wording), permanent exclusions (Section 4.4 — war/nuclear hazard/cosmetic surgery/weight loss treatment/experimental therapy/self-inflicted injury/sterility/infertility/HIV unless from transfusion/blood products/needle stick/donor organ), loaded waiting for late entry (if entry age > 50-55, additional 12-24 months PED waiting may apply)",
        "section_keywords": [
            "waiting period",
            "pre-existing disease",
            "PED",
            "specific disease",
            "exclusion",
            "what is not covered",
            "general exclusion",
            "permanent exclusion",
            "moratorium",
            "8 continuous years",
        ],
        "owned_fields": [
            "waiting_periods.pde_waiting_months",
            "waiting_periods.initial_waiting_period_days",
            "waiting_periods.specific_disease_waiting_months",
            "waiting_periods.specific_diseases",
            "waiting_periods.maternity_waiting_months",
            "waiting_periods.accident_waiting_days",
            "waiting_periods.loaded_waiting_days",
            "exclusions.permanent_exclusions",
            "exclusions.waiting_period_exclusions",
            "exclusions.general_exclusions",
            "exclusions.notes",
        ],
    },
    {
        "name": "maternity_sublimits_addons",
        "label": "Pass 3: Maternity, Sub-limits & Additional Features",
        "description": "Extract maternity benefits (Section 3.5-3.7 or Optional Cover 3.11-3.13 — 'maternity optional cover' often treated as separate add-on. Check: covered=true/false, waiting 9-36 months, sub-limit ₹25K-₹100K or '10% of average SI', covers first two children only with per-child caps, pre-conception 30-90 days covered, postnatal 60-90 days covered, newborn cover 'from day 1 till policy expiry', vaccination cover included. If maternity not mentioned anywhere → mark covered=false + add to confirmed_absent), disease/treatment sub-limits (Section 3 How Much We Reimburse or Schedule tables — expressed as '% of Sum Insured' e.g. '10% of SI for Cataract/Stone', '20% of SI for Joint Replacement/Prostate', '25% of SI for Cardiac/Neurological', '5% of SI for Hernia/Appendicitis'. Extract EVERY row as a separate DiseaseSubLimit element with item name and limit string. This is critical — most Indian policies have sub-limit tables with 8-15+ items), AYUSH cover (Section 3.4 or Schedule — typically 'Covered as per IRDAI guidelines' with 10-25% of SI sub-limit, requires treatment in recognized AYUSH hospital; if not mentioned → check permanent exclusions for AYUSH exclusion), modern treatments (Section 3.15 — robotic surgery, HIFU, radiofrequency ablation, oral chemotherapy, immunotherapy, brachytherapy, stereotactic radiosurgery, laser treatment; often with per-procedure sub-limits or 'as per schedule of benefits'), annual health checkup (every 2-5 years after a claim-free year, sub-limit ₹1K-₹5K; 'once in every 2 years' or 'once in 4 years after no claim'), OPD/dental/optical (often explicitly EXCLUDED in Section 4.4 — if stated as excluded, set cover=false; if not mentioned at all, leave null), consumables cover (surgical implants/prosthetics/pacemakers — newer IRDAI-compliant policies cover these; older policies may be silent → leave null), organ donor expenses (typically covered as part of transplant treatment; donor's medical expenses reimbursed up to actuals within SI limit), co-pay waiver for cashless (Optional Cover — 'No Proportionate Deduction in Network Hospital' means co-pay waived if treated in network)",
        "section_keywords": [
            "maternity",
            "delivery",
            "childbirth",
            "newborn",
            "sub-limit",
            "sub limit",
            "disease sub-limit",
            "surgical limit",
            "procedure limit",
            "specific procedure",
            "additional cover",
            "AYUSH",
            "AYUSH cover",
            "alternative treatment",
            "OPD",
            "health checkup",
            "wellness",
            "modern treatment",
            "robotic surgery",
            "consumables",
            "organ donor",
        ],
        "owned_fields": [
            "maternity.covered",
            "maternity.waiting_months",
            "maternity.sum_insured_limit",
            "maternity.preconception_days",
            "maternity.postnatal_days",
            "maternity.newborn_cover",
            "maternity.newborn_cover_days",
            "maternity.vaccination_cover",
            "maternity.delivery_types_covered",
            "maternity.first_child_limit",
            "maternity.second_child_limit",
            "sub_limits.disease_specific",
            "sub_limits.surgical_procedures",
            "sub_limits.annual_health_checkup",
            "sub_limits.specific_benefits",
            "sub_limits.modern_treatment_sub_limits",
            "additional_features.wellness_benefits",
            "additional_features.annual_health_checkup",
            "additional_features.alternative_treatment_cover",
            "additional_features.alternative_treatment_limit",
            "additional_features.oopd_cover",
            "additional_features.dental_cover",
            "additional_features.optical_cover",
            "additional_features.organ_donor_expenses",
            "additional_features.co_pay_waiver_for_cashless",
            "additional_features.modern_treatment_cover",
            "additional_features.consumables_cover",
            "additional_features.nc_age_load",
        ],
    },
    {
        "name": "policy_terms_and_claims",
        "label": "Pass 4: Policy Terms & Claims",
        "description": "Extract policy term (Section 5 or Policy Schedule — usually 1 year; some policies offer 2/3 year multi-year options with premium lock-in), free look period (Section 5.13 — standard 15 days from date of receipt of policy document; 30 days for distance marketing/e-commerce policies; policyholder can return policy for full refund minus stamp duty and medical exam cost), grace period (Section 5.11 or premium clause — 15 days for monthly premium mode, 30 days for quarterly/half-yearly/yearly; policy lapses if premium unpaid after grace; no cover during grace period if earlier policy lapsed), portability (Section 5.15 — allowed under IRDAI portability regulations; request must be made 45 days before renewal date; waiting period credits transfer from previous insurer; continuity benefit — completed waiting periods are preserved; portability cannot be denied on health condition grounds), cancellation by insurer (Section 5.12 — can cancel only for fraud/non-disclosure/misrepresentation/proliferation of claims; 15 days written notice; refund of unearned premium on pro-rata basis), cancellation by policyholder (any time during policy term; refund at short period scale: 1/4th annual rate if cancelled within 1 month, 1/2 if within 3 months, 3/4th if within 6 months, no refund after 6 months), claims intimation (Section 5.5-5.7 — planned hospitalization: TPA informed 48-96 hours before admission; emergency: TPA informed within 24-48 hours of admission; post-discharge reimbursement: documents submitted within 7-15 days of discharge), claim settlement TAT (IRDAI mandate — insurer must settle within 30 days of receipt of last document if no investigation needed; within 45 days if investigation required; if delayed, interest payable at 2% above bank rate), cashless network (TPA name and network size — 'NIA network of 7000+ hospitals' or specific TPA like 'Medsave', 'Paramount', 'Vidal'; network information may be in separate document or Annexure), reinstatement of lapsed policy (within 30 consecutive days of expiry; with payment of outstanding premium; fresh PED waiting may be imposed for break in coverage), location_coverage (policy territory — 'treatment within India only' for domestic policies; 'worldwide cover' for international policies; Indian policies typically cover India only, Nepal and Bhutan are sometimes included)",
        "section_keywords": [
            "policy terms",
            "terms and conditions",
            "policy conditions",
            "free look",
            "grace period",
            "cancellation",
            "refund",
            "reinstatement",
            "portability",
            "migration",
            "claim",
            "claim procedure",
            "claim intimation",
            "cashless",
            "reimbursement",
            "claim documents",
            "pre-authorisation",
            "preauthorization",
        ],
        "owned_fields": [
            "portability.allowed",
            "portability.conditions",
            "portability.waiting_period_waived",
            "policy_terms.policy_term_years",
            "policy_terms.free_look_period_days",
            "policy_terms.grace_period_days",
            "policy_terms.cancellation_allowed_by_insurer",
            "policy_terms.cancellation_allowed_by_policyholder",
            "policy_terms.refund_on_cancellation",
            "policy_terms.reinstatement_period_days",
            "policy_terms.reinstatement_conditions",
            "policy_terms.pro_rata_treatment",
            "policy_terms.location_coverage",
            "claims.claim_intimation_window",
            "claims.cashless_network",
            "claims.reimbursement_allowed",
            "claims.pre_authorization_required",
            "claims.discharge_process",
            "claims.claim_settlement_tat",
            "claims.required_documents_for_claim",
        ],
    },
]


def get_all_owned_fields() -> set:
    """Return set of all field paths owned across all passes (no duplicates)."""
    seen = set()
    for p in PASS_CONFIG:
        for f in p["owned_fields"]:
            seen.add(f)
    return seen


def get_pass_for_field(field_path: str) -> int:
    """Return the pass index (0-3) that owns a given field path."""
    for i, p in enumerate(PASS_CONFIG):
        if field_path in p["owned_fields"]:
            return i
    return -1
