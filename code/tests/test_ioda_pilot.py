import importlib.util
import math
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "scripts" / "build_ioda_pilot.py"
spec = importlib.util.spec_from_file_location("ioda_pilot", str(MODULE))
ioda = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ioda)


def series(start, values, step=600, country="ZZ"):
    return {"entityType": "country", "entityCode": country,
            "entityName": "Test country", "datasource": "ping-slash24",
            "subtype": "", "from": start, "until": start + len(values) * step,
            "step": step, "nativeStep": step, "values": values}


class DailyAggregationTests(unittest.TestCase):
    def test_null_zero_and_nonfinite_are_distinct_full_day_denominator(self):
        agg = ioda.Aggregator(2024, ["ZZ", "YY"])
        start = ioda.utc_epoch("2024-02-29")
        agg.add(series(start, [0, None, 6, float("nan")]), "test")
        rows = {(r["country_code"], r["signal"], r["date_utc"]): r
                for r in agg.daily_rows()}
        row = rows[("ZZ", "ping-slash24", "2024-02-29")]
        self.assertEqual(row["mean_raw"], 3)
        self.assertEqual((row["valid_n"], row["null_n"], row["nonfinite_n"], row["zero_n"]), (2, 1, 1, 1))
        self.assertEqual(row["expected_slots"], 144)
        self.assertEqual(row["absent_slots"], 140)
        self.assertAlmostEqual(row["valid_fraction"], 2 / 144)
        self.assertAlmostEqual(row["missing_fraction"], 142 / 144)
        self.assertEqual(row["zero_fraction_valid"], 0.5)
        missing = rows[("YY", "ping-slash24", "2024-02-29")]
        self.assertIsNone(missing["mean_raw"])
        self.assertEqual(missing["expected_slots"], 144)
        self.assertEqual(missing["valid_fraction"], 0)
        self.assertEqual(missing["denominator_source"], "signal_cadence_inferred_no_country_series")
        self.assertEqual(len(rows), 2 * 3 * 366)

    def test_offset_and_exclusive_quarter_end_and_year_clip(self):
        agg = ioda.Aggregator(2024, ["ZZ"])
        # A 60-second phase offset straddles UTC midnight and leap day.
        start = ioda.utc_epoch("2024-02-29") - 540
        agg.add(series(start, [3, 9]), "offset")
        agg.add(series(ioda.utc_epoch("2024-04-01") - 540, [15]), "q1_end")
        agg.add(series(ioda.utc_epoch("2025-01-01") + 60, [999]), "outside")
        rows = {r["date_utc"]: r for r in agg.daily_rows()
                if r["signal"] == "ping-slash24"}
        self.assertEqual(rows["2024-02-28"]["mean_raw"], 3)
        self.assertEqual(rows["2024-02-29"]["mean_raw"], 9)
        self.assertEqual(rows["2024-03-31"]["mean_raw"], 15)
        self.assertIsNone(rows["2024-04-01"]["mean_raw"])
        self.assertEqual(rows["2024-02-29"]["expected_slots"], 144)
        self.assertEqual(rows["2024-02-29"]["timestamp_phase_seconds"], 60)

    def test_duplicate_identical_deduplicated_conflict_and_partial_overlap_fail(self):
        agg = ioda.Aggregator(2024, ["ZZ"])
        start = ioda.utc_epoch("2024-01-01")
        agg.add(series(start, [1, None, 3]), "a")
        agg.add(series(start, [1, None, 3]), "identical")
        row = next(r for r in agg.daily_rows() if r["signal"] == "ping-slash24")
        self.assertEqual(row["returned_n"], 3)
        self.assertEqual(agg.duplicates[0]["kind"], "identical_segment_deduplicated")
        with self.assertRaisesRegex(ValueError, "conflict"):
            agg.add(series(start, [1, 2, 3]), "conflicting")
        with self.assertRaisesRegex(ValueError, "overlap"):
            agg.add(series(start + 600, [None, 3, 4]), "partial")

    def test_native_step_mismatch_and_irregular_payload_fail(self):
        start = ioda.utc_epoch("2024-01-01")
        agg = ioda.Aggregator(2024, ["ZZ"])
        s = series(start, [1, 2])
        s["nativeStep"] = 300
        with self.assertRaisesRegex(ValueError, "step.*nativeStep"):
            agg.add(s, "downsampled")
        s = series(start, [1, 2])
        s["until"] += 600
        with self.assertRaisesRegex(ValueError, "length"):
            agg.add(s, "truncated")


if __name__ == "__main__":
    unittest.main()
