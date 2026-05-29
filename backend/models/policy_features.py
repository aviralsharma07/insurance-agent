from pydantic import BaseModel, Field
from typing import Optional, Literal
from typing import Union as TypingUnion


class CoverageInfo(BaseModel):
    sum_insured_range: Optional[str] = Field(
        None,
        description="Range of sum insured options e.g. ₹5L-₹50L or list of discrete options",
    )
    sum_insured_type: Optional[str] = Field(
        None, description="individual, floater, both, or group"
    )
    room_rent_type: Optional[str] = Field(
        None, description="per_day, percentage_of_si, tiered"
    )
    room_rent_limit: Optional[str] = Field(
        None, description="e.g. 2% of SI, ₹5000/day, or tiered by room type"
    )
    icu_limit: Optional[str] = Field(
        None, description="ICU rent limit as amount or % of SI"
    )
    domiciliary_cover: Optional[str] = Field(
        None, description="Domiciliary/hospitalization-at-home cover details"
    )
    day_care_procedures_included: Optional[bool] = Field(
        None, description="Whether day care procedures are covered"
    )
    ambulance_cover: Optional[str] = Field(
        None, description="Ambulance cover amount and type (road/air)"
    )
    pre_hospitalization_days: Optional[int] = Field(
        None, description="Days before hospitalization covered"
    )
    post_hospitalization_days: Optional[int] = Field(
        None, description="Days after discharge covered"
    )


class Deductibles(BaseModel):
    deductible_amount: Optional[str] = Field(
        None, description="Deductible amount if applicable"
    )
    deductible_type: Optional[str] = Field(
        None, description="compulsory, voluntary, none"
    )
    copay_percentage: Optional[float] = Field(None, ge=0, le=100)
    copay_applies_to: Optional[str] = Field(
        None, description="room_rent, all_charges, specific_items"
    )
    copay_conditions: Optional[str] = Field(
        None, description="Age-based, SI-based, zone-based conditions"
    )


class DiseaseWaitingPeriod(BaseModel):
    disease_name: str = Field(..., description="Name of the disease/procedure")
    waiting_months: int = Field(..., ge=0)


class WaitingPeriods(BaseModel):
    # NOTE: field name is pde (not ped) — historical typo, do not rename until full migration
    pde_waiting_months: Optional[int] = Field(
        None, description="Pre-existing disease waiting period in months"
    )
    initial_waiting_period_days: Optional[int] = Field(
        None, description="Initial waiting period in days, typically 30"
    )
    specific_disease_waiting_months: Optional[int] = Field(
        None, description="Default waiting for listed diseases"
    )
    specific_diseases: Optional[list[DiseaseWaitingPeriod]] = Field(
        None, description="Disease-wise waiting periods"
    )
    maternity_waiting_months: Optional[int] = Field(None)
    accident_waiting_days: Optional[int] = Field(
        None, description="Usually 0 for accidents"
    )
    loaded_waiting_days: Optional[int] = Field(
        None, description="Loading waiting period for late entry"
    )


class Maternity(BaseModel):
    covered: Optional[bool] = Field(None)
    waiting_months: Optional[int] = Field(None)
    sum_insured_limit: Optional[str] = Field(
        None, description="Max maternity cover amount or % of SI"
    )
    preconception_days: Optional[int] = Field(
        None, description="Days before delivery covered"
    )
    postnatal_days: Optional[int] = Field(
        None, description="Days after delivery covered"
    )
    newborn_cover: Optional[bool] = Field(None)
    newborn_cover_days: Optional[int] = Field(None)
    vaccination_cover: Optional[bool] = Field(None)
    delivery_types_covered: Optional[str] = Field(
        None, description="normal, C-section, both"
    )
    first_child_limit: Optional[str] = Field(None)
    second_child_limit: Optional[str] = Field(None)


class DiseaseSubLimit(BaseModel):
    item: str = Field(..., description="Procedure, treatment, or disease name")
    limit: str = Field(..., description="Limit expressed as amount or % of SI")


