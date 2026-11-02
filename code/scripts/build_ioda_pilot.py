#!/usr/bin/env python3
"""Aggregate raw IODA signals to UTC-day QA tables, using Python >=3.8 stdlib.

This creates descriptive raw-signal quality products only. It does not impute,
normalize to a baseline, identify outages, estimate effects, or screen events.
"""
import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import sys


CORE = ("ping-slash24", "bgp", "merit-nt")
DAY = 86400
UTC = dt.timezone.utc


def utc_epoch(date):
    return int(dt.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp())


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump_json(path, obj):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def ceil_div(x, y):
    return -((-x) // y)


def slot_count(start, until, step, phase):
    return ceil_div(until - phase, step) - ceil_div(start - phase, step)


class Aggregator:
    def __init__(self, year, countries):
        self.year = year
        self.start = utc_epoch("%04d-01-01" % year)
        self.until = utc_epoch("%04d-01-01" % (year + 1))
        self.countries = sorted(countries)
        if len(set(self.countries)) != len(self.countries):
            raise ValueError("duplicate countries in download plan")
        self.names = {}
        self.daily = {}
        self.intervals = collections.defaultdict(list)
        self.cadence = {}
        self.global_cadence = collections.defaultdict(set)
        self.series_audit = []
        self.duplicates = []
        self.excluded = collections.Counter()

    def add(self, series, source):
        signal = series.get("datasource")
        if signal not in CORE:
            self.excluded[signal or "MISSING_DATASOURCE"] += 1
            return
        if series.get("entityType") != "country" or series.get("subtype") not in ("", None):
            raise ValueError("unexpected core entity type/subtype in " + source)
        country = series["entityCode"]
        if country not in self.countries:
            raise ValueError("unplanned country " + country)
        key = (country, signal)
        start, until, step, native = (series[k] for k in ("from", "until", "step", "nativeStep"))
        if any(isinstance(x, bool) or not isinstance(x, int) for x in (start, until, step, native)):
            raise ValueError("noninteger timing fields in " + source)
        if step <= 0 or native <= 0 or until <= start:
            raise ValueError("invalid time interval in " + source)
        if step != native:
            raise ValueError("step differs from nativeStep; native observation coverage cannot be inferred: " + source)
        values = series["values"]
        if not isinstance(values, list) or len(values) != ceil_div(until - start, step):
            raise ValueError("values length does not match [from, until) and step in " + source)
        cadence = (step, native, start % step)
        if key in self.cadence and cadence != self.cadence[key]:
            raise ValueError("changing cadence/phase needs explicit segment denominator: " + repr(key))
        self.cadence[key] = cadence
        self.global_cadence[signal].add(cadence)
        self.names[country] = series.get("entityName", "")
        digest = hashlib.sha256(json.dumps(values, separators=(",", ":"), allow_nan=True).encode()).hexdigest()
        clipped_start, clipped_until = max(start, self.start), min(until, self.until)
        for previous in self.intervals[key]:
            if max(clipped_start, previous[0]) < min(clipped_until, previous[1]):
                same_extent = (start, until) == (previous[2], previous[3])
                if same_extent and digest == previous[4]:
                    self.duplicates.append({"country_code": country, "signal": signal,
                                            "source_file": source, "previous_source_file": previous[5],
                                            "from": start, "until": until,
                                            "kind": "identical_segment_deduplicated", "points": len(values)})
                    return
                kind = "conflict" if same_extent else "partial overlap"
                raise ValueError(kind + " between " + source + " and " + previous[5] + " for " + repr(key))
        if clipped_start < clipped_until:
            self.intervals[key].append((clipped_start, clipped_until, start, until, digest, source))
        counts = collections.Counter()
        first_valid = last_valid = None
        # Each slice respects the actual timestamp phase, including midnight offsets.
        index = max(0, ceil_div(self.start - start, step))
        stop = min(len(values), max(0, ceil_div(self.until - start, step)))
        while index < stop:
            stamp = start + index * step
            day = stamp // DAY * DAY
            next_index = min(stop, ceil_div(day + DAY - start, step))
            block = values[index:next_index]
            finite = []
            null_n = nonfinite_n = zero_n = negative_n = 0
            for offset, value in enumerate(block):
                if value is None:
                    null_n += 1
                elif isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("non-numeric raw core value in " + source)
                elif not math.isfinite(value):
                    nonfinite_n += 1
                else:
                    finite.append(value)
                    zero_n += value == 0
                    negative_n += value < 0
                    value_stamp = start + (index + offset) * step
                    if first_valid is None:
                        first_valid = value_stamp
                    last_valid = value_stamp
            valid_n = len(finite)
            stats = self.daily.setdefault((country, signal, day), [0.0, 0, 0, 0, 0, 0, 0, set()])
            stats[0] += math.fsum(finite)
            for pos, value in enumerate((valid_n, len(block), null_n, nonfinite_n, zero_n, negative_n), 1):
                stats[pos] += value
            stats[7].add(source)
            for field, value in (("valid_n", valid_n), ("returned_n", len(block)), ("null_n", null_n),
                                 ("nonfinite_n", nonfinite_n), ("zero_n", zero_n), ("negative_n", negative_n)):
                counts[field] += value
            index = next_index
        self.series_audit.append({"source_file": source, "country_code": country, "signal": signal,
                                  "from_epoch": start, "until_epoch_exclusive": until,
                                  "step_seconds": step, "native_step_seconds": native,
                                  "timestamp_phase_seconds": start % step, "source_values_n": len(values),
                                  "source_values_sha256": digest, "first_valid_epoch_in_year": first_valid,
                                  "last_valid_epoch_in_year": last_valid, **counts})

    def daily_rows(self):
        for country in self.countries:
            for signal in CORE:
                key = (country, signal)
                cadence = self.cadence.get(key)
                denominator_source = "country_signal_observed_cadence"
                if cadence is None:
                    candidates = self.global_cadence[signal]
                    if len(candidates) == 1:
                        cadence = next(iter(candidates))
                        denominator_source = "signal_cadence_inferred_no_country_series"
                    else:
                        denominator_source = "unknown_no_unique_signal_cadence"
                for day in range(self.start, self.until, DAY):
                    total, valid, returned, null, nonfinite, zero, negative, sources = self.daily.get(
                        (country, signal, day), (0, 0, 0, 0, 0, 0, 0, set()))
                    expected = slot_count(day, day + DAY, cadence[0], cadence[2]) if cadence else None
                    if expected is not None and returned > expected:
                        raise ValueError("returned points exceed daily denominator: " + repr((country, signal, day)))
                    yield {"country_code": country, "country_name": self.names.get(country, ""),
                           "signal": signal, "date_utc": dt.datetime.fromtimestamp(day, UTC).date().isoformat(),
                           "mean_raw": total / valid if valid else None,
                           "valid_n": valid, "returned_n": returned, "null_n": null,
                           "nonfinite_n": nonfinite, "zero_n": zero, "negative_n": negative,
                           "step_seconds": cadence[0] if cadence else None,
                           "native_step_seconds": cadence[1] if cadence else None,
                           "timestamp_phase_seconds": cadence[2] if cadence else None,
                           "expected_slots": expected, "absent_slots": expected - returned if expected is not None else None,
                           "valid_fraction": valid / expected if expected else None,
                           "missing_fraction": (expected - valid) / expected if expected else None,
                           "zero_fraction_valid": zero / valid if valid else None,
                           "zero_fraction_expected": zero / expected if expected else None,
                           "denominator_source": denominator_source,
                           "source_status": "no_country_signal_series" if key not in self.cadence else
                           ("no_returned_slots_on_day" if not returned else ("returned_all_invalid" if not valid else "has_valid_values")),
                           "source_file_count": len(sources)}


def write_csv(path, rows):
    with Path(path).open("x", encoding="utf-8", newline="") as handle:
        rows = iter(rows)
        first = next(rows, None)
        if first is None:
            return
        writer = csv.DictWriter(handle, fieldnames=list(first))
        writer.writeheader()
        writer.writerow(first)
        writer.writerows(rows)


def read_source(path, root):
    metadata_path = path.with_name(path.name.replace(".json.gz", ".metadata.json"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    digest = sha256(path)
    if digest != metadata["sha256"] or path.stat().st_size != metadata["bytes"]:
        raise ValueError("metadata SHA256/bytes mismatch: " + str(path))
    with gzip.open(str(path), "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("error") is not None or payload.get("type") != "signals":
        raise ValueError("not a successful raw signal response: " + str(path))
    if "/signals/raw/country/" not in metadata.get("url", ""):
        raise ValueError("source URL is not raw country signals: " + str(path))
    source = str(path.relative_to(root))
    manifest = {"source_file": source, "sha256": digest, "bytes": path.stat().st_size,
                "metadata_file": str(metadata_path.relative_to(root)), "metadata_sha256": sha256(metadata_path),
                "source_url": metadata["url"], "retrieved_utc": metadata.get("retrieved_utc"),
                "request_from": payload["requestParameters"]["from"],
                "request_until_exclusive": payload["requestParameters"]["until"],
                "year": metadata["year"], "quarter": metadata["quarter"],
                "requested_countries": metadata["countries"]}
    return payload, metadata, manifest


def build(root, out, year):
    out.mkdir(parents=True, exist_ok=False)
    plan_path = root / "download_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    agg = Aggregator(year, plan["codes"])
    manifests = []
    paths = sorted((root / "raw_country_batches").glob("%s_Q*_batch*.json.gz" % year))
    paths += sorted((root / "raw_core_signals").glob("%s*.json.gz" % year))
    if not paths:
        raise ValueError("no raw files for requested year")
    try:
        for i, path in enumerate(paths, 1):
            payload, metadata, manifest = read_source(path, root)
            if metadata["year"] != year:
                raise ValueError("source metadata year differs from requested year")
            manifests.append(manifest)
            actual_meta = []
            for group in payload["data"]:
                if not isinstance(group, list):
                    raise ValueError("expected nested signal data array")
                for series in group:
                    if series.get("datasource") in CORE:
                        if series["entityCode"] not in metadata["countries"]:
                            raise ValueError("series country not in source request")
                        if not (manifest["request_from"] <= series["from"] < series["until"] <= manifest["request_until_exclusive"]):
                            raise ValueError("series interval outside source request")
                        actual_meta.append({"country": series["entityCode"], "signal": series["datasource"],
                                            "step": series["step"], "nativeStep": series["nativeStep"],
                                            "points": len(series["values"]),
                                            "nonmissing": sum(v is not None for v in series["values"]),
                                            "start": series["from"], "until": series["until"]})
                    agg.add(series, manifest["source_file"])
            if sorted(actual_meta, key=lambda x: (x["country"], x["signal"])) != sorted(metadata["core_signals"], key=lambda x: (x["country"], x["signal"])):
                raise ValueError("raw series and metadata core summary disagree: " + str(path))
            if i % 10 == 0 or i == len(paths):
                print("Validated and aggregated %d/%d source files" % (i, len(paths)), flush=True)
        # A full signal-level cadence is required to give every requested country a denominator.
        for signal in CORE:
            if len(agg.global_cadence[signal]) != 1:
                raise ValueError("no unique observed signal cadence for absent-series denominators: " + signal)
        daily_path = out / ("ioda_country_signal_day_%s.csv.gz" % year)
        annual = {}
        day_rows = 0
        with gzip.open(str(daily_path), "xt", encoding="utf-8", newline="") as handle:
            writer = None
            for row in agg.daily_rows():
                if writer is None:
                    writer = csv.DictWriter(handle, fieldnames=list(row))
                    writer.writeheader()
                writer.writerow(row)
                day_rows += 1
                key = row["country_code"], row["signal"]
                if key not in annual:
                    annual[key] = {"country_code": key[0], "country_name": row["country_name"], "signal": key[1],
                                   "year": year, "calendar_days": 0, "days_with_valid_values": 0,
                                   "days_valid_fraction_ge_0_8": 0,
                                   **{k: 0 for k in ("valid_n", "returned_n", "null_n", "nonfinite_n", "zero_n", "negative_n", "expected_slots", "absent_slots")},
                                   "step_seconds": row["step_seconds"], "native_step_seconds": row["native_step_seconds"],
                                   "timestamp_phase_seconds": row["timestamp_phase_seconds"],
                                   "denominator_source": row["denominator_source"], "_total": 0.0}
                a = annual[key]
                a["calendar_days"] += 1
                a["days_with_valid_values"] += row["valid_n"] > 0
                a["days_valid_fraction_ge_0_8"] += row["valid_fraction"] >= 0.8
                for field in ("valid_n", "returned_n", "null_n", "nonfinite_n", "zero_n", "negative_n", "expected_slots", "absent_slots"):
                    a[field] += row[field]
                if row["valid_n"]:
                    a["_total"] += row["mean_raw"] * row["valid_n"]
        for a in annual.values():
            total = a.pop("_total")
            a["mean_raw"] = total / a["valid_n"] if a["valid_n"] else None
            a["valid_fraction"] = a["valid_n"] / a["expected_slots"]
            a["missing_fraction"] = 1 - a["valid_fraction"]
            a["zero_fraction_valid"] = a["zero_n"] / a["valid_n"] if a["valid_n"] else None
            a["zero_fraction_expected"] = a["zero_n"] / a["expected_slots"]
            a["annual_valid_fraction_ge_0_8"] = int(a["valid_fraction"] >= 0.8)
            a["full_observability_status"] = "NOT_ASSESSED_BASELINE_NEAR_ZERO_EVENT_AND_PLATFORM_SCREEN_PENDING"
        write_csv(out / ("ioda_country_signal_year_%s.csv" % year), annual.values())
        write_csv(out / "source_series_audit.csv", agg.series_audit)
        dump_json(out / "source_manifest.json", {"ioda_root": str(root), "download_plan_sha256": sha256(plan_path),
                                                  "download_plan_file": str(plan_path), "sources": manifests})
        dump_json(out / "duplicate_audit.json", {"records": agg.duplicates, "partial_overlaps_or_conflicts": 0})
        country_screen = []
        for country in agg.countries:
            flags = {s: annual[(country, s)]["annual_valid_fraction_ge_0_8"] for s in CORE}
            country_screen.append({"country_code": country, "year": year,
                                   "ap_annual_valid_fraction_ge_0_8": flags["ping-slash24"],
                                   "bgp_annual_valid_fraction_ge_0_8": flags["bgp"],
                                   "merit_nt_annual_valid_fraction_ge_0_8": flags["merit-nt"],
                                   "ap_and_any_validation_coverage_only": int(flags["ping-slash24"] and (flags["bgp"] or flags["merit-nt"])),
                                   "full_observability_pass": "NOT_ASSESSED"})
        write_csv(out / "country_coverage_screen.csv", country_screen)
        summary = {"year": year, "calendar_days": (agg.until - agg.start) // DAY,
                   "countries_requested": len(agg.countries), "daily_rows": day_rows,
                   "annual_rows": len(annual), "raw_files": len(paths), "core_series_segments": len(agg.series_audit),
                   "excluded_noncore_series_by_datasource": dict(agg.excluded),
                   "exact_duplicate_segments_deduplicated": len(agg.duplicates),
                   "partial_overlaps_or_conflicts": 0,
                   "countries_ap_plus_validation_at_80pct_coverage_only": sum(r["ap_and_any_validation_coverage_only"] for r in country_screen),
                   "signals": {}}
        for signal in CORE:
            rows = [a for a in annual.values() if a["signal"] == signal]
            expected, valid = (sum(a[k] for a in rows) for k in ("expected_slots", "valid_n"))
            summary["signals"][signal] = {"step_seconds": next(iter(agg.global_cadence[signal]))[0],
                                           "countries_with_any_valid_values": sum(a["valid_n"] > 0 for a in rows),
                                           "countries_annual_valid_fraction_ge_0_8": sum(a["annual_valid_fraction_ge_0_8"] for a in rows),
                                           "countries_no_returned_series": sum((a["country_code"], signal) not in agg.cadence for a in rows),
                                           **{k: sum(a[k] for a in rows) for k in ("valid_n", "returned_n", "null_n", "nonfinite_n", "zero_n", "negative_n", "expected_slots", "absent_slots")},
                                           "pooled_valid_fraction": valid / expected,
                                           "all_zero_among_observed_countries": [a["country_code"] for a in rows if a["valid_n"] and a["valid_n"] == a["zero_n"]]}
        dump_json(out / "summary.json", summary)
        dump_json(out / "method.json", {
            "created_utc": dt.datetime.now(UTC).isoformat(), "python_version": platform.python_version(),
            "script": str(Path(__file__).resolve()), "script_sha256": sha256(Path(__file__)),
            "year": year, "period_from_epoch": agg.start, "period_until_exclusive_epoch": agg.until,
            "unit": "country x raw core datasource x UTC calendar day; raw signal units retained per datasource",
            "timestamps": "t_i = series.from + i * series.step; series.until exclusive; actual offset retained; UTC timestamp assigns day",
            "mean_raw": "arithmetic mean of finite numeric returned values, including genuine zero; missing when no finite values; no interpolation",
            "valid_n": "finite numeric returned observations; bool/string rejected; negative values retained and counted separately",
            "missing": "null_n and nonfinite_n are explicit returned invalid values; absent_slots=expected_slots-returned_n; missing_fraction=(expected_slots-valid_n)/expected_slots",
            "expected_slots": "full UTC-day or full calendar-year grid, using observed per-country cadence and phase; absent country series use unique same-signal cadence, explicitly flagged; denominator never restricted to observed dates",
            "step_validation": "step must equal nativeStep; changes in per-country step/phase or lack of unique signal cadence fail instead of inventing denominators",
            "duplicates": "exact duplicate interval plus values SHA256 deduplicated and logged; differing same-interval values and partial overlaps fail; no silent conflict precedence",
            "scope": "only requested year; only raw_country_batches and raw_core_signals; no alerts, historical snapshots, normalized signals, or probe duplicates",
            "coverage_threshold": "annual valid_fraction >= 0.8 is proposal condition 1 only; AP plus BGP/Telescope coverage does not satisfy baseline, near-zero, platform or event-window screening",
            "limitations": ["not an effect estimate, connectivity loss, DHRD or outage-person count", "zero fraction is descriptive, no near-zero cutoff has been chosen", "no historical 2018-2025 availability claim", "no STOP, cyclone or synchronized-platform anomaly exclusions performed", "timestamps are UTC, not local or population local day"],
            "daily_columns": list(next(agg.daily_rows())), "annual_columns": list(next(iter(annual.values()))),
        })
        checksums = {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()}
        dump_json(out / "output_checksums.json", checksums)
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    except Exception as exc:
        dump_json(out / "FAILED.json", {"error": str(exc), "exception": type(exc).__name__, "validated_source_files": len(manifests),
                                        "duplicate_records": agg.duplicates, "status": "INCOMPLETE_DO_NOT_USE"})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ioda-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="New directory; refuses to overwrite existing outputs")
    parser.add_argument("--year", type=int, default=2024)
    args = parser.parse_args()
    build(args.ioda_root.resolve(), args.out.resolve(), args.year)


if __name__ == "__main__":
    main()
