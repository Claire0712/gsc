#!/usr/bin/env python3
"""Prepare national IODA coverage/quality screening, without resilience estimates.

Reads immutable raw country archives for 2022--2025, verifies compressed SHA256
and size, and works on one quarter and one decompressed JSON file at a time.
Dense native-grid NumPy arrays replace per-observation Python dictionaries.
Only alternate values at conflicting timestamps need additional typed arrays.

CLI: python prepare_ioda_quality.py --data-root DATA --output-dir DERIVED
An exit status of 0 means the audit completed; inspect quality_pass and errors
for source-data failures. Fatal execution/discovery errors return exit status 1.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

import numpy as np


YEARS = (2022, 2023, 2024, 2025)
CADENCES = {"ping-slash24": 600, "bgp": 300, "merit-nt": 300}
COLLECTIONS = ("raw_country_batches", "raw_core_signals")
COUNT_FIELDS = (
    "expected_points", "valid_points", "zero_points", "conflict_points", "duplicate_points",
    "observed_points", "null_points", "negative_points", "nonfinite_points", "invalid_only_points",
    "null_only_points", "absent_points", "alignment_excluded_points", "series_count",
    "empty_series", "rejected_series", "missing_series", "requested", "phase_conflict",
)
QUARTER_FIELDS = ("country_id", "year", "quarter", "signal", *COUNT_FIELDS,
                  "coverage", "candidate_80pct", "timestamp_phase_seconds")
ANNUAL_FIELDS = tuple(field for field in QUARTER_FIELDS if field != "quarter")
NOTES = [
    "Coverage screening only; no resilience, outage, causal, or representativeness estimates.",
    "Expected points cover each full half-open UTC quarter/year at ping-slash24=600s; bgp/merit-nt=300s.",
    "Countries are the union of selected metadata country codes; every country has all three signals for 2022-2025.",
    "ISO2-shaped historical/special codes are retained as archived; this does not certify contemporary country status.",
    "Zero is valid. Only finite nonnegative numeric observations enter valid coverage.",
    "Null plus a valid value retains the valid observation; null, negative and nonfinite flags remain separately counted.",
    "Distinct valid values at the exact same country/source/timestamp are conflicts; all values at that point are excluded.",
    "duplicate_points counts excess identical valid numeric observations, including repeats at conflicted timestamps; nulls are not observations.",
    "Consistent native timestamp phase is retained; incompatible phases exclude the entire country/source quarter. No timestamps are snapped.",
    "For nonzero phase, until may be the next native-grid timestamp or the clipped quarter boundary, provided no observation crosses the boundary.",
    "candidate_80pct means coverage >= 0.80 only and is a screening flag, not an approved analysis sample.",
    "Annual missing_series/requested/phase_conflict are counts of quarters; annual timestamp phases list all observed quarterly phases.",
    "A completed audit may report input errors; quality_pass is false when errors, conflicts, invalid values, or incompatible phases are found.",
]


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def quarter_bounds(year, quarter):
    if type(year) is not int or type(quarter) is not int or quarter not in (1, 2, 3, 4):
        raise ValueError("Invalid year/quarter")
    start = dt.datetime(year, quarter * 3 - 2, 1, tzinfo=dt.timezone.utc)
    end = (dt.datetime(year + 1, 1, 1, tzinfo=dt.timezone.utc) if quarter == 4 else
           dt.datetime(year, quarter * 3 + 1, 1, tzinfo=dt.timezone.utc))
    return int(start.timestamp()), int(end.timestamp())


def atomic_json(path, data):
    _atomic_write(path, lambda stream: json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False))


def _atomic_write(path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", prefix="." + path.name,
                                         suffix=".tmp", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def atomic_csv(path, rows, fields):
    def write(stream):
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    _atomic_write(path, write)


def fingerprint(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {"bytes": size, "sha256": digest.hexdigest()}


class SignalGrid:
    """One country/signal quarter. Flags allow invalids and valid data to coexist."""
    SEEN, NULL, NEGATIVE, NONFINITE, CONFLICT = 1, 2, 4, 8, 16

    def __init__(self, expected):
        self.expected = expected
        self.values = None
        self.counts = None
        self.flags = None
        self.alternates = []
        self.phases = set()
        self.series_count = self.empty_series = self.rejected_series = 0

    def allocate(self):
        if self.values is None:
            self.values = np.full(self.expected, np.nan, dtype=np.float64)
            self.counts = np.zeros(self.expected, dtype=np.uint32)
            self.flags = np.zeros(self.expected, dtype=np.uint8)

    def add_values(self, offset, values, nulls):
        self.allocate()
        stop = offset + len(values)
        flags = self.flags[offset:stop]
        flags |= self.SEEN
        flags[nulls] |= self.NULL
        finite = np.isfinite(values)
        flags[~finite & ~nulls] |= self.NONFINITE
        flags[finite & (values < 0)] |= self.NEGATIVE
        valid = finite & (values >= 0) & ~nulls
        reference = self.values[offset:stop]
        counts = self.counts[offset:stop]
        previous = counts > 0
        conflicting = valid & previous & (reference != values)
        flags[conflicting] |= self.CONFLICT
        if np.any(conflicting):
            indices = np.flatnonzero(conflicting).astype(np.int32) + offset
            self.alternates.append((indices, values[conflicting].copy()))
        reference[valid & ~previous] = values[valid & ~previous]
        if np.any(counts[valid] == np.iinfo(np.uint32).max):
            raise ValueError("Too many repeated observations for uint32 counts")
        counts[valid] += 1

    def statistics(self):
        row = {field: 0 for field in COUNT_FIELDS}
        row.update(expected_points=self.expected, series_count=self.series_count,
                   empty_series=self.empty_series, rejected_series=self.rejected_series,
                   missing_series=int(self.series_count == 0), phase_conflict=int(len(self.phases) > 1))
        if len(self.phases) > 1:
            row["alignment_excluded_points"] = self.expected
            return row
        if self.values is None:
            row["absent_points"] = self.expected
            return row
        flags = self.flags
        seen = (flags & self.SEEN) != 0
        numeric = self.counts > 0
        conflict = (flags & self.CONFLICT) != 0
        valid = numeric & ~conflict
        invalid = (flags & (self.NEGATIVE | self.NONFINITE)) != 0
        null = (flags & self.NULL) != 0
        extra_distinct = 0
        if self.alternates:
            indices = np.concatenate([chunk[0] for chunk in self.alternates])
            values = np.concatenate([chunk[1] for chunk in self.alternates])
            order = np.lexsort((values, indices))
            indices, values = indices[order], values[order]
            extra_distinct = 1 + int(np.count_nonzero((indices[1:] != indices[:-1]) | (values[1:] != values[:-1])))
        row.update(
            valid_points=int(np.count_nonzero(valid)),
            zero_points=int(np.count_nonzero(valid & (self.values == 0))),
            conflict_points=int(np.count_nonzero(conflict)),
            duplicate_points=int(self.counts.sum(dtype=np.uint64)) - int(np.count_nonzero(numeric)) - extra_distinct,
            observed_points=int(np.count_nonzero(seen)), null_points=int(np.count_nonzero(null)),
            negative_points=int(np.count_nonzero(flags & self.NEGATIVE)),
            nonfinite_points=int(np.count_nonzero(flags & self.NONFINITE)),
            invalid_only_points=int(np.count_nonzero(~numeric & invalid)),
            null_only_points=int(np.count_nonzero(~numeric & ~invalid & null)),
            absent_points=int(np.count_nonzero(~seen)),
        )
        return row


class QuarterAccumulator:
    def __init__(self, year, quarter):
        self.year, self.quarter = year, quarter
        self.start, self.until = quarter_bounds(year, quarter)
        self.grids = {}

    def _grid(self, country, signal):
        key = (country, signal)
        if key not in self.grids:
            self.grids[key] = SignalGrid((self.until - self.start) // CADENCES[signal])
        return self.grids[key]

    def add(self, series, origin=""):
        if not isinstance(series, dict):
            raise ValueError("Series is not an object")
        country, signal = series.get("entityCode"), series.get("datasource")
        if series.get("entityType") != "country" or not isinstance(country, str) or not re.fullmatch(r"[A-Z]{2}", country):
            raise ValueError("Expected country entity with ISO2-shaped entityCode")
        if signal not in CADENCES:
            raise ValueError("Unexpected signal")
        grid = self._grid(country, signal)
        grid.series_count += 1
        try:
            step = CADENCES[signal]
            if (type(series.get("step")) is not int or type(series.get("nativeStep")) is not int or
                    series["step"] != step or series["nativeStep"] != step):
                raise ValueError("Invalid/coarsened cadence: step and nativeStep must match the native source cadence")
            start, until = series.get("from"), series.get("until")
            if type(start) is not int or type(until) is not int or until < start:
                raise ValueError("Invalid series from/until timestamps")
            values = series.get("values")
            if not isinstance(values, list):
                raise ValueError("Series values must be a list")
            if not values:
                if not self.start <= start <= until <= self.until:
                    raise ValueError("Empty series outside its metadata quarter")
                grid.empty_series += 1
                return
            if start < self.start or start + (len(values) - 1) * step >= self.until:
                raise ValueError("Observation spills outside the half-open metadata quarter/year")
            expected_until = start + len(values) * step
            if until != expected_until and not (until == self.until < expected_until):
                raise ValueError("Series length does not match from/until/native cadence")
            if any(value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))) for value in values):
                raise ValueError("Series values must be numeric or null")
            if any(isinstance(value, int) and abs(value) > 2 ** 53 and
                   (abs(value) > np.finfo(np.float64).max or int(float(value)) != value) for value in values):
                raise ValueError("Integer precision would be lost in the native float64 observation array")
            numeric = np.asarray(values, dtype=np.float64)
            nulls = np.fromiter((value is None for value in values), dtype=np.bool_, count=len(values))
            phase = (start - self.start) % step
            grid.phases.add(phase)
            if len(grid.phases) > 1:
                raise ValueError("Incompatible timestamp phase; entire country/signal quarter excluded")
            offset = (start - self.start - phase) // step
            grid.add_values(offset, numeric, nulls)
        except (ValueError, TypeError, OverflowError):
            grid.rejected_series += 1
            raise

    def row(self, country, signal, requested=False):
        grid = self.grids.get((country, signal))
        if grid is None:
            grid = SignalGrid((self.until - self.start) // CADENCES[signal])
        row = grid.statistics()
        coverage = row["valid_points"] / row["expected_points"]
        row.update(country_id=country, year=self.year, quarter=self.quarter, signal=signal,
                   requested=int(requested), coverage=coverage, candidate_80pct=coverage >= 0.8,
                   timestamp_phase_seconds=";".join(str(value) for value in sorted(grid.phases)))
        return row


def _metadata(root, path):
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("Metadata must be an object")
    year = record.get("year")
    if type(year) is not int:
        raise ValueError("Metadata year must be an integer")
    if year not in YEARS:
        return None
    quarter_bounds(year, record.get("quarter"))
    countries = record.get("countries")
    if (not isinstance(countries, list) or not countries or
            any(not isinstance(code, str) or not re.fullmatch(r"[A-Z]{2}", code) for code in countries)):
        raise ValueError("Metadata countries must be a nonempty list of ISO2-shaped codes")
    source = record.get("datasource")
    if source is not None and source not in CADENCES:
        raise ValueError("Metadata datasource is not a core source")
    if type(record.get("bytes")) is not int or record["bytes"] < 0:
        raise ValueError("Metadata bytes must be a nonnegative integer")
    if not isinstance(record.get("sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", record["sha256"]):
        raise ValueError("Metadata SHA256 must be a 64-digit hex string")
    if not isinstance(record.get("file"), str) or Path(record["file"]).is_absolute():
        raise ValueError("Metadata file must be relative to data-root")
    payload = (root / record["file"]).resolve()
    allowed = [(root / "ioda" / collection).resolve() for collection in COLLECTIONS]
    if not any(folder in payload.parents for folder in allowed) or not payload.name.endswith(".json.gz"):
        raise ValueError("Metadata file is outside the two permitted raw national collections")
    record["_path"] = path
    record["_payload"] = payload
    return record


def annual_rows(quarterly):
    annual = {}
    phases = {}
    for row in quarterly:
        key = row["country_id"], row["year"], row["signal"]
        if key not in annual:
            annual[key] = {field: 0 for field in COUNT_FIELDS}
            annual[key].update(country_id=key[0], year=key[1], signal=key[2])
            phases[key] = set()
        for field in COUNT_FIELDS:
            annual[key][field] += row[field]
        phases[key].update(filter(None, row["timestamp_phase_seconds"].split(";")))
    for key, row in annual.items():
        row["coverage"] = row["valid_points"] / row["expected_points"]
        row["candidate_80pct"] = row["coverage"] >= 0.8
        row["timestamp_phase_seconds"] = ";".join(sorted(phases[key], key=int))
    return [annual[key] for key in sorted(annual)]


def run(data_root, output_dir):
    root, output = Path(data_root).resolve(), Path(output_dir).resolve()
    if output == root or any((root / "ioda" / folder).resolve() == output or
                             (root / "ioda" / folder).resolve() in output.parents for folder in COLLECTIONS):
        raise ValueError("output-dir must be separate from the raw national archives")
    output.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    status = {"state": "running", "run_id": run_id, "pid": os.getpid(), "updated_utc": now(), "processed_files": 0,
              "total_files": 0, "country_years": 0, "notes": NOTES, "quality_pass": False,
              "failed_files": 0, "error_count": 0}
    errors, files, quarterly = [], [], []

    def progress():
        status["updated_utc"] = now()
        atomic_json(output / "progress.json", status)

    def record_error(path, message, **extra):
        error = {"file": str(path), "message": str(message), **extra}
        errors.append(error)
        status["error_count"] = len(errors)
        return error

    atomic_json(output / "summary.json", status)
    progress()
    try:
        metadata_paths = sorted(path for folder in COLLECTIONS
                                for path in (root / "ioda" / folder).glob("*.metadata.json")
                                if not path.name.startswith("._"))
        records, countries = [], set()
        skipped = 0
        for path in metadata_paths:
            try:
                record = _metadata(root, path)
                if record is None:
                    skipped += 1
                    continue
                countries.update(record["countries"])
                records.append(record)
            except (OSError, ValueError, TypeError) as error:
                name = str(path.relative_to(root))
                record_error(name, error, stage="metadata")
                files.append({"metadata": name, "passed": False, "error": str(error)})
        if not records:
            raise ValueError("No valid 2022-2025 national IODA metadata found")
        status.update(total_files=len(records) + len(files), processed_files=len(files),
                      failed_files=len(files), country_years=len(countries) * len(YEARS),
                      skipped_out_of_scope_metadata=skipped, countries=len(countries))
        progress()
        requested = {(record["year"], record["quarter"], country, signal)
                     for record in records for country in record["countries"]
                     for signal in ([record["datasource"]] if record.get("datasource") else CADENCES)}
        for year in YEARS:
            for quarter in (1, 2, 3, 4):
                agg = QuarterAccumulator(year, quarter)
                for record in (r for r in records if (r["year"], r["quarter"]) == (year, quarter)):
                    path = record["_payload"]
                    entry = {"metadata": str(record["_path"].relative_to(root)), "file": record["file"],
                             "year": year, "quarter": quarter, "passed": False,
                             "expected_sha256": record["sha256"], "expected_bytes": record["bytes"],
                             "accepted_series": 0, "rejected_series": 0, "ignored_noncore_series": 0}
                    before = len(errors)
                    raw = None
                    try:
                        entry.update(fingerprint(path))
                        if entry["bytes"] != record["bytes"]:
                            raise ValueError("Compressed byte-size mismatch")
                        if entry["sha256"].lower() != record["sha256"].lower():
                            raise ValueError("Compressed SHA256 mismatch")
                        with gzip.open(path, "rt", encoding="utf-8") as stream:
                            raw = json.load(stream)
                        if not isinstance(raw, dict) or raw.get("error"):
                            raise ValueError("Malformed response or stored API error")
                        request = raw.get("requestParameters", {})
                        if request.get("from") != agg.start or request.get("until") != agg.until:
                            raise ValueError("Response request does not match its metadata UTC quarter")
                        groups = raw.get("data")
                        if not isinstance(groups, list) or any(not isinstance(group, list) for group in groups):
                            raise ValueError("Response data must be a list of series lists")
                        sources = [record["datasource"]] if record.get("datasource") else CADENCES
                        for group in groups:
                            for series in group:
                                try:
                                    if not isinstance(series, dict):
                                        raise ValueError("Series must be an object")
                                    if series.get("datasource") not in CADENCES:
                                        entry["ignored_noncore_series"] += 1
                                        continue
                                    if series.get("entityCode") not in record["countries"]:
                                        raise ValueError("Series country is not in metadata countries")
                                    if series["datasource"] not in sources:
                                        raise ValueError("Series source does not match metadata datasource")
                                    agg.add(series, record["file"])
                                    entry["accepted_series"] += 1
                                except (ValueError, TypeError, OverflowError) as error:
                                    entry["rejected_series"] += 1
                                    record_error(record["file"], error, stage="series",
                                                 country=series.get("entityCode") if isinstance(series, dict) else None,
                                                 signal=series.get("datasource") if isinstance(series, dict) else None)
                        entry["passed"] = len(errors) == before
                    except (OSError, EOFError, ValueError, TypeError, AttributeError) as error:
                        entry["error"] = str(error)
                        record_error(record["file"], error, stage="file")
                    finally:
                        # Drop the JSON tree before opening the next archive.
                        raw = groups = group = series = None
                    files.append(entry)
                    status["processed_files"] += 1
                    status["failed_files"] += int(not entry["passed"])
                    status.update(current_year=year, current_quarter=quarter, current_file=record["file"])
                    progress()
                for country in sorted(countries):
                    for signal in CADENCES:
                        row = agg.row(country, signal, (year, quarter, country, signal) in requested)
                        quarterly.append(row)
                        for field, message in (("conflict_points", "Conflicting numeric observations excluded"),
                                               ("negative_points", "Negative observations excluded"),
                                               ("nonfinite_points", "Nonfinite observations excluded")):
                            if row[field]:
                                record_error("quarter_aggregate", message, year=year, quarter=quarter,
                                             country=country, signal=signal, points=row[field])
                del agg
        annual = annual_rows(quarterly)
        atomic_csv(output / "coverage_quarterly.csv", quarterly, QUARTER_FIELDS)
        atomic_csv(output / "coverage_annual.csv", annual, ANNUAL_FIELDS)
        status.update(state="completed", updated_utc=now(), quality_pass=not errors,
                      annual_rows=len(annual), quarterly_rows=len(quarterly),
                      candidate_country_year_signals=sum(row["candidate_80pct"] for row in annual),
                      valid_points=sum(row["valid_points"] for row in annual),
                      conflict_points=sum(row["conflict_points"] for row in annual),
                      duplicate_points=sum(row["duplicate_points"] for row in annual),
                      current_file=None)
        atomic_json(output / "summary.json", status)
        manifest = {"run_id": run_id, "state": "completed", "updated_utc": now(), "data_root": str(root),
                    "script_sha256": fingerprint(Path(__file__))["sha256"],
                    "years": list(YEARS), "native_cadence_seconds": CADENCES, "files": files,
                    "errors": errors, "notes": NOTES,
                    "outputs": [{"file": name, **fingerprint(output / name)} for name in
                                ("coverage_annual.csv", "coverage_quarterly.csv", "summary.json")]}
        atomic_json(output / "manifest.json", manifest)
        progress()
        return status.copy()
    except BaseException as error:
        status.update(state="failed", updated_utc=now(), quality_pass=False,
                      failure_type=type(error).__name__, failure=str(error))
        atomic_json(output / "summary.json", status)
        atomic_json(output / "manifest.json", {"run_id": run_id, "state": "failed", "updated_utc": now(),
                                                "script_sha256": fingerprint(Path(__file__))["sha256"],
                                                "files": files, "errors": errors, "fatal_error": str(error),
                                                "outputs": [], "notes": NOTES})
        progress()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = run(args.data_root, args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