class SubLimits(BaseModel):
    disease_specific: Optional[list[DiseaseSubLimit]] = Field(
        None, description="Sub-limits per disease/procedure"
    )
    surgical_procedures: Optional[list[DiseaseSubLimit]] = Field(
        None, description="Surgical procedure sub-limits"
    )
    annual_health_checkup: Optional[str] = Field(
        None, description="Health checkup benefit limit"
    )
    specific_benefits: Optional[list[str]] = Field(
        None, description="Other specific benefit limits"
    )
    modern_treatment_sub_limits: Optional[list[DiseaseSubLimit]] = Field(
        None, description="Robotic, laser, cataract etc."
    )


class Exclusions(BaseModel):
    permanent_exclusions: Optional[list[str]] = Field(
        None, description="Always excluded items/diseases"
    )
    waiting_period_exclusions: Optional[list[str]] = Field(
        None, description="Excluded during waiting period"
    )
    general_exclusions: Optional[list[str]] = Field(
        None, description="General policy exclusions"
    )
    notes: Optional[str] = Field(
        None, description="Important exclusion notes or caveats"
    )


class NoClaimBonus(BaseModel):
    ncb_type: Optional[str] = Field(
        None,
        description="percentage_increase, sum_insured_increase, both, or cumulative",
    )
    increase_percentage_per_year: Optional[float] = Field(
        None, description="Annual NCB increase %"
    )
    max_ncb_percentage: Optional[float] = Field(None, description="Maximum NCB % cap")
    restoration_benefit: Optional[bool] = Field(
        None, description="Whether sum insured restores after claim"
    )
    restoration_details: Optional[str] = Field(
        None, description="Restoration conditions: unlimited, one_time, same_illness"
    )
    cumulative_bonus_type: Optional[str] = Field(
        None, description="How cumulative bonus accumulates"
    )


class Eligibility(BaseModel):
    min_entry_age_main: Optional[int] = Field(None)
    max_entry_age_main: Optional[int] = Field(None)
    max_renewal_age: Optional[int] = Field(
        None, description="Lifelong / specific age / none"
    )
    min_entry_age_dependent: Optional[int] = Field(None)
    max_entry_age_dependent: Optional[int] = Field(None)
    max_number_of_dependents: Optional[int] = Field(None)
    dependent_relationship_types: Optional[str] = Field(
        None, description="spouse, children, parents, parents_in_law"
    )


class Portability(BaseModel):
    allowed: Optional[bool] = Field(None)
    conditions: Optional[str] = Field(
        None, description="Portability conditions and restrictions"
    )
    waiting_period_waived: Optional[str] = Field(
        None, description="full, partial, none"
    )


class PolicyTerms(BaseModel):
    policy_term_years: Optional[int] = Field(default=1)
    free_look_period_days: Optional[int] = Field(
        None, description="Typically 15 or 30 days"
    )
    grace_period_days: Optional[int] = Field(
        None, description="Grace period for premium payment"
    )
    cancellation_allowed_by_insurer: Optional[str] = Field(
        None, description="Conditions for insurer cancellation"
    )
    cancellation_allowed_by_policyholder: Optional[str] = Field(
        None, description="Conditions for policyholder cancellation"
    )
    refund_on_cancellation: Optional[str] = Field(
        None, description="Refund terms if cancelled"
    )
    reinstatement_period_days: Optional[int] = Field(
        None, description="Days within which policy can be reinstated"
    )
    reinstatement_conditions: Optional[str] = Field(
        None, description="Conditions for reinstatement"
    )
    pro_rata_treatment: Optional[str] = Field(
        None, description="Pro-rata coverage terms"
    )
    location_coverage: Optional[str] = Field(
        None, description="worldwide, india_only, specific_regions"
    )


