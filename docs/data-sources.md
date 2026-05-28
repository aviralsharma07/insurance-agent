# Data Sources

Status values: `pending` | `in_progress` | `complete` | `failed`

## Policy Wordings — Tier 1 (Must Have Before Launch)

| # | Insurer | Type | CSR | URL | Status |
|---|---------|------|-----|-----|--------|
| 1 | HDFC ERGO General Insurance | General | ~99.16% | hdfcergo.com/downloads/health-insurance-wordings | pending |
| 2 | Star Health & Allied Insurance | SAHI | ~99%+ | starhealth.in/policy-wordings | pending |
| 3 | Niva Bupa Health Insurance | SAHI | ~92.4% | nivabupa.com/downloads | pending |
| 4 | Care Health Insurance | SAHI | ~95%+ | careinsurance.com/download-center | pending |
| 5 | Aditya Birla Health Insurance | SAHI | ~96%+ | health.adityabirlacapital.com/downloads | pending |
| 6 | Bajaj General Insurance | General | ~96% | bajajgeneralinsurance.com/health-insurance-plans/health-insurance-documents.html | pending |
| 7 | ICICI Lombard General Insurance | General | ~97%+ | icicilombard.com/health-insurance/policy-wordings | pending |
| 8 | Tata AIG General Insurance | General | ~98%+ | tataaig.com/health-insurance/policy-wordings | pending |

## Policy Wordings — Tier 2 (Version 1.1)

| # | Insurer | Type | URL | Status |
|---|---------|------|-----|--------|
| 9 | ManipalCigna Health Insurance | SAHI | manipalcigna.com/downloads | pending |
| 10 | SBI General Insurance | General | sbigeneral.in/portal/health-insurance/downloads | pending |
| 11 | New India Assurance | PSU | newindia.co.in/portal/web/guest/health-insurance-policies | pending |
| 12 | National Insurance Company | PSU | nationalinsurance.nic.co.in/products/health | pending |
| 13 | Oriental Insurance Company | PSU | orientalinsurance.org.in/health-insurance-plans | pending |
| 14 | United India Insurance | PSU | uiic.co.in/health-insurance | pending |
| 15 | Royal Sundaram General Insurance | General | royalsundaram.in/health-insurance/policy-document | pending |

## Policy Wordings — Tier 3 (Version 2.0)

| # | Insurer | Type | URL | Status |
|---|---------|------|-----|--------|
| 16 | Go Digit General Insurance | General | godigit.com/health-insurance/policy-wordings | pending |
| 17 | Acko General Insurance | General | acko.com/health-insurance | pending |
| 18 | IFFCO-Tokio General Insurance | General | iffcotokio.co.in/health-insurance | pending |
| 19 | Reliance General Insurance | General | reliancegeneral.co.in/Insurance/Health-Insurance | pending |
| 20 | Cholamandalam MS General Insurance | General | cholainsurance.com/health-insurance | pending |
| 21 | Future Generali India Insurance | General | futuregenerali.in/insurance-products/health-insurance | pending |
| 22 | Zurich Kotak General Insurance | General | kotakgeneral.com/health-insurance | pending |
| 23 | Liberty General Insurance | General | libertyinsurance.in/health-insurance | pending |
| 24 | Universal Sompo General Insurance | General | universalsompo.com/health-insurance | pending |
| 25 | Narayana Health Insurance | SAHI | narayanainsurance.com | pending |

## IRDAI — Historical Data

| Source | URL | Years Covered | Status |
|--------|-----|---------------|--------|
| IRDAI Annual Reports | https://www.irdai.gov.in/ → Publications → Annual Reports | FY2017-18 to FY2024-25 | complete |
| IRDAI Health Insurance Circulars | https://www.irdai.gov.in/ → Legislation → Circulars → Health | Various | complete |
| IRDAI Health Insurance Regulations | https://www.irdai.gov.in/ → Legislation → Regulations | Various | complete |

### IRDAI Reference Directory Structure

IRDAI reference PDFs are stored in `policy_data/` under:
```
policy_data/_irdai_reference/
  ├── circulars/       — IRDAI health insurance circulars (119 files)
  ├── regulations/     — IRDAI health insurance regulations (4 files)
  ├── reports/         — Annual reports and data tables (20 files)
  └── data/            — Supplementary data files (12 files)
```

## IRDAI — UIN Lifecycle

| Source | URL | Status | Notes |
|--------|-----|--------|-------|
| IRDAI Health Products Listing | irdai.gov.in/health-insurance-products | complete | 1,099 records, 1,082 UIN bases, 32 insurers. Scraped via public listing (intranet XLSX behind firewall). Names normalized. |

## PDF Classification Pipeline

All ~1,067 PDFs in `policy_data/` are classified by `backend/scripts/classify_pdfs.py`.

### Classification Categories

| Category | Count | Description |
|----------|-------|-------------|
| `policy_wording` | 781 | Health insurance policy wording documents (contain UIN) |
| `circular` | 119 | IRDAI circulars and regulations |
| `brochure` | 70 | Product brochures, KIS, prospectuses, or files ≤3 pages |
| `non_health` | 61 | Non-health insurance (PA, motor, travel, etc.) |
| `reference_data` | 32 | IRDAI reports, data tables, supplementary materials |
| `corrupt` | 4 | Files <50KB (likely corrupt or empty) |

### UIN Detection

UINs (Unique Identification Numbers) are extracted from PDF text using a regex pattern of ~90 insurer-specific prefixes. The format is:

```
[3-letter company code][2-letter line of biz][2-3 letter type][3+ digits][optional V+version]
```

Example: `ICIHLIP12345V012020` → ICICI Lombard, Health, Individual Policy, #12345, Version 1

UINs are cross-referenced against `uin_lifecycle.json` to tag status:
- **active** (647): Currently valid policy version
- **superseded** (13): Replaced by a newer version

### UIN Lifecycle Status

IRDAI UIN lifecycle data covers products registered with IRDAI. Of 836 files with detected UINs, 660 match the lifecycle data. The remaining 176 may be older UINs not in the current listing or group/PA products.

### Canonical vs Alternate Sources

When the same UIN exists as both an IRDAI reference copy and a website policy wording, the IRDAI copy is marked as `is_canonical: true`. Currently 41 canonical (IRDAI source) files identified.

### Prune Policy

Files classified as `non_health` or `corrupt` are moved to `policy_data/_pruned/` (never deleted) to reduce storage. 65 files (200.6 MB) are currently pruned.

## Local Data Directory

All downloaded PDFs and extracted data live in `data/` (gitignored). Structure:

```
policy_data/                                        — Source PDFs from scraping
  ├── [01-23]_[insurer_name]/                      — Per-insurer policy wordings (781 files)
  ├── _irdai_reference/                             — IRDAI circulars, regulations, reports
  │   ├── circulars/                                — 119 IRDAI circulars
  │   ├── regulations/                              — 4 IRDAI regulations
  │   ├── reports/                                  — 20 IRDAI annual reports
  │   └── data/                                     — 12 supplementary data files
  └── _pruned/                                      — Non-policy files moved here (65 files, 200.6 MB)
insurance-agent/data/
  ├── uin_lifecycle.json                            — UIN version history (1,099 records)
  ├── policy_index.json                             — Master file index with classifications (1,067 entries)
  ├── classification_report.json                    — PDF audit results summary
  ├── extracted/                                    — Multi-pass extraction JSON output
  └── irdai_historical/                             — Per-year IRDAI report data
```
