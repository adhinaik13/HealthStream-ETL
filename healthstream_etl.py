#!/usr/bin/env python3
"""ETL for synthetic healthcare encounter events; standard library only."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = (
    "event_id", "patient_key", "event_date",
    "encounter_type", "diagnosis_code", "amount_usd",
)
CLEAN_COLUMNS = REQUIRED_COLUMNS


def _normalize(row: dict[str, str], row_number: int) -> tuple[dict[str, str] | None, str | None]:
    missing = [key for key in REQUIRED_COLUMNS if key not in row]
    if missing:
        return None, "missing required columns: " + ", ".join(missing)
    event_id = (row.get("event_id") or "").strip()
    patient_key = (row.get("patient_key") or "").strip()
    encounter_type = (row.get("encounter_type") or "").strip().lower()
    diagnosis_code = (row.get("diagnosis_code") or "").strip().upper()
    raw_date = (row.get("event_date") or "").strip()
    raw_amount = (row.get("amount_usd") or "").strip()

    if not event_id:
        return None, "event_id is empty"
    if not patient_key:
        return None, "patient_key is empty"
    if not encounter_type:
        return None, "encounter_type is empty"
    if not diagnosis_code:
        return None, "diagnosis_code is empty"
    try:
        event_date = date.fromisoformat(raw_date)
        if event_date.isoformat() != raw_date:
            return None, "event_date must use YYYY-MM-DD"
    except ValueError:
        return None, "event_date must use YYYY-MM-DD"
    try:
        amount = Decimal(raw_amount)
    except (InvalidOperation, ValueError):
        return None, "amount_usd must be a finite non-negative number"
    if not amount.is_finite() or amount < 0:
        return None, "amount_usd must be a finite non-negative number"
    try:
        normalized_amount = amount.quantize(Decimal("0.01"))
    except InvalidOperation:
        return None, "amount_usd is outside the supported numeric range"

    return {
        "event_id": event_id,
        "patient_key": patient_key,
        "event_date": event_date.isoformat(),
        "encounter_type": encounter_type,
        "diagnosis_code": diagnosis_code,
        "amount_usd": format(normalized_amount, "f"),
    }, None


def run_etl(input_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Transform input CSV and write cleaned events, summary, and quality report."""
    source = Path(input_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    with source.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Input CSV is empty or has no header")
        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError("Input CSV missing required columns: " + ", ".join(missing))
        input_rows = list(reader)

    accepted: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    rejected: list[dict[str, Any]] = []
    duplicate_count = 0

    for row_number, row in enumerate(input_rows, start=2):
        normalized, error = _normalize(row, row_number)
        if error:
            rejected.append({"row": row_number, "reason": error})
            continue
        assert normalized is not None
        if normalized["event_id"] in seen_ids:
            duplicate_count += 1
            rejected.append({"row": row_number, "reason": "duplicate event_id"})
            continue
        seen_ids.add(normalized["event_id"])
        accepted.append(normalized)

    accepted.sort(key=lambda item: (item["event_date"], item["encounter_type"], item["event_id"]))
    with (destination / "cleaned_events.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CLEAN_COLUMNS)
        writer.writeheader()
        writer.writerows(accepted)

    aggregates: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"encounter_count": 0, "total_amount_usd": Decimal("0.00")}
    )
    for event in accepted:
        group = (event["event_date"], event["encounter_type"])
        aggregates[group]["encounter_count"] += 1
        aggregates[group]["total_amount_usd"] += Decimal(event["amount_usd"])

    with (destination / "daily_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ("event_date", "encounter_type", "encounter_count", "total_amount_usd")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for (event_date, encounter_type), values in sorted(aggregates.items()):
            writer.writerow({
                "event_date": event_date,
                "encounter_type": encounter_type,
                "encounter_count": values["encounter_count"],
                "total_amount_usd": format(values["total_amount_usd"], ".2f"),
            })

    report = {
        "input_file": source.name,
        "input_rows": len(input_rows),
        "accepted_rows": len(accepted),
        "rejected_rows": len(rejected),
        "duplicate_rows": duplicate_count,
        "rejection_details": rejected,
        "status": "success" if not rejected else "completed_with_rejections",
    }
    (destination / "quality_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to source encounter CSV")
    parser.add_argument("--output-dir", required=True, help="Directory for ETL outputs")
    args = parser.parse_args()
    report = run_etl(args.input, args.output_dir)
    print(json.dumps({key: value for key, value in report.items() if key != "rejection_details"}, indent=2))


if __name__ == "__main__":
    main()
