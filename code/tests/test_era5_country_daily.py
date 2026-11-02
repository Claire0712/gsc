"""Numerical and end-to-end checks for the bounded ERA5 country-day job."""
import datetime as dt
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from scipy import sparse

try:
    from netCDF4 import Dataset
except ImportError:
    # Exercise real HDF5 files locally without installing a second reader.
    from h5netcdf.legacyapi import Dataset

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/aggregate_era5_country_daily.py"


def module():
    # A missing implementation is an intentional assertion in the first red run.
    assert SCRIPT.exists(), "ERA5 country-day implementation is not present"
    spec = importlib.util.spec_from_file_location("era5_country_daily", SCRIPT)
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


class DailyMathTests(unittest.TestCase):
    def setUp(self):
        self.m = module()

    def test_pixel_extrema_precede_population_weighting(self):
        temperature = np.full((24, 1, 2), 283.15)
        temperature[0, 0] = [273.15, 293.15]
        temperature[1, 0] = [293.15, 273.15]
        daily = self.m.daily_statistics(temperature, np.arange(24), 1, "t2m")
        weights = sparse.csr_matrix([[0.25, 0.75]])
        result = self.m.weighted_statistics(weights, daily)
        self.assertAlmostEqual(result["tmin_c"][0, 0], 0.0, places=4)
        self.assertAlmostEqual(result["tmax_c"][0, 0], 20.0, places=4)
        self.assertEqual(result["valid_fraction"][0, 0], 1)

    def test_dewpoint_is_daily_mean_then_weighted(self):
        values = np.empty((24, 1, 2))
        values[:, 0, 0] = 273.15 + np.arange(24)
        values[:, 0, 1] = 283.15 + np.arange(24)
        daily = self.m.daily_statistics(values, np.arange(24), 1, "d2m")
        result = self.m.weighted_statistics(sparse.csr_matrix([[0.25, 0.75]]), daily)
        self.assertAlmostEqual(result["dewpoint_c"][0, 0], 19, places=4)

    def test_missing_cell_invalidates_country_without_renormalization(self):
        values = np.full((24, 1, 2), 283.15)
        values[7, 0, 1] = np.nan
        daily = self.m.daily_statistics(values, np.arange(24), 1, "t2m")
        result = self.m.weighted_statistics(sparse.csr_matrix([[0.25, 0.75], [1, 0]]), daily)
        self.assertTrue(np.isnan(result["tmin_c"][0, 0]))
        self.assertEqual(result["valid_fraction"][0, 0], .25)
        self.assertAlmostEqual(result["tmin_c"][0, 1], 10, places=4)

    def test_even_tiny_positive_missing_weight_invalidates(self):
        values = np.full((24, 1, 2), 283.15)
        values[0, 0, 1] = np.inf
        daily = self.m.daily_statistics(values, np.arange(24), 1, "t2m")
        result = self.m.weighted_statistics(sparse.csr_matrix([[1 - 1e-14, 1e-14]]), daily)
        self.assertTrue(np.isnan(result["tmax_c"][0, 0]))

    def test_masked_values_missing_hours_and_missing_days_remain_nan(self):
        values = np.ma.array(np.full((47, 1, 2), 283.15), mask=False)
        values.mask[0, 0, 0] = True
        # Hour 30 is absent, and the entire third day is absent.
        slots = np.delete(np.arange(48), 30)
        daily = self.m.daily_statistics(values, slots, 3, "d2m")
        result = self.m.weighted_statistics(sparse.eye(2, format="csr"), daily)
        self.assertTrue(np.isnan(result["dewpoint_c"][0, 0]))
        self.assertAlmostEqual(result["dewpoint_c"][0, 1], 10, places=4)
        self.assertTrue(np.isnan(result["dewpoint_c"][1:]).all())
        np.testing.assert_array_equal(result["valid_fraction"][1:], 0)

    def test_zero_population_has_no_values_or_coverage(self):
        daily = self.m.daily_statistics(np.full((24, 1, 1), 283.15), np.arange(24), 1, "t2m")
        result = self.m.weighted_statistics(sparse.csr_matrix((1, 1)), daily)
        self.assertTrue(np.isnan(result["tmin_c"]).all())
        self.assertTrue(np.isnan(result["valid_fraction"]).all())

    def test_kelvin_required(self):
        self.m.validate_temperature_units("K")
        self.m.validate_temperature_units("kelvin")
        with self.assertRaisesRegex(ValueError, "Kelvin"):
            self.m.validate_temperature_units("degree_Celsius")


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.m = module()

    def test_month_partition_preserves_year_change_and_leap_day(self):
        self.assertEqual(list(self.m.months_between("202312", "202402")), ["202312", "202401", "202402"])
        self.assertEqual(self.m.month_dates("202402")[-1], "2024-02-29")
        self.assertEqual(len(self.m.month_dates("202302")), 28)

    def test_cf_time_maps_hours_and_retains_a_gap(self):
        origin = dt.datetime(1970, 1, 1)
        start = (dt.datetime(2024, 2, 1) - origin).total_seconds()
        slots = self.m.hour_slots([start, start + 7200], "seconds since 1970-01-01", "proleptic_gregorian", "202402")
        np.testing.assert_array_equal(slots, [0, 2])

    def test_bad_calendar_duplicate_unsorted_offhour_and_out_of_month_rejected(self):
        for times, units, calendar in [
            ([0], "hours since 2024-02-01", "360_day"),
            ([0, 0], "hours since 2024-02-01", "standard"),
            ([2, 1], "hours since 2024-02-01", "standard"),
            ([.5], "hours since 2024-02-01", "standard"),
            ([696], "hours since 2024-02-01", "standard"),
            ([float("nan")], "hours since 2024-02-01", "standard"),
        ]:
            with self.subTest(times=times, calendar=calendar), self.assertRaises(ValueError):
                self.m.hour_slots(times, units, calendar, "202402")


