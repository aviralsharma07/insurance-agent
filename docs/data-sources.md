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
| IRDAI Annual Reports | irdai.gov.in → Publications → Annual Reports | FY2017-18 to FY2024-25 | pending |

## IRDAI — UIN Lifecycle

| Source | URL | Status | Notes |
|--------|-----|--------|-------|
| IRDAI Health Products Listing | irdai.gov.in/health-insurance-products | complete | 1,099 records, 1,082 UIN bases, 32 insurers. Scraped via public listing (intranet XLSX behind firewall). Names normalized. |

## Local Data Directory

All downloaded PDFs and extracted data live in `data/` (gitignored). Structure:

```
policy_data/                  — Source PDFs from scraping
  └── [insurer_name]/         — Per-insurer folders
_irdai_reference/             — IRDAI circulars and regulations
data/
  ├── uin_lifecycle.json      — UIN version history
  ├── irdai_historical/       — Per-year IRDAI report data
  ├── classification_report.json — PDF audit results
  ├── policy_index.json       — Master file index with classifications
  ├── extracted/              — Multi-pass extraction JSON output
  └── _pruned/                — Non-policy files moved here (never deleted)
```
