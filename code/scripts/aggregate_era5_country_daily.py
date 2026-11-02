#!/usr/bin/env python3
"""Aggregate hourly ERA5 in bounded spatial tiles, using fixed population weights.

UTC day definition: pixel-level 24-hour t2m minima/maxima and d2m means,
then country population weighting. Any missing hour at any positively weighted
pixel invalidates that country's affected daily metric; weights are never
renormalized to the available population. All temperatures are exported in C.
"""
from __future__ import annotations

import calendar
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

import numpy as np
from scipy import sparse


def _month_start(month: str) -> dt.datetime:
    if not re.fullmatch(r"\d{6}", month):
        raise ValueError(f"Expected YYYYMM, got {month!r}")
    return dt.datetime.strptime(month, "%Y%m")


def months_between(start: str, end: str):
    current, last = _month_start(start), _month_start(end)
    if current > last:
        raise ValueError("start-month must precede end-month")
    while current <= last:
        yield current.strftime("%Y%m")
        current = (current.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def month_dates(month: str) -> list[str]:
    start = _month_start(month)
    return [(start + dt.timedelta(days=i)).date().isoformat()
            for i in range(calendar.monthrange(start.year, start.month)[1])]


def validate_temperature_units(units: str):
    if units.strip().lower() not in {"k", "kelvin", "kelvins"}:
        raise ValueError(f"Expected Kelvin temperature units, got {units!r}")


def hour_slots(values, units: str, calendar_name: str, month: str) -> np.ndarray:
    """Validate a UTC hourly time axis, allowing explicitly reported gaps."""
    if calendar_name not in {"standard", "gregorian", "proleptic_gregorian"}:
        raise ValueError(f"Unsupported calendar: {calendar_name}")
    match = re.fullmatch(r"(seconds?|minutes?|hours?|days?) since (.+)", units.strip())
    if not match:
        raise ValueError(f"Unsupported CF time units: {units!r}")
    origin_text = match.group(2).strip().replace(" UTC", "+00:00").replace("Z", "+00:00")
    try:
        origin = dt.datetime.fromisoformat(origin_text)
    except ValueError as exc:
        raise ValueError(f"Invalid CF time origin: {origin_text!r}") from exc
    if origin.tzinfo:
        origin = origin.astimezone(dt.timezone.utc).replace(tzinfo=None)
    factors = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
    values = np.asarray(np.ma.filled(np.ma.asarray(values, dtype=float), np.nan))
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("Time axis must be a finite one-dimensional array")
    hours = (values * factors[match.group(1).rstrip("s")]
             + (origin - _month_start(month)).total_seconds()) / 3600
    if not np.allclose(hours, np.rint(hours), rtol=0, atol=1e-7):
        raise ValueError("Time axis contains non-hourly timestamps")
    slots = np.rint(hours).astype(np.int64)
    if np.any(slots < 0) or np.any(slots >= len(month_dates(month)) * 24):
        raise ValueError("Time axis contains timestamps outside the requested month")
    if np.any(np.diff(slots) <= 0):
        raise ValueError("Time axis must be strictly increasing without duplicates")
    return slots


def daily_statistics(values, slots: np.ndarray, days: int, variable: str) -> dict:
    """Reduce a single monthly spatial tile; retain only day-by-cell arrays."""
    if variable not in {"t2m", "d2m"}:
        raise ValueError(f"Unsupported ERA5 variable {variable}")
    values = np.asarray(np.ma.filled(np.ma.asarray(values, dtype=np.float32), np.nan))
    if values.ndim < 2 or values.shape[0] != len(slots):
        raise ValueError("Tile time dimension does not match the time axis")
    cells = int(np.prod(values.shape[1:]))
    values = values.reshape(len(slots), cells)
    if len(slots) == days * 24 and np.array_equal(slots, np.arange(days * 24)):
        hourly = values.reshape(days, 24, cells)
    else:
        complete = np.full((days * 24, cells), np.nan, dtype=np.float32)
        complete[slots] = values
        hourly = complete.reshape(days, 24, cells)
    valid = np.isfinite(hourly).all(axis=1)
    if variable == "t2m":
        result = {"tmin_c": np.min(hourly, axis=1).astype(np.float64) - 273.15,
                  "tmax_c": np.max(hourly, axis=1).astype(np.float64) - 273.15}
    else:
        result = {"dewpoint_c": np.mean(hourly, axis=1, dtype=np.float64) - 273.15}
    for field in result.values():
        field[~valid] = np.nan
    result["valid"] = valid
    return result


def weighted_statistics(weights: sparse.csr_matrix, daily: dict) -> dict:
    """Return unrenormalized weighted values and positive-weight missing mass."""
    row_mass = np.asarray(weights.sum(axis=1)).ravel()
    missing_mass = np.asarray(weights.dot((~daily["valid"]).T)).T
    valid_fraction = np.clip(row_mass[None, :] - missing_mass, 0, 1)
    valid_fraction[:, row_mass == 0] = np.nan
    result = {"missing_mass": missing_mass, "valid_fraction": valid_fraction}
    for name, values in daily.items():
        if name == "valid":
            continue
        weighted = np.asarray(weights.dot(np.nan_to_num(values, nan=0).T)).T
        weighted[(missing_mass > 0) | (row_mass[None, :] == 0)] = np.nan
        result[name] = weighted
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_fingerprint(path: Path) -> dict:
    path = Path(path).resolve()
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"Input changed while hashing: {path}")
    return {"path": str(path), "size": after.st_size, "mtime_ns": after.st_mtime_ns,
            "sha256": digest}


