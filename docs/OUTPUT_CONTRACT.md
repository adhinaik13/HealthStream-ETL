# ETL output contract

The pipeline accepts encounter CSV input and writes three artifacts to the requested output directory:

- `cleaned_events.csv`: normalized accepted records in deterministic sort order.
- `daily_summary.csv`: aggregates grouped by event date and normalized encounter type, with monetary totals represented to two decimal places.
- `quality_report.json`: input, accepted, rejected, and duplicate counts plus row-level rejection reasons.

## Input and validation rules

- The input must have a header and every required column.
- UTF-8 with an optional byte-order mark is accepted.
- Physical CSV data rows are reported using one-based file line numbers (header is line 1).
- Event IDs must be unique after trimming whitespace.
- Dates must be canonical `YYYY-MM-DD` values.
- Amounts must be finite, non-negative decimal numbers. Floating-point arithmetic is not used for money.
- Monetary values are normalized to two decimal places using Python Decimal's default half-even rounding context.

## Operational notes

The current implementation reads the CSV into memory before transforming it. This is appropriate for the included sample, but memory usage grows with input size. For large data sets, use streaming validation and a bounded/disk-backed duplicate-key strategy, while preserving deterministic output and accurate row diagnostics.

Output files are overwritten on each run. Run into a fresh output directory when comparing results or retaining audit artifacts. This is a synthetic educational dataset and is not intended for clinical decision-making.
