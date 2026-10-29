import csv
import json
import tempfile
import unittest
from pathlib import Path

from healthstream_etl import run_etl


HEADER = ["event_id", "patient_key", "event_date", "encounter_type", "diagnosis_code", "amount_usd"]


class ValidationEdgeCaseTests(unittest.TestCase):
    def _write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER)
            writer.writeheader()
            writer.writerows(rows)

    def _row(self, event_id: str, amount: str, **overrides: str) -> dict[str, str]:
        row = {
            "event_id": event_id,
            "patient_key": "patient-1",
            "event_date": "2026-01-02",
            "encounter_type": "Outpatient",
            "diagnosis_code": "z00.00",
            "amount_usd": amount,
        }
        row.update(overrides)
        return row

    def test_rejects_non_finite_negative_and_invalid_amounts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.csv"
            self._write_csv(source, [
                self._row("valid", "0"),
                self._row("negative", "-0.01"),
                self._row("nan", "NaN"),
                self._row("infinity", "Infinity"),
                self._row("text", "not-a-number"),
            ])

            report = run_etl(source, root / "out")

            self.assertEqual(report["input_rows"], 5)
            self.assertEqual(report["accepted_rows"], 1)
            self.assertEqual(report["rejected_rows"], 4)
            self.assertEqual(report["status"], "completed_with_rejections")
            self.assertEqual(
                [item["reason"] for item in report["rejection_details"]],
                ["amount_usd must be a finite non-negative number"] * 4,
            )
            with (root / "out" / "cleaned_events.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["event_id"] for row in rows], ["valid"])
            self.assertEqual(rows[0]["amount_usd"], "0.00")

    def test_duplicate_event_id_is_rejected_and_report_is_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.csv"
            self._write_csv(source, [
                self._row("same-id", "10.00"),
                self._row("same-id", "20.00"),
            ])

            report = run_etl(source, root / "out")
            persisted = json.loads((root / "out" / "quality_report.json").read_text(encoding="utf-8"))

            self.assertEqual(report["accepted_rows"], 1)
            self.assertEqual(report["duplicate_rows"], 1)
            self.assertEqual(report["rejected_rows"], 1)
            self.assertEqual(persisted, report)
            self.assertEqual(persisted["rejection_details"][0]["reason"], "duplicate event_id")

    def test_missing_required_header_fails_before_writing_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADER[:-1])
                writer.writeheader()
                writer.writerow({key: "x" for key in HEADER[:-1]})

            with self.assertRaisesRegex(ValueError, "missing required columns: amount_usd"):
                run_etl(source, root / "out")

            self.assertFalse((root / "out" / "cleaned_events.csv").exists())


if __name__ == "__main__":
    unittest.main()
