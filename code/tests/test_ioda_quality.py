"""Regression tests for national IODA coverage preparation; no network required."""
import csv
import gzip
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_ioda_quality.py"


def load_module():
    if not SCRIPT.exists():
        return None
    spec = importlib.util.spec_from_file_location("ioda_quality", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_series(start, values, *, country="ZZ", signal="ping-slash24", step=600):
    return {"entityType": "country", "entityCode": country, "datasource": signal,
            "from": start, "until": start + len(values) * step,
            "step": step, "nativeStep": step, "values": values}


class QualityTestCase(unittest.TestCase):
    def setUp(self):
        self.ioda = load_module()
        self.assertIsNotNone(self.ioda, "The requested quality implementation does not exist yet")
        self.start, self.until = self.ioda.quarter_bounds(2024, 1)


class QuarterTests(QualityTestCase):
    def test_duplicate_and_conflict_counts_are_independent_of_file_order(self):
        results = []
        for values in set(itertools.permutations((1, 1, 2, 2, 3))):
            agg = self.ioda.QuarterAccumulator(2024, 1)
            for value in values:
                agg.add(make_series(self.start, [value, 0]), "fixture")
            row = agg.row("ZZ", "ping-slash24")
            results.append((row["valid_points"], row["zero_points"],
                            row["conflict_points"], row["duplicate_points"]))
        self.assertEqual(set(results), {(1, 1, 1, 6)})

    def test_null_valid_zero_and_invalid_values_remain_distinct(self):
        for series_order in (([None, 0, -1, float("nan"), None], [4, None, None, None, None]),
                             ([4, None, None, None, None], [None, 0, -1, float("nan"), None])):
            agg = self.ioda.QuarterAccumulator(2024, 1)
            for values in series_order:
                agg.add(make_series(self.start, values), "fixture")
            row = agg.row("ZZ", "ping-slash24")
            self.assertEqual(row["valid_points"], 2)
            self.assertEqual(row["zero_points"], 1)
            self.assertEqual(row["conflict_points"], 0)
            self.assertEqual(row["negative_points"], 1)
            self.assertEqual(row["nonfinite_points"], 1)
            self.assertEqual(row["invalid_only_points"], 2)
            self.assertEqual(row["null_only_points"], 1)
            self.assertEqual(row["absent_points"], row["expected_points"] - 5)
            self.assertEqual(row["duplicate_points"], 0)

    def test_empty_and_missing_series_are_distinct(self):
        agg = self.ioda.QuarterAccumulator(2024, 1)
        empty = make_series(self.start, [])
        empty["until"] = self.until
        agg.add(empty, "empty")
        self.assertEqual(agg.row("ZZ", "ping-slash24")["empty_series"], 1)
        self.assertEqual(agg.row("ZZ", "ping-slash24")["missing_series"], 0)
        self.assertEqual(agg.row("ZZ", "bgp")["missing_series"], 1)

    def test_coarsened_series_and_length_mismatch_are_rejected(self):
        bad_series = make_series(self.start, [1])
        bad_series["nativeStep"] = 300
        bad_length = make_series(self.start, [1])
        bad_length["until"] += 600
        for item, message in ((bad_series, "cadence"), (bad_length, "length")):
            agg = self.ioda.QuarterAccumulator(2024, 1)
            with self.assertRaisesRegex(ValueError, message):
                agg.add(item, "bad")
            row = agg.row("ZZ", "ping-slash24")
            self.assertEqual(row["valid_points"], 0)
            self.assertEqual(row["rejected_series"], 1)

    def test_consistent_native_phase_is_preserved_without_timestamp_snapping(self):
        agg = self.ioda.QuarterAccumulator(2024, 1)
        agg.add(make_series(self.start + 60, [0, 2]), "phase")
        agg.add(make_series(self.until - 540, [3]), "quarter_end")
        row = agg.row("ZZ", "ping-slash24")
        self.assertEqual(row["valid_points"], 3)
        self.assertEqual(row["timestamp_phase_seconds"], "60")
        self.assertEqual(row["expected_points"], 91 * 144)

    def test_full_phase_shifted_quarter_can_clip_until_at_requested_boundary(self):
        agg = self.ioda.QuarterAccumulator(2024, 1)
        source = make_series(self.start + 60, [0] * (91 * 144))
        source["until"] = self.until
        agg.add(source, "phase_clipped")
        row = agg.row("ZZ", "ping-slash24")
        self.assertEqual(row["coverage"], 1)
        self.assertTrue(row["candidate_80pct"])
        self.assertEqual(row["zero_points"], row["expected_points"])

    def test_incompatible_phases_exclude_the_country_signal_quarter(self):
        for phases in ((0, 60), (60, 0)):
            agg = self.ioda.QuarterAccumulator(2024, 1)
            agg.add(make_series(self.start + phases[0], [1]), "first")
            with self.assertRaisesRegex(ValueError, "phase"):
                agg.add(make_series(self.start + phases[1], [2]), "other")
            row = agg.row("ZZ", "ping-slash24")
            self.assertEqual(row["valid_points"], 0)
            self.assertEqual(row["phase_conflict"], 1)
            self.assertEqual(row["timestamp_phase_seconds"], "0;60")

    def test_half_open_quarter_and_year_boundaries_do_not_clip_silently(self):
        agg = self.ioda.QuarterAccumulator(2024, 1)
        agg.add(make_series(self.until - 600, [0]), "last")
        for start in (self.until, self.start - 600):
            with self.assertRaisesRegex(ValueError, "quarter"):
                agg.add(make_series(start, [9]), "spill")
        self.assertEqual(agg.row("ZZ", "ping-slash24")["valid_points"], 1)
        final = self.ioda.QuarterAccumulator(2024, 4)
        _, year_end = self.ioda.quarter_bounds(2024, 4)
        with self.assertRaisesRegex(ValueError, "quarter"):
            final.add(make_series(year_end - 600, [1, 2]), "year_spill")

    def test_values_must_be_numbers_or_null(self):
        for value in ("1", True, {}, []):
            agg = self.ioda.QuarterAccumulator(2024, 1)
            with self.assertRaisesRegex(ValueError, "numeric"):
                agg.add(make_series(self.start, [value]), "bad_value")
            self.assertEqual(agg.row("ZZ", "ping-slash24")["valid_points"], 0)

    def test_integer_precision_loss_cannot_be_mistaken_for_exact_duplicate(self):
        agg = self.ioda.QuarterAccumulator(2024, 1)
        agg.add(make_series(self.start, [2 ** 53]), "exact_float64")
        with self.assertRaisesRegex(ValueError, "precision"):
            agg.add(make_series(self.start, [2 ** 53 + 1]), "inexact_float64")
        self.assertEqual(agg.row("ZZ", "ping-slash24")["duplicate_points"], 0)


class PipelineTests(QualityTestCase):
    def make_archive(self, root, name, series, *, collection="raw_country_batches",
                     year=2024, quarter=1, countries=None, source=None):
        folder = root / "ioda" / collection
        folder.mkdir(parents=True, exist_ok=True)
        start, until = self.ioda.quarter_bounds(year, quarter)
        raw = {"requestParameters": {"from": start, "until": until}, "data": [series]}
        payload = gzip.compress(json.dumps(raw).encode())
        path = folder / (name + ".json.gz")
        path.write_bytes(payload)
        metadata = {"file": str(path.relative_to(root)), "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload), "year": year, "quarter": quarter,
                    "countries": countries or ["ZZ"], "datasource": source}
        meta = folder / (name + ".metadata.json")
        meta.write_text(json.dumps(metadata))
        return path, meta

    def read_rows(self, path):
        with path.open(newline="") as source:
            return list(csv.DictReader(source))

    def test_pipeline_deduplicates_collections_and_uses_full_leap_year(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "data"
            out = Path(temp) / "out"
            source = make_series(self.start, [0, None, 2])
            self.make_archive(root, "one", [source])
            self.make_archive(root, "two", [source], collection="raw_core_signals", source="ping-slash24")
            self.make_archive(root, "ignored_2021", [], year=2021)
            summary = self.ioda.run(root, out)
            self.assertEqual(summary["state"], "completed")
            self.assertEqual(summary.get("pid"), os.getpid())
            self.assertEqual(summary["processed_files"], 2)
            self.assertEqual(summary["total_files"], 2)
            annual = self.read_rows(out / "coverage_annual.csv")
            row = next(r for r in annual if r["year"] == "2024" and r["signal"] == "ping-slash24")
            self.assertEqual(int(row["expected_points"]), 366 * 144)
            self.assertEqual(int(row["valid_points"]), 2)
            self.assertEqual(int(row["duplicate_points"]), 2)
            self.assertEqual(int(row["zero_points"]), 1)
            self.assertAlmostEqual(float(row["coverage"]), 2 / (366 * 144))
            self.assertEqual(row["candidate_80pct"], "False")
            row2023 = next(r for r in annual if r["year"] == "2023" and r["signal"] == "bgp")
            self.assertEqual(int(row2023["expected_points"]), 365 * 288)
            self.assertEqual(int(row2023["valid_points"]), 0)
            first_bytes = (out / "coverage_annual.csv").read_bytes()
            self.ioda.run(root, out)
            self.assertEqual(first_bytes, (out / "coverage_annual.csv").read_bytes())
            self.assertEqual(json.loads((out / "progress.json").read_text())["state"], "completed")
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(len(manifest["files"]), 2)
            self.assertEqual(manifest.get("script_sha256"), hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
            for output in manifest["outputs"]:
                actual = hashlib.sha256((out / output["file"]).read_bytes()).hexdigest()
                self.assertEqual(actual, output["sha256"])

    def test_full_year_80_percent_flag_uses_nonmissing_deduplicated_denominator(self):
        with tempfile.TemporaryDirectory() as temp:
            root, out = Path(temp) / "data", Path(temp) / "out"
            total_valid = 0
            for quarter in (1, 2, 3, 4):
                start, until = self.ioda.quarter_bounds(2024, quarter)
                expected = (until - start) // 600
                valid = int(expected * 0.81)
                total_valid += valid
                source = make_series(start, [0] * valid + [None] * (expected - valid))
                self.make_archive(root, f"q{quarter}", [source, source], quarter=quarter)
            self.ioda.run(root, out)
            row = next(r for r in self.read_rows(out / "coverage_annual.csv")
                       if r["year"] == "2024" and r["signal"] == "ping-slash24")
            self.assertEqual(row["candidate_80pct"], "True")
            self.assertEqual(int(row["valid_points"]), total_valid)
            self.assertEqual(int(row["duplicate_points"]), total_valid)
            self.assertEqual(int(row["zero_points"]), total_valid)
            self.assertAlmostEqual(float(row["coverage"]), total_valid / (366 * 144))

    def test_hash_failure_is_reported_and_original_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root, out = Path(temp) / "data", Path(temp) / "out"
            path, meta = self.make_archive(root, "broken", [make_series(self.start, [7])])
            original = path.read_bytes()
            metadata = json.loads(meta.read_text())
            metadata["sha256"] = "0" * 64
            meta.write_text(json.dumps(metadata))
            summary = self.ioda.run(root, out)
            self.assertFalse(summary["quality_pass"])
            self.assertEqual(summary["failed_files"], 1)
            self.assertIn("SHA256", json.dumps(json.loads((out / "manifest.json").read_text())["errors"]))
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(all(int(r["valid_points"]) == 0 for r in self.read_rows(out / "coverage_annual.csv")))

    def test_request_quarter_and_metadata_country_mismatch_are_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root, out = Path(temp) / "data", Path(temp) / "out"
            self.make_archive(root, "country", [make_series(self.start, [7], country="YY")])
            path, meta = self.make_archive(root, "quarter", [make_series(self.start, [7])])
            raw = json.loads(gzip.decompress(path.read_bytes()))
            raw["requestParameters"]["until"] += 600
            payload = gzip.compress(json.dumps(raw).encode())
            path.write_bytes(payload)
            metadata = json.loads(meta.read_text())
            metadata.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
            meta.write_text(json.dumps(metadata))
            summary = self.ioda.run(root, out)
            self.assertFalse(summary["quality_pass"])
            messages = json.dumps(json.loads((out / "manifest.json").read_text())["errors"])
            self.assertIn("country", messages)
            self.assertIn("quarter", messages)
            self.assertTrue(all(int(r["valid_points"]) == 0 for r in self.read_rows(out / "coverage_annual.csv")))

    def test_missing_input_sets_failed_state_without_stale_completed_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            root, out = Path(temp) / "data", Path(temp) / "out"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "No.*metadata"):
                self.ioda.run(root, out)
            self.assertEqual(json.loads((out / "progress.json").read_text())["state"], "failed")
            self.assertEqual(json.loads((out / "summary.json").read_text())["state"], "failed")


if __name__ == "__main__":
    unittest.main()