def load_weight_bundle(weights_path: Path, metadata_path: Path, grid_path: Path) -> dict:
    fingerprints = {name: file_fingerprint(path) for name, path in
                    (("weights", weights_path), ("countries", metadata_path), ("grid", grid_path))}
    weights = sparse.load_npz(weights_path).astype(np.float64).tocsr()
    weights.sum_duplicates()
    weights.eliminate_zeros()
    weights.sort_indices()
    if not np.isfinite(weights.data).all() or (weights.data < 0).any():
        raise ValueError("Population weights must be finite and nonnegative")
    with Path(metadata_path).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    country_ids = [row["country_id"].strip() for row in rows]
    population = np.asarray([float(row["total_population"]) for row in rows])
    if not country_ids or any(not name for name in country_ids) or len(set(country_ids)) != len(country_ids):
        raise ValueError("Country identifiers must be nonempty and unique")
    if not np.isfinite(population).all() or (population < 0).any():
        raise ValueError("Country population must be finite and nonnegative")
    grid = json.loads(Path(grid_path).read_text(encoding="utf-8"))["grid"]
    if grid["flatten_order"] != "C":
        raise ValueError("Expected C-order flattened latitude/longitude weights")
    for name in ("latitude", "longitude"):
        values = np.asarray(grid[name], dtype="<f8")
        if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
            raise ValueError(f"Invalid {name} grid")
        digest = hashlib.sha256(values.tobytes(order="C")).hexdigest()
        if digest != grid[name + "_sha256"]:
            raise ValueError(f"Grid {name} hash mismatch")
    shape = (len(grid["latitude"]), len(grid["longitude"]))
    if list(shape) != grid["shape"] or weights.shape != (len(rows), int(np.prod(shape))):
        raise ValueError("Weights dimensions do not match country metadata and grid")
    mass = np.asarray(weights.sum(axis=1)).ravel()
    positive = population > 0
    if not np.allclose(mass[positive], 1, rtol=0, atol=1e-10) or np.any(mass[~positive] != 0):
        raise ValueError("Positive-population weights must be normalized to 1; zero-population rows must be empty")
    return {"weights": weights, "country_ids": country_ids, "population": population,
            "grid": grid, "fingerprints": fingerprints}


