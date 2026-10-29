import csv
import json
import tempfile
import unittest
from pathlib import Path

from healthstream_etl import run_etl


HEADER = ["event_id", "patient_key", "event_date", "encounter_type", "diagnosis_code", "amount_usd"]


class HealthStreamETLTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "input.csv"
        self.output = self.root / "out"

    def tearDown(self):
        self.temp.cleanup()

    def write_rows(self, rows):
        with self.source.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER)
            writer.writeheader()
            writer.writerows(rows)

    def row(self, event_id="e1", **updates):
        item = dict(event_id=event_id, patient_key="p1", event_date="2026-01-02",
                    encounter_type="Outpatient", diagnosis_code="z00.00", amount_usd="10")
        item.update(updates)
        return item

    def test_normalizes_and_aggregates(self):
        self.write_rows([self.row("e1"), self.row("e2", amount_usd="2.5", encounter_type="OUTPATIENT")])
        report = run_etl(self.source, self.output)
        self.assertEqual(report["accepted_rows"], 2)
        with (self.output / "cleaned_events.csv").open(encoding="utf-8") as handle:
            events = list(csv.DictReader(handle))
        self.assertEqual(events[0]["encounter_type"], "outpatient")
        with (self.output / "daily_summary.csv").open(encoding="utf-8") as handle:
            summary = list(csv.DictReader(handle))
        self.assertEqual(summary[0]["encounter_count"], "2")
        self.assertEqual(summary[0]["total_amount_usd"], "12.50")

    def test_rejects_invalid_amount_and_date(self):
        self.write_rows([self.row("e1", amount_usd="-1"), self.row("e2", event_date="yesterday")])
        report = run_etl(self.source, self.output)
        self.assertEqual(report["accepted_rows"], 0)
        self.assertEqual(report["rejected_rows"], 2)

    def test_rejects_amount_outside_decimal_range_without_crashing(self):
        self.write_rows([self.row("e1", amount_usd="1e999999999999999999")])
        report = run_etl(self.source, self.output)
        self.assertEqual(report["accepted_rows"], 0)
        self.assertEqual(report["rejected_rows"], 1)
        self.assertIn("supported numeric range", report["rejection_details"][0]["reason"])

    def test_deduplicates_event_id(self):
        self.write_rows([self.row("same"), self.row("same", amount_usd="99")])
        report = run_etl(self.source, self.output)
        self.assertEqual(report["accepted_rows"], 1)
        self.assertEqual(report["duplicate_rows"], 1)
        stored = json.loads((self.output / "quality_report.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["status"], "completed_with_rejections")

    def test_rejects_empty_identifiers_and_non_finite_amounts(self):
        self.write_rows([
            self.row(" ", patient_key="p2"),
            self.row("e2", patient_key="  "),
            self.row("e3", amount_usd="NaN"),
            self.row("e4", amount_usd="Infinity"),
        ])
        report = run_etl(self.source, self.output)
        self.assertEqual(report["accepted_rows"], 0)
        self.assertEqual(report["rejected_rows"], 4)

    def test_normalizes_money_to_cents_and_sorts_output(self):
        self.write_rows([
            self.row("z", event_date="2026-01-03", amount_usd="1.235"),
            self.row("a", event_date="2026-01-01", amount_usd="2"),
        ])
        report = run_etl(self.source, self.output)
        self.assertEqual(report["accepted_rows"], 2)
        with (self.output / "cleaned_events.csv").open(newline="", encoding="utf-8") as handle:
            events = list(csv.DictReader(handle))
        self.assertEqual([event["event_id"] for event in events], ["a", "z"])
        self.assertEqual(events[1]["amount_usd"], "1.24")

    def test_empty_dataset_produces_header_only_outputs_and_zero_counts(self):
        self.write_rows([])
        report = run_etl(self.source, self.output)
        self.assertEqual(report["input_rows"], 0)
        self.assertEqual(report["accepted_rows"], 0)
        self.assertEqual(report["rejected_rows"], 0)
        self.assertEqual(report["status"], "success")
        with (self.output / "cleaned_events.csv").open(newline="", encoding="utf-8") as handle:
            self.assertEqual(list(csv.DictReader(handle)), [])
        with (self.output / "daily_summary.csv").open(newline="", encoding="utf-8") as handle:
            self.assertEqual(list(csv.DictReader(handle)), [])

    def test_rejection_report_uses_source_row_numbers(self):
        self.write_rows([self.row("valid"), self.row("bad", event_date="not-a-date")])
        report = run_etl(self.source, self.output)
        self.assertEqual(report["accepted_rows"], 1)
        self.assertEqual(report["rejection_details"], [
            {"row": 3, "reason": "event_date must use YYYY-MM-DD"}
        ])

    def test_money_rounding_uses_decimal_half_even_at_ties(self):
        self.write_rows([
            self.row("odd-cent", amount_usd="1.235"),
            self.row("even-cent", amount_usd="1.245"),
        ])
        report = run_etl(self.source, self.output)
        self.assertEqual(report["accepted_rows"], 2)
        with (self.output / "cleaned_events.csv").open(newline="", encoding="utf-8") as handle:
            amounts = {row["event_id"]: row["amount_usd"] for row in csv.DictReader(handle)}
        self.assertEqual(amounts, {"odd-cent": "1.24", "even-cent": "1.24"})

    def test_fails_fast_on_missing_schema(self):
        self.source.write_text("event_id,patient_key\ne1,p1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            run_etl(self.source, self.output)


if __name__ == "__main__":
    unittest.main()
