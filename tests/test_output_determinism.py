import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from healthstream_etl import run_etl


HEADER = ["event_id", "patient_key", "event_date", "encounter_type", "diagnosis_code", "amount_usd"]


class OutputDeterminismTests(unittest.TestCase):
    def test_repeated_runs_produce_byte_identical_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADER)
                writer.writeheader()
                writer.writerows([
                    {
                        "event_id": "b", "patient_key": "p2", "event_date": "2026-02-02",
                        "encounter_type": "Outpatient", "diagnosis_code": "z00.00", "amount_usd": "1.235",
                    },
                    {
                        "event_id": "a", "patient_key": "p1", "event_date": "2026-02-01",
                        "encounter_type": "Inpatient", "diagnosis_code": "a01", "amount_usd": "12.50",
                    },
                ])

            first = root / "first"
            second = root / "second"
            run_etl(source, first)
            run_etl(source, second)

            names = ("cleaned_events.csv", "daily_summary.csv", "quality_report.json")
            for name in names:
                first_bytes = (first / name).read_bytes()
                second_bytes = (second / name).read_bytes()
                self.assertEqual(first_bytes, second_bytes, name)
                self.assertEqual(hashlib.sha256(first_bytes).hexdigest(),
                                 hashlib.sha256(second_bytes).hexdigest(), name)

    def test_header_only_csv_has_stable_zero_row_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "empty.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerow(HEADER)

            output = root / "out"
            report = run_etl(source, output)
            self.assertEqual(report["input_rows"], 0)
            self.assertEqual(report["accepted_rows"], 0)
            self.assertEqual(report["rejected_rows"], 0)
            self.assertEqual(report["rejection_details"], [])
            self.assertEqual((output / "cleaned_events.csv").read_text(encoding="utf-8").strip(),
                             ",".join(HEADER))


if __name__ == "__main__":
    unittest.main()
