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

    def test_deduplicates_event_id(self):
        self.write_rows([self.row("same"), self.row("same", amount_usd="99")])
        report = run_etl(self.source, self.output)
        self.assertEqual(report["accepted_rows"], 1)
        self.assertEqual(report["duplicate_rows"], 1)
        stored = json.loads((self.output / "quality_report.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["status"], "completed_with_rejections")

    def test_fails_fast_on_missing_schema(self):
        self.source.write_text("event_id,patient_key\ne1,p1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            run_etl(self.source, self.output)


if __name__ == "__main__":
    unittest.main()