class Claims(BaseModel):
    claim_intimation_window: Optional[str] = Field(
        None, description="e.g. 24 hours, 72 hours, 7 days"
    )
    cashless_network: Optional[str] = Field(
        None, description="Cashless hospital network details (TPA, network size)"
    )
    reimbursement_allowed: Optional[bool] = Field(None)
    pre_authorization_required: Optional[bool] = Field(None)
    discharge_process: Optional[str] = Field(
        None, description="Discharge formality or TAT details"
    )
    claim_settlement_tat: Optional[str] = Field(
        None, description="Claim settlement turnaround time"
    )
    required_documents_for_claim: Optional[list[str]] = Field(None)


class AdditionalFeatures(BaseModel):
    wellness_benefits: Optional[bool] = Field(None)
    annual_health_checkup: Optional[str] = Field(
        None, description="Free checkup benefit conditions"
    )
    alternative_treatment_cover: Optional[bool] = Field(
        None, description="AYUSH / Homeopathy / Ayurveda coverage"
    )
    alternative_treatment_limit: Optional[str] = Field(
        None, description="Limit on alternative treatments"
    )
    oopd_cover: Optional[str] = Field(
        None, description="Outpatient department cover details"
    )
    dental_cover: Optional[bool] = Field(None)
    optical_cover: Optional[bool] = Field(None)
    organ_donor_expenses: Optional[bool] = Field(
        None, description="Organ donor transplant expenses"
    )
    co_pay_waiver_for_cashless: Optional[bool] = Field(None)
    modern_treatment_cover: Optional[str] = Field(
        None, description="Robotic, laser, laparoscopic, cataract, etc."
    )
    consumables_cover: Optional[bool] = Field(
        None, description="Surgical consumables/implants cover"
    )
    nc_age_load: Optional[str] = Field(
        None, description="New entrant age loading details"
    )


class PolicyFeatures(BaseModel):
    uin: Optional[str] = Field(None, description="Insurance UIN number from document")
    product_name: Optional[str] = Field(
        None, description="Product name as stated in the policy"
    )
    insurer_name: Optional[str] = Field(None, description="Insurance company name")
    network_hospital_count: Optional[int] = Field(
        None, description="Number of network/cashless hospitals available"
    )

    coverage: Optional[CoverageInfo] = None
    deductibles: Optional[Deductibles] = None
    waiting_periods: Optional[WaitingPeriods] = None
    maternity: Optional[Maternity] = None
    sub_limits: Optional[SubLimits] = None
    exclusions: Optional[Exclusions] = None
    no_claim_bonus: Optional[NoClaimBonus] = None
    eligibility: Optional[Eligibility] = None
    portability: Optional[Portability] = None
    policy_terms: Optional[PolicyTerms] = None
    claims: Optional[Claims] = None
    additional_features: Optional[AdditionalFeatures] = None
    confirmed_absent: list[str] = Field(
        default_factory=list,
        description="Fields the model explicitly searched for and confirmed absent from document",
    )


_TOTAL_FIELD_COUNT = None


def _unwrap(ftype):
    origin = getattr(ftype, "__origin__", None)
    if origin is TypingUnion:
        for arg in ftype.__args__:
            if arg is not type(None):
                return arg
    return ftype


def _count_leaf_fields(cls) -> int:
    total = 0
    for fn, fi in cls.model_fields.items():
        if fn == "confirmed_absent":
            continue
        ftype = _unwrap(fi.annotation)
        if getattr(ftype, "__origin__", None) is list:
            total += 1
        elif hasattr(ftype, "model_fields"):
            total += _count_leaf_fields(ftype)
        else:
            total += 1
    return total


def get_total_field_count() -> int:
    global _TOTAL_FIELD_COUNT
    if _TOTAL_FIELD_COUNT is None:
        _TOTAL_FIELD_COUNT = _count_leaf_fields(PolicyFeatures)
    return _TOTAL_FIELD_COUNT


TOTAL_FIELDS = get_total_field_count()
