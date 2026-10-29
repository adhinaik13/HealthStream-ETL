import csv
import tempfile
import unittest
from pathlib import Path

from healthstream_etl import run_etl


HEADER = ["event_id", "patient_key", "event_date", "encounter_type", "diagnosis_code", "amount_usd"]


class LargeInputTests(unittest.TestCase):
    def test_streams_rows_and_preserves_counts_and_sorted_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "many.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADER)
                writer.writeheader()
                for i in range(10_000):
                    writer.writerow({
                        "event_id": f"event-{i:05d}",
                        "patient_key": f"patient-{i % 100:03d}",
                        "event_date": f"2026-01-{(i % 28) + 1:02d}",
                        "encounter_type": "Outpatient",
                        "diagnosis_code": "z00.00",
                        "amount_usd": "1.25",
                    })

            report = run_etl(source, root / "out")
            self.assertEqual(report["input_rows"], 10_000)
            self.assertEqual(report["accepted_rows"], 10_000)
            self.assertEqual(report["rejected_rows"], 0)
            with (root / "out" / "cleaned_events.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 10_000)
            self.assertEqual(rows[0]["event_date"], "2026-01-01")
            self.assertEqual(rows[-1]["event_date"], "2026-01-28")


if __name__ == "__main__":
    unittest.main()