FIELDS = ["country_id", "date", "tmin_c", "tmax_c", "dewpoint_c",
          "t2m_pop_valid_fraction", "dewpoint_pop_valid_fraction", "pop_valid_fraction",
          "total_population", "hours_present", "hours_expected", "day_definition"]


def _log(message: str):
    print(f"{dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} {message}", flush=True)


def _write_atomic(path: Path, writer):
    """Publish a fully flushed file with an atomic rename in the same directory."""
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _validated_resume(csv_path: Path, audit_path: Path, provenance: dict, bundle: dict, dates: list[str]):
    if not csv_path.is_file() or not audit_path.is_file():
        return None
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        expected_rows = len(bundle["country_ids"]) * len(dates)
        if (audit.get("provenance") != provenance or audit.get("rows") != expected_rows
                or audit.get("output_sha256") != sha256_file(csv_path)):
            return None
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDS:
                return None
            keys = [(row["country_id"], row["date"]) for row in reader]
        expected = {(country, date) for country in bundle["country_ids"] for date in dates}
        if len(keys) != expected_rows or set(keys) != expected:
            return None
        return audit
    except (OSError, ValueError, KeyError, TypeError, csv.Error):
        return None


def _read_tile(variable, lat_slice: slice, lon_slice: slice) -> np.ndarray:
    raw = variable[:, lat_slice, lon_slice]
    values = np.asarray(np.ma.filled(np.ma.asarray(raw, dtype=np.float32), np.nan))
    # netCDF4 masks these automatically; explicitly recognize them for readers
    # that return raw fill values, including the local HDF5 integration tests.
    for attribute in ("_FillValue", "missing_value"):
        if attribute in variable.ncattrs():
            for fill in np.asarray(variable.getncattr(attribute)).ravel():
                values[values == fill] = np.nan
    return values


