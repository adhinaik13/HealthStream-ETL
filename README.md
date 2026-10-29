# HealthStream ETL

A small, testable Python ETL pipeline for **synthetic healthcare encounter events**. It demonstrates ingestion, validation, normalization, duplicate handling, deterministic aggregation, quality reporting, and CI without using real patient information.

> **Data safety:** every row in `data/sample_encounters.csv` is fabricated. Do not use real patient data in this demo. This is an educational project, not a clinical or billing system.

## Pipeline

```text
CSV source
  -> schema and value validation
  -> normalize dates, categories and amounts
  -> deduplicate by event_id
  -> cleaned_events.csv
  -> daily_summary.csv + quality_report.json
```

## Requirements

Python 3.10+; the pipeline uses only the Python standard library.

## Run

```bash
python healthstream_etl.py --input data/sample_encounters.csv --output-dir output
python -m unittest discover -s tests -v
```

The output directory contains:
- `cleaned_events.csv`: normalized, valid, unique events.
- `daily_summary.csv`: encounter count and total amount grouped by date and encounter type.
- `quality_report.json`: input, accepted, rejected, duplicate counts and row-level rejection reasons.

## Validation rules

- Required columns: `event_id`, `patient_key`, `event_date`, `encounter_type`, `diagnosis_code`, `amount_usd`.
- Event IDs and patient keys must be non-empty.
- Dates must use ISO `YYYY-MM-DD`.
- Amounts must be finite and non-negative; values are rounded to two decimal places using Python Decimal’s default `ROUND_HALF_EVEN` rule. Tests cover halfway rounding values, empty datasets, and source-row diagnostics.
- Repeated event IDs are counted as duplicates and only the first valid occurrence is retained.
- Invalid records are excluded and reported; the pipeline does not silently coerce invalid values.
- Duplicate header names fail fast; rows with surplus fields are rejected with their source row number, and malformed CSV quoting fails rather than being silently accepted.

## Design choices

- Deterministic output ordering to make runs reproducible.
- Monetary rounding uses Decimal arithmetic and the documented half-even rule to avoid binary floating-point aggregation drift.
- Standard-library implementation keeps setup lightweight.
- Synthetic pseudonymous keys only; no names, addresses, dates of birth, or other direct identifiers.
- Rejected rows are summarized by input row number and reason, not copied into the output report.
- This is a portfolio demonstration. It does not claim HIPAA compliance, production-grade security, real EHR integration, or clinical validity.

## Project structure

```text
healthstream-etl/
├── .github/workflows/ci.yml
├── data/sample_encounters.csv
├── healthstream_etl.py
├── tests/test_healthstream_etl.py
└── README.md
```

## CI

GitHub Actions runs the unit tests and a sample end-to-end pipeline check on pushes and pull requests.