class MonthlyJobTests(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.weights_path = self.root / "weights.npz"
        self.csv_path = self.root / "country_metadata.csv"
        self.grid_path = self.root / "weights_metadata.json"
        sparse.save_npz(self.weights_path, sparse.csr_matrix([[.25, .75, 0, 0], [0, 0, .5, .5], [0, 0, 0, 0]]))
        self.csv_path.write_text("country_id,total_population,country_name\n001,100,Alpha\n002,200,Beta\n003,0,Empty\n")
        grid = {"latitude": [1., 0.], "longitude": [10., 11.], "shape": [2, 2], "flatten_order": "C"}
        for key in ("latitude", "longitude"):
            grid[key + "_sha256"] = hashlib.sha256(np.asarray(grid[key], dtype="<f8").tobytes()).hexdigest()
        self.grid_path.write_text(json.dumps({"schema_version": 1, "grid": grid}))

    def bundle(self):
        self.assertTrue(hasattr(self.m, "load_weight_bundle"), "Weight input validation is not implemented")
        return self.m.load_weight_bundle(self.weights_path, self.csv_path, self.grid_path)

    def make_nc(self, month="202402", missing_hour=False, units="K", reverse_lat=False):
        slots = np.arange(len(self.m.month_dates(month)) * 24)
        if missing_hour:
            slots = np.delete(slots, 30)
        path = self.root / f"era5_2m_{month}.nc"
        with Dataset(path, "w") as dataset:
            for dim, size in (("valid_time", len(slots)), ("latitude", 2), ("longitude", 2)):
                dataset.createDimension(dim, size)
            time = dataset.createVariable("valid_time", "i8", ("valid_time",))
            time.units = f"hours since {month[:4]}-{month[4:]}-01 00:00:00"
            time.calendar = "proleptic_gregorian"
            time[:] = slots
            lat = dataset.createVariable("latitude", "f8", ("latitude",))
            lat[:] = [0, 1] if reverse_lat else [1, 0]
            lon = dataset.createVariable("longitude", "f8", ("longitude",))
            lon[:] = [10, 11]
            for name in ("t2m", "d2m"):
                var = dataset.createVariable(name, "f4", ("valid_time", "latitude", "longitude"), fill_value=-9999.)
                var.units = units
                values = np.full((len(slots), 2, 2), 283.15, dtype=np.float32)
                if name == "t2m":
                    values[:, 0, 1] = 293.15
                    values[slots % 24 == 0, 0, :] = [273.15, 303.15]
                    values[slots % 24 == 1, 0, :] = [293.15, 283.15]
                    values[slots == 72, 0, 1] = -9999.
                else:
                    values[:, 0, 1] = 293.15
                    values[slots == 96, 0, 0] = -9999.
                var[:] = values
        return path

    def run_month(self, source, bundle=None, tile_lat=1, tile_lon=1):
        self.assertTrue(hasattr(self.m, "process_month"), "Monthly processing is not implemented")
        with contextlib.redirect_stdout(io.StringIO()):
            return self.m.process_month(source, "202402", bundle or self.bundle(), self.root / "out",
                                        tile_lat=tile_lat, tile_lon=tile_lon, dataset_factory=Dataset)

    def read_rows(self):
        with (self.root / "out/era5_country_daily_202402.csv").open() as f:
            return {(row["country_id"], row["date"]): row for row in csv.DictReader(f)}

    def test_weight_ids_grid_and_raw_population_preserved(self):
        bundle = self.bundle()
        self.assertEqual(bundle["country_ids"], ["001", "002", "003"])
        np.testing.assert_array_equal(bundle["population"], [100, 200, 0])
        self.assertEqual(bundle["weights"].shape, (3, 4))

    def test_unnormalized_weights_and_corrupt_grid_hash_rejected(self):
        self.bundle()
        sparse.save_npz(self.weights_path, sparse.csr_matrix([[25, 75, 0, 0], [0, 0, .5, .5], [0, 0, 0, 0]]))
        with self.assertRaisesRegex(ValueError, "normalized"):
            self.bundle()
        sparse.save_npz(self.weights_path, sparse.csr_matrix([[.25, .75, 0, 0], [0, 0, .5, .5], [0, 0, 0, 0]]))
        metadata = json.loads(self.grid_path.read_text())
        metadata["grid"]["latitude"][0] = 2
        self.grid_path.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, "hash"):
            self.bundle()

    def test_tiled_month_output_missing_coverage_and_leap_day(self):
        self.run_month(self.make_nc(missing_hour=True))
        rows = self.read_rows()
        self.assertEqual(len(rows), 3 * 29)
        first = rows["001", "2024-02-01"]
        self.assertAlmostEqual(float(first["tmin_c"]), 7.5, places=4)
        self.assertAlmostEqual(float(first["tmax_c"]), 27.5, places=4)
        self.assertAlmostEqual(float(first["dewpoint_c"]), 17.5, places=4)
        self.assertEqual(first["day_definition"], "UTC")
        self.assertEqual(float(first["pop_valid_fraction"]), 1)
        self.assertEqual(rows["001", "2024-02-02"]["hours_present"], "23")
        self.assertTrue(np.isnan(float(rows["001", "2024-02-02"]["tmin_c"])))
        fourth = rows["001", "2024-02-04"]
        self.assertTrue(np.isnan(float(fourth["tmin_c"])))
        self.assertEqual(float(fourth["t2m_pop_valid_fraction"]), .25)
        self.assertEqual(float(fourth["dewpoint_pop_valid_fraction"]), 1)
        fifth = rows["001", "2024-02-05"]
        self.assertTrue(np.isnan(float(fifth["dewpoint_c"])))
        self.assertEqual(float(fifth["pop_valid_fraction"]), .75)
        self.assertTrue(np.isnan(float(rows["003", "2024-02-29"]["pop_valid_fraction"])))
        audit = json.loads((self.root / "out/era5_country_daily_202402.audit.json").read_text())
        self.assertEqual(audit["missing_hour_count"], 1)
        self.assertEqual(audit["rows"], 87)
        self.assertIn("sha256", audit["provenance"]["source"])

    def test_tile_size_does_not_change_answer(self):
        source = self.make_nc()
        self.run_month(source)
        small = self.read_rows()
        self.run_month(source, tile_lat=2, tile_lon=2)
        self.assertEqual(self.read_rows(), small)

    def test_resume_checks_output_and_source_content(self):
        source = self.make_nc()
        first = self.run_month(source)
        second = self.run_month(source)
        self.assertEqual(first["status"], "processed")
        self.assertEqual(second["status"], "skipped_validated")
        output = self.root / "out/era5_country_daily_202402.csv"
        output.write_text("damaged\n")
        self.assertEqual(self.run_month(source)["status"], "processed")
        with Dataset(source, "a") as dataset:
            dataset.variables["d2m"][0, 0, 0] = 303.15
        self.assertEqual(self.run_month(source)["status"], "processed")

    def test_grid_order_and_units_rejected_without_final_outputs(self):
        for bad_units, reverse_lat in [("degC", False), ("K", True)]:
            source = self.make_nc(units=bad_units, reverse_lat=reverse_lat)
            with self.subTest(units=bad_units, reverse_lat=reverse_lat), self.assertRaises(ValueError):
                self.run_month(source)
            self.assertFalse((self.root / "out/era5_country_daily_202402.csv").exists())


if __name__ == "__main__":
    unittest.main()