def _aggregate_dataset(dataset, month: str, bundle: dict, tile_lat: int, tile_lon: int) -> tuple:
    grid, weights = bundle["grid"], bundle["weights"]
    if tile_lat < 1 or tile_lon < 1:
        raise ValueError("Tile dimensions must be positive")
    for name in ("latitude", "longitude"):
        coordinate = dataset.variables[name]
        actual = np.asarray(coordinate[:])
        if coordinate.dimensions != (name,) or not np.array_equal(actual, np.asarray(grid[name])):
            raise ValueError(f"ERA5 {name} coordinates/order differ from the weight grid")
    time_var = dataset.variables["valid_time"]
    if time_var.dimensions != ("valid_time",):
        raise ValueError("Unexpected ERA5 valid_time dimensions")
    slots = hour_slots(time_var[:], time_var.units, getattr(time_var, "calendar", "standard"), month)
    dates = month_dates(month)
    days, countries = len(dates), len(bundle["country_ids"])
    shape = (days, countries)
    hours_present = np.bincount(slots // 24, minlength=days)
    result = {name: np.zeros(shape, dtype=np.float64) for name in ("tmin_c", "tmax_c", "dewpoint_c")}
    missing = {name: np.zeros(shape, dtype=np.float64) for name in ("t2m", "d2m", "joint")}
    nlat, nlon = grid["shape"]
    variable_metadata = {}
    for name in ("t2m", "d2m"):
        variable = dataset.variables[name]
        validate_temperature_units(variable.units)
        if variable.dimensions != ("valid_time", "latitude", "longitude"):
            raise ValueError(f"Unexpected dimensions for {name}: {variable.dimensions}")
        if variable.shape != (len(slots), nlat, nlon):
            raise ValueError(f"Unexpected shape for {name}: {variable.shape}")
        if hasattr(variable, "set_var_chunk_cache"):
            # Avoid a separate large HDF5 cache for each variable on the 4-GB host.
            variable.set_var_chunk_cache(size=16 * 1024 * 1024, nelems=1009, preemption=0.75)
        variable_metadata[name] = {"units": variable.units, "dtype": str(variable.dtype),
                                   "dimensions": list(variable.dimensions)}
    tile_number = 0
    total_tiles = ((nlat + tile_lat - 1) // tile_lat) * ((nlon + tile_lon - 1) // tile_lon)
    tiles_read = 0
    for lat_start in range(0, nlat, tile_lat):
        lat_stop = min(nlat, lat_start + tile_lat)
        for lon_start in range(0, nlon, tile_lon):
            lon_stop = min(nlon, lon_start + tile_lon)
            tile_number += 1
            flat = (np.arange(lat_start, lat_stop)[:, None] * nlon
                    + np.arange(lon_start, lon_stop)[None, :]).ravel()
            tile_weights = weights[:, flat].tocsr()
            if not tile_weights.nnz:
                _log(f"month={month} tile={tile_number}/{total_tiles} skipped_no_population")
                continue
            tiles_read += 1
            lat_slice, lon_slice = slice(lat_start, lat_stop), slice(lon_start, lon_stop)
            previous_valid = None
            for variable_name in ("t2m", "d2m"):
                _log(f"month={month} tile={tile_number}/{total_tiles} variable={variable_name} "
                     f"lat={lat_start}:{lat_stop} lon={lon_start}:{lon_stop} reading")
                values = _read_tile(dataset.variables[variable_name], lat_slice, lon_slice)
                daily = daily_statistics(values, slots, days, variable_name)
                del values
                invalid = ~daily["valid"]
                missing[variable_name] += np.asarray(tile_weights.dot(invalid.T)).T
                for metric, daily_values in daily.items():
                    if metric != "valid":
                        result[metric] += np.asarray(tile_weights.dot(np.nan_to_num(daily_values, nan=0).T)).T
                if previous_valid is None:
                    previous_valid = daily["valid"]
                else:
                    joint_invalid = ~(previous_valid & daily["valid"])
                    missing["joint"] += np.asarray(tile_weights.dot(joint_invalid.T)).T
                del daily, invalid
            _log(f"month={month} tile={tile_number}/{total_tiles} complete")
    zero_population = bundle["population"] == 0
    for metric in result:
        variable_name = "d2m" if metric == "dewpoint_c" else "t2m"
        result[metric][(missing[variable_name] > 0) | zero_population[None, :]] = np.nan
    row_mass = np.asarray(weights.sum(axis=1)).ravel()
    for source, field in (("t2m", "t2m_pop_valid_fraction"), ("d2m", "dewpoint_pop_valid_fraction"),
                          ("joint", "pop_valid_fraction")):
        result[field] = np.clip(row_mass[None, :] - missing[source], 0, 1)
        result[field][:, zero_population] = np.nan
    metadata = {"hours_present_by_day": hours_present.tolist(), "expected_hour_count": days * 24,
                "actual_hour_count": len(slots), "missing_hour_count": days * 24 - len(slots),
                "missing_hour_slots": np.setdiff1d(np.arange(days * 24), slots).tolist(),
                "variables": variable_metadata, "tiles_read": tiles_read, "total_tiles": total_tiles}
    return result, hours_present, metadata


def process_month(source: Path, month: str, bundle: dict, output_dir: Path,
                  tile_lat: int = 121, tile_lon: int = 240, dataset_factory=None) -> dict:
    source, output_dir = Path(source), Path(output_dir)
    dates = month_dates(month)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"era5_country_daily_{month}.csv"
    audit_path = output_dir / f"era5_country_daily_{month}.audit.json"
    started = time.monotonic()
    _log(f"month={month} hashing_source path={source}")
    fingerprint = file_fingerprint(source)
    provenance = {"source": fingerprint, "weight_inputs": bundle["fingerprints"],
                  "script_sha256": sha256_file(Path(__file__)), "month": month,
                  "tile_lat": tile_lat, "tile_lon": tile_lon, "algorithm_version": 1,
                  "day_definition": "UTC", "missing_policy": "any_positive_weight_cell_missing_any_hour_invalidates",
                  "temperature_order": "pixel_24h_extreme_then_population_weighted_country",
                  "dewpoint_order": "pixel_24h_mean_then_population_weighted_country"}
    if _validated_resume(csv_path, audit_path, provenance, bundle, dates) is not None:
        _log(f"month={month} skipped_validated source_weights_code_and_output_sha256_match")
        return {"status": "skipped_validated", "month": month, "csv": str(csv_path), "audit": str(audit_path)}
    if dataset_factory is None:
        from netCDF4 import Dataset
        dataset_factory = Dataset
    with dataset_factory(str(source), "r") as dataset:
        result, hours_present, metadata = _aggregate_dataset(dataset, month, bundle, tile_lat, tile_lon)
    source_after = source.stat()
    if (source_after.st_size, source_after.st_mtime_ns) != (fingerprint["size"], fingerprint["mtime_ns"]):
        raise RuntimeError(f"Input changed while processing: {source}")

    def write_csv(handle):
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for country_index, country_id in enumerate(bundle["country_ids"]):
            for day_index, date in enumerate(dates):
                row = {field: format(float(values[day_index, country_index]), ".10g")
                       for field, values in result.items()}
                row.update(country_id=country_id, date=date,
                           total_population=format(float(bundle["population"][country_index]), ".12g"),
                           hours_present=int(hours_present[day_index]), hours_expected=24, day_definition="UTC")
                writer.writerow(row)

    _write_atomic(csv_path, write_csv)
    audit = {"schema_version": 1, "month": month, "rows": len(dates) * len(bundle["country_ids"]),
             "country_count": len(bundle["country_ids"]), "day_count": len(dates),
             "zero_population_country_ids": [country for country, population in zip(bundle["country_ids"], bundle["population"]) if population == 0],
             "provenance": provenance, "output_sha256": sha256_file(csv_path), **metadata,
             "invalid_country_days": {key: int(np.isnan(result[key]).sum()) for key in ("tmin_c", "tmax_c", "dewpoint_c")},
             "elapsed_seconds": round(time.monotonic() - started, 3),
             "completed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    _write_atomic(audit_path, lambda handle: json.dump(audit, handle, indent=2, allow_nan=False))
    _log(f"month={month} complete rows={audit['rows']} elapsed_seconds={audit['elapsed_seconds']}")
    return {"status": "processed", "month": month, "csv": str(csv_path), "audit": str(audit_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--era5-dir", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--country-metadata", type=Path, required=True)
    parser.add_argument("--grid-metadata", type=Path, help="Default: weights_metadata.json beside --weights")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start-month", default="201801")
    parser.add_argument("--end-month", default="202512")
    parser.add_argument("--tile-lat", type=int, default=121)
    parser.add_argument("--tile-lon", type=int, default=240)
    parser.add_argument("--max-months", type=int)
    args = parser.parse_args(argv)
    if args.tile_lat < 1 or args.tile_lon < 1 or (args.max_months is not None and args.max_months < 1):
        parser.error("tile dimensions and max-months must be positive")
    months = list(months_between(args.start_month, args.end_month))
    if args.max_months:
        months = months[:args.max_months]
    grid_path = args.grid_metadata or args.weights.parent / "weights_metadata.json"
    bundle = load_weight_bundle(args.weights, args.country_metadata, grid_path)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # A held advisory lock prevents two instances publishing to the same folder.
    import fcntl
    with (args.output_dir / ".aggregate.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        for month in months:
            process_month(args.era5_dir / f"era5_2m_{month}.nc", month, bundle, args.output_dir,
                          tile_lat=args.tile_lat, tile_lon=args.tile_lon)
    _log(f"all_months_complete count={len(months)}")


if __name__ == "__main__":
    main()
