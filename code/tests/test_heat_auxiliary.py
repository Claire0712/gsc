import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare_heat_auxiliary.py"


def module():
    assert SCRIPT.exists(), "Auxiliary preparation implementation is missing"
    spec = importlib.util.spec_from_file_location("prepare_heat_auxiliary", SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)


class AuxiliaryTests(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.out = self.root / "out"
        self.crosswalk = [dict(ioda_iso2="AA", ioda_name="Alpha", worldbank_iso3="AAA", worldbank_name="Alpha Republic", mapping_status="exact_iso2_match"),
                          dict(ioda_iso2="BB", ioda_name="Beta", worldbank_iso3="BBB", worldbank_name="Beta", mapping_status="exact_iso2_match"),
                          dict(ioda_iso2="XX", ioda_name="Unmatched", worldbank_iso3="", worldbank_name="", mapping_status="unmatched_needs_review")]
        write_csv(self.data / "metadata/ioda_worldbank_crosswalk.csv", list(self.crosswalk[0]), self.crosswalk)
        self.stop = [dict(start_date_type="Actual", start_date="2022-01-01", end_date="2022-01-02 00:00:00", country="Alpha", geo_scope="It only affected one city, county, or village", area_name="Nationwide", shutdown_type="Shutdown", affected_network="Mobile", shutdown_extent="Full network", shutdown_status="Ended", count_year="2022", other_raw="  preserve me  ")]
        write_csv(self.data / "stop/STOP_combined_2016_2025.csv", list(self.stop[0]), self.stop)
        self.tracks = [dict(SID="storm1", ISO_TIME="2022-01-01 00:00:00", LAT="10", LON="181", SEASON="2022", NAME="Alpha", TRACK_TYPE="main", WMO_WIND=" ", RAW="x")]
        write_csv(self.data / "ibtracs/ibtracs_2018_2025_UTC.csv", list(self.tracks[0]), self.tracks)
        self.wb_fields = ["iso3", "country", "year", "EG.ELC.ACCS.ZS", "IT.NET.USER.ZS", "NY.GDP.PCAP.PP.KD", "SP.POP.TOTL", "SP.URB.TOTL.IN.ZS"]
        self.wb = [dict(zip(self.wb_fields, ["AAA", "Alpha Republic", "2019", "80", "20", "1000", "100", "40"])),
                   dict(zip(self.wb_fields, ["AAA", "Alpha Republic", "2022", "90", "0", "2000", "120", "50"])),
                   dict(zip(self.wb_fields, ["AAA", "Alpha Republic", "2025", "", "80", "", "", ""])),
                   dict(zip(self.wb_fields, ["BBB", "Beta", "2018", "", "10", "", "", ""])),
                   dict(zip(self.wb_fields, ["BBB", "Beta", "2025", "", "50", "", "", ""]))]
        self.write_wb()

    def write_wb(self):
        write_csv(self.data / "worldbank/country_year_indicators_2018_2025.csv", self.wb_fields, self.wb)

    def run_job(self):
        return self.m.prepare(self.data, self.out)

    def rows(self, name):
        with (self.out / name).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_stop_preserves_raw_and_no_national_scope_inference(self):
        self.run_job()
        row = self.rows("stop_cleaned.csv")[0]
        for key, value in self.stop[0].items():
            self.assertEqual(row[key], value)
        self.assertEqual(row["source_row"], "1")
        self.assertEqual(row["normalized_start_date"], "2022-01-01")
        self.assertEqual(row["normalized_end_date"], "2022-01-02")
        self.assertEqual(row["interval_days_inclusive"], "2")
        self.assertEqual(row["normalized_geo_scope"], "single_locality")
        self.assertEqual(row["matched_worldbank_iso3"], "AAA")

    def test_stop_missing_invalid_reversed_and_multiple_country_are_not_imputed(self):
        variants = [dict(end_date="", shutdown_status="Ongoing"), dict(end_date="April/2017 following the inauguration"),
                    dict(end_date="2021-12-31"), dict(country="alpha"), dict(country="Alpha; Beta")]
        records = [dict(self.stop[0], **change) for change in variants]
        write_csv(self.data / "stop/STOP_combined_2016_2025.csv", list(self.stop[0]), records)
        self.run_job()
        rows = self.rows("stop_cleaned.csv")
        for row in rows[:3]:
            self.assertEqual(row["bounded_interval_eligible"], "0")
            self.assertEqual(row["interval_days_inclusive"], "")
        self.assertEqual(rows[0]["normalized_end_date"], "")
        self.assertIn("end_date_missing", rows[0]["qa_flags"])
        self.assertIn("end_date_invalid", rows[1]["qa_flags"])
        self.assertIn("date_range_reversed", rows[2]["qa_flags"])
        self.assertEqual(rows[3]["matched_worldbank_iso3"], "")
        self.assertIn("multiple_countries", rows[4]["qa_flags"])

    def test_ibtracs_utc_longitude_duplicate_conflicts_and_raw_retention(self):
        records = [self.tracks[0], dict(self.tracks[0]), dict(self.tracks[0], LAT="11"),
                   dict(self.tracks[0], SID="storm2", ISO_TIME="2022-01-01T03:00:00+03:00", LON="180"),
                   dict(self.tracks[0], SID="bad", ISO_TIME="not a time", LAT="91", LON="-9999")]
        write_csv(self.data / "ibtracs/ibtracs_2018_2025_UTC.csv", list(self.tracks[0]), records)
        self.run_job()
        rows = self.rows("ibtracs_cleaned.csv")
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["LON"], "181")
        self.assertEqual(float(rows[0]["normalized_longitude"]), -179)
        self.assertEqual(rows[0]["normalized_time_utc"], "2022-01-01T00:00:00Z")
        for row in rows[:3]:
            self.assertEqual(row["duplicate_sid_time"], "1")
            self.assertEqual(row["conflicting_sid_time"], "1")
        self.assertEqual(float(rows[3]["normalized_longitude"]), -180)
        self.assertEqual(rows[3]["normalized_time_utc"], rows[0]["normalized_time_utc"])
        self.assertIn("latitude_invalid", rows[4]["qa_flags"])
        self.assertEqual(rows[4]["normalized_longitude"], "")
        self.assertEqual(rows[0]["normalized_wmo_wind"], "")

    def test_worldbank_share_uses_latest_nonfuture_year_with_lag_at_most_three(self):
        self.run_job()
        rows = {(row["ioda_iso2"], int(row["year"])): row for row in self.rows("worldbank_dlep_2022_2025.csv")}
        self.assertEqual(len(rows), 12)
        self.assertEqual(float(rows["AA", 2022]["internet_share"]), 0)
        self.assertEqual(rows["AA", 2024]["internet_source_year"], "2022")
        self.assertEqual(rows["AA", 2024]["internet_lag_years"], "2")
        self.assertEqual(float(rows["AA", 2025]["internet_share"]), .8)
        self.assertEqual(rows["BB", 2022]["internet_share"], "")
        self.assertEqual(rows["BB", 2024]["internet_share"], "")
        self.assertEqual(rows["XX", 2025]["internet_status"], "unmatched_crosswalk")
        self.assertEqual(rows["AA", 2022]["release_date_known"], "0")

    def test_worldbank_three_year_boundary_and_invalid_percent(self):
        self.wb[1]["IT.NET.USER.ZS"] = "101"
        self.write_wb()
        self.run_job()
        rows = {(r["ioda_iso2"], int(r["year"])): r for r in self.rows("worldbank_dlep_2022_2025.csv")}
        self.assertEqual(float(rows["AA", 2022]["internet_share"]), .2)
        self.assertEqual(rows["AA", 2022]["internet_lag_years"], "3")
        self.assertEqual(rows["AA", 2023]["internet_share"], "")
        clean = self.rows("worldbank_cleaned.csv")
        self.assertIn("internet_percent_out_of_range", clean[1]["qa_flags"])

    def test_worldbank_conflicting_duplicates_are_preserved_and_not_selected(self):
        self.wb.append(dict(self.wb[1], **{"IT.NET.USER.ZS": "99"}))
        self.write_wb()
        self.run_job()
        clean = self.rows("worldbank_cleaned.csv")
        self.assertEqual(len(clean), 6)
        self.assertIn("conflicting_country_year", clean[1]["qa_flags"])
        selected = next(r for r in self.rows("worldbank_dlep_2022_2025.csv") if r["ioda_iso2"] == "AA" and r["year"] == "2022")
        self.assertEqual(selected["internet_source_year"], "2019")

    def test_prior_year_capability_does_not_use_current_year(self):
        self.run_job()
        row = next(r for r in self.rows("worldbank_prior_year_capability_2022_2025.csv") if r["ioda_iso2"] == "AA" and r["year"] == "2022")
        self.assertEqual(row["electricity_access_source_year"], "2019")
        self.assertEqual(float(row["electricity_access_share"]), .8)
        self.assertEqual(row["release_date_known"], "0")

    def test_manifest_source_integrity_summary_and_cli(self):
        original = {p: p.read_bytes() for p in self.data.rglob("*.csv")}
        result = subprocess.run([sys.executable, str(SCRIPT), "--data-root", str(self.data), "--output-dir", str(self.out)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.out / "summary.json").read_text())
        self.assertEqual(summary["state"], "complete")
        self.assertEqual(summary["stop"]["source_rows"], 1)
        self.assertEqual(summary["ibtracs"]["source_rows"], 1)
        self.assertEqual(summary["worldbank"]["dlep_rows"], 12)
        progress = json.loads((self.out / "progress.json").read_text())
        self.assertEqual(progress["state"], "complete")
        self.assertIn("pid", progress)
        self.assertGreater(progress["pid"], 0)
        manifest = json.loads((self.out / "manifest.json").read_text())
        self.assertEqual(len(manifest["inputs"]), 4)
        self.assertEqual(manifest["outputs"]["stop_cleaned.csv"]["sha256"], self.m.sha256(self.out / "stop_cleaned.csv"))
        for path, content in original.items():
            self.assertEqual(path.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
