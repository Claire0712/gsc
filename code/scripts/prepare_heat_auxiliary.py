#!/usr/bin/env python3
"""Prepare existing HeatSignal auxiliary CSVs; preserve every source record.

No downloads, date imputation, fuzzy country matching, or future-year backfill.
Only Python's standard library is required. source_row is the one-based data
record index, excluding the CSV header (not a physical line number).
"""
import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile


INPUTS = {
    "stop": "stop/STOP_combined_2016_2025.csv",
    "ibtracs": "ibtracs/ibtracs_2018_2025_UTC.csv",
    "worldbank": "worldbank/country_year_indicators_2018_2025.csv",
    "crosswalk": "metadata/ioda_worldbank_crosswalk.csv",
}
INDICATORS = {
    "EG.ELC.ACCS.ZS": ("electricity_access", "electricity_access_share", True),
    "IT.NET.USER.ZS": ("internet", "internet_share", True),
    "NY.GDP.PCAP.PP.KD": ("gdp_per_capita_ppp", "gdp_per_capita_ppp", False),
    "SP.POP.TOTL": ("population", "population", False),
    "SP.URB.TOTL.IN.ZS": ("urban_population", "urban_population_share", True),
}
MISSING = {"", "na", "n/a", "nan", "null", "none", ".."}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint(path):
    path = Path(path).resolve()
    before = path.stat()
    digest = sha256(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("Source changed while hashing: " + str(path))
    return {"path": str(path), "size_bytes": after.st_size, "mtime_ns": after.st_mtime_ns, "sha256": digest}


def atomic_write(path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path, value):
    atomic_write(path, lambda handle: json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False))


def read_csv(path, required=()):
    """Stream records while refusing malformed headers or mismatched field counts."""
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if not fields or len(set(fields)) != len(fields) or any(not field for field in fields):
            raise ValueError("Invalid or duplicate CSV header: " + str(path))
        if set(required) - set(fields):
            raise ValueError("Missing required columns: " + ", ".join(sorted(set(required) - set(fields))))
        for index, row in enumerate(reader, 1):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV field count differs at source_row={index}: {path}")
            yield index, row


def csv_fields(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return next(csv.reader(handle))


def write_csv(path, fields, rows):
    if len(fields) != len(set(fields)):
        raise ValueError("Source columns collide with generated preparation columns")
    def write(handle):
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    atomic_write(path, write)


def flag_text(flags):
    return "|".join(sorted(set(flags)))


def number(raw):
    text = str(raw).strip()
    if text.lower() in MISSING:
        return None, "missing"
    try:
        value = float(text)
    except ValueError:
        return None, "invalid"
    return (value, "valid") if math.isfinite(value) else (None, "invalid")


def parse_date(raw):
    text = raw.strip()
    if not text:
        return None, "missing"
    # Only unambiguous ISO calendar dates/timestamps. Free text is preserved.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?", text):
        return None, "invalid"
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).date(), "valid"
    except ValueError:
        return None, "invalid"


def load_crosswalk(path):
    rows = [row for _, row in read_csv(path, ("ioda_iso2", "ioda_name", "worldbank_iso3", "worldbank_name", "mapping_status"))]
    codes = [row["ioda_iso2"].strip() for row in rows]
    if any(not code for code in codes) or len(set(codes)) != len(codes):
        raise ValueError("Crosswalk IODA ISO2 codes must be nonempty and unique")
    return rows


def country_name_index(crosswalk, wb_rows):
    names = defaultdict(set)
    for row in crosswalk:
        if row["mapping_status"] == "exact_iso2_match" and row["worldbank_iso3"].strip():
            for field in ("ioda_name", "worldbank_name"):
                if row[field].strip():
                    names[row[field].strip()].add(row["worldbank_iso3"].strip())
    for row in wb_rows:
        if row["country"].strip() and re.fullmatch(r"[A-Z]{3}", row["iso3"].strip()):
            names[row["country"].strip()].add(row["iso3"].strip())
    return names


STOP_EXTRA = ["source_row", "normalized_start_date", "normalized_end_date", "date_interval_status",
              "bounded_interval_eligible", "interval_days_inclusive", "normalized_geo_scope",
              "matched_worldbank_iso3", "country_match_status", "qa_flags"]


def prepare_stop(source, output, names):
    qa = Counter()
    matches = Counter()
    scopes = Counter()
    summary = {"source_rows": 0, "rows": 0, "bounded_intervals": 0, "output": output.name}
    scope_map = {
        "It only affected one city, county, or village": "single_locality",
        "It affected more than one city in the same state, province, or region": "multiple_localities_within_admin1",
        "It affected locations in more than one state, province, or region": "multiple_admin1",
    }
    def records():
        for index, raw in read_csv(source, ("start_date", "end_date", "country", "geo_scope", "area_name", "start_date_type")):
            flags = []
            start, start_status = parse_date(raw["start_date"])
            end, end_status = parse_date(raw["end_date"])
            if start_status != "valid":
                flags.append("start_date_" + start_status)
            if end_status != "valid":
                flags.append("end_date_" + end_status)
            status = "complete" if start and end else "incomplete"
            if start and end and end < start:
                flags.append("date_range_reversed")
                status = "reversed"
            if raw["start_date_type"].strip().lower() == "estimated":
                flags.append("start_date_estimated")
            elif not raw["start_date_type"].strip():
                flags.append("start_date_type_missing")
            country = raw["country"].strip()
            matched = ""
            if ";" in country:
                flags.append("multiple_countries")
                match_status = "multiple_countries_unresolved"
            elif len(names.get(country, ())) == 1:
                matched = next(iter(names[country]))
                match_status = "exact_name_match"
            elif len(names.get(country, ())) > 1:
                match_status = "ambiguous_exact_name"
            else:
                match_status = "unmatched_exact_name"
            if not matched:
                flags.append(match_status)
            scope = scope_map.get(raw["geo_scope"].strip(), "unknown")
            if scope == "unknown":
                flags.append("scope_unresolved")
            eligible = status == "complete"
            row = dict(raw, source_row=index, normalized_start_date=start.isoformat() if start else "",
                       normalized_end_date=end.isoformat() if end else "", date_interval_status=status,
                       bounded_interval_eligible=int(eligible),
                       interval_days_inclusive=(end - start).days + 1 if eligible else "",
                       normalized_geo_scope=scope, matched_worldbank_iso3=matched,
                       country_match_status=match_status, qa_flags=flag_text(flags))
            summary["source_rows"] += 1
            summary["rows"] += 1
            summary["bounded_intervals"] += int(eligible)
            qa.update(set(flags))
            matches[match_status] += 1
            scopes[scope] += 1
            yield row
    write_csv(output, csv_fields(source) + STOP_EXTRA, records())
    summary.update(qa_counts=dict(qa), country_match_counts=dict(matches), scope_counts=dict(scopes))
    return summary


IBTRACS_EXTRA = ["source_row", "normalized_sid", "normalized_time_utc", "normalized_latitude",
                 "normalized_longitude", "normalized_wmo_wind", "duplicate_sid_time",
                 "conflicting_sid_time", "qa_flags"]


def normalize_track(raw):
    flags = []
    sid = raw["SID"].strip()
    if not sid:
        flags.append("sid_missing")
    text = raw["ISO_TIME"].strip()
    normalized_time = ""
    if text:
        try:
            if not re.match(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}", text):
                raise ValueError("timestamp must contain date and seconds")
            parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
            parsed = parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed.astimezone(dt.timezone.utc)
            normalized_time = parsed.isoformat().replace("+00:00", "Z")
            if parsed.year < 2018 or parsed.year > 2025:
                flags.append("time_outside_2018_2025")
        except ValueError:
            flags.append("time_invalid")
    else:
        flags.append("time_missing")
    lat, lat_status = number(raw["LAT"])
    if lat is not None and not -90 <= lat <= 90:
        lat, lat_status = None, "invalid"
    if lat_status != "valid":
        flags.append("latitude_" + lat_status)
    lon, lon_status = number(raw["LON"])
    # Accept documented geographic representations only; do not wrap sentinels.
    if lon is not None and not -180 <= lon <= 360:
        lon, lon_status = None, "invalid"
    if lon_status != "valid":
        flags.append("longitude_" + lon_status)
    elif not -180 <= lon < 180:
        flags.append("longitude_wrapped")
    normalized_lon = (lon + 180) % 360 - 180 if lon is not None else ""
    wind, wind_status = number(raw.get("WMO_WIND", ""))
    if wind is not None and wind < 0:
        wind, wind_status = None, "invalid"
    if wind_status != "valid":
        flags.append("wmo_wind_" + wind_status)
    return {"normalized_sid": sid, "normalized_time_utc": normalized_time,
            "normalized_latitude": lat if lat is not None else "", "normalized_longitude": normalized_lon,
            "normalized_wmo_wind": wind if wind is not None else ""}, flags


def prepare_ibtracs(source, output, progress):
    # Two streaming passes retain only key/count/digest state, not the 180-column table.
    groups = {}
    required = ("SID", "ISO_TIME", "LAT", "LON", "SEASON", "NAME", "TRACK_TYPE")
    for index, raw in read_csv(source, required):
        normal, _ = normalize_track(raw)
        key = (normal["normalized_sid"], normal["normalized_time_utc"])
        if all(key):
            digest = hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            group = groups.setdefault(key, [0, digest, False])
            group[0] += 1
            group[2] |= digest != group[1]
        if index % 10000 == 0:
            progress("ibtracs_index", index)
    summary = {"source_rows": 0, "rows": 0, "output": output.name,
               "duplicate_sid_time_groups": sum(value[0] > 1 for value in groups.values()),
               "conflicting_sid_time_groups": sum(value[2] for value in groups.values())}
    qa = Counter()
    def records():
        for index, raw in read_csv(source, required):
            normal, flags = normalize_track(raw)
            group = groups.get((normal["normalized_sid"], normal["normalized_time_utc"]), [1, "", False])
            duplicate, conflicting = group[0] > 1, group[2]
            if duplicate:
                flags.append("duplicate_sid_time")
            if conflicting:
                flags.append("conflicting_sid_time")
            summary["source_rows"] += 1
            summary["rows"] += 1
            qa.update(set(flags))
            if index % 10000 == 0:
                progress("ibtracs_write", index)
            yield dict(raw, source_row=index, **normal, duplicate_sid_time=int(duplicate),
                       conflicting_sid_time=int(conflicting), qa_flags=flag_text(flags))
    write_csv(output, csv_fields(source) + IBTRACS_EXTRA, records())
    summary["qa_counts"] = dict(qa)
    return summary


def clean_worldbank(source):
    rows = []
    groups = defaultdict(list)
    for index, raw in read_csv(source, ("iso3", "country", "year", *INDICATORS)):
        flags = []
        iso3 = raw["iso3"].strip()
        if not re.fullmatch(r"[A-Z]{3}", iso3):
            flags.append("iso3_invalid")
        year = int(raw["year"].strip()) if re.fullmatch(r"\d{4}", raw["year"].strip()) else None
        if year is None:
            flags.append("year_invalid")
        elif not 2018 <= year <= 2025:
            flags.append("year_outside_2018_2025")
        row = dict(raw, source_row=index, normalized_iso3=iso3, normalized_year=year or "")
        for indicator, (prefix, output_name, percent) in INDICATORS.items():
            value, status = number(raw[indicator])
            if value is not None and (value < 0 or (percent and value > 100)):
                value, status = None, "percent_out_of_range" if percent else "negative"
            if status != "valid":
                flags.append(prefix + "_" + status)
            row["normalized_" + output_name] = (value / 100 if percent else value) if value is not None else ""
        row["_flags"] = flags
        rows.append(row)
        if year is not None and re.fullmatch(r"[A-Z]{3}", iso3):
            groups[iso3, year].append(row)
    for group in groups.values():
        if len(group) > 1:
            fingerprints = {tuple(row[indicator].strip() for indicator in INDICATORS) for row in group}
            for row in group:
                row["_flags"].append("duplicate_country_year")
                if len(fingerprints) > 1:
                    row["_flags"].append("conflicting_country_year")
    qa = Counter()
    for row in rows:
        flags = row.pop("_flags")
        row["qa_flags"] = flag_text(flags)
        qa.update(set(flags))
    usable = {key: group[0] for key, group in groups.items()
              if "conflicting_country_year" not in group[0]["qa_flags"]}
    return rows, usable, dict(qa)


def choose_indicator(index, iso3, year, indicator, prior_only=False):
    prefix, output_name, _ = INDICATORS[indicator]
    for source_year in range(year - int(prior_only), year - 4, -1):
        row = index.get((iso3, source_year))
        if row and row["normalized_" + output_name] != "":
            return {output_name: row["normalized_" + output_name], prefix + "_source_year": source_year,
                    prefix + "_lag_years": year - source_year, prefix + "_source_row": row["source_row"],
                    prefix + "_status": "current_year" if year == source_year else "lagged"}
    return {output_name: "", prefix + "_source_year": "", prefix + "_lag_years": "",
            prefix + "_source_row": "", prefix + "_status": "missing_in_allowed_window"}


def prepare_worldbank(source, output_dir, crosswalk):
    rows, index, qa = clean_worldbank(source)
    clean_path = output_dir / "worldbank_cleaned.csv"
    extra = ["source_row", "normalized_iso3", "normalized_year"] + ["normalized_" + item[1] for item in INDICATORS.values()] + ["qa_flags"]
    write_csv(clean_path, csv_fields(source) + extra, rows)
    base_fields = ["ioda_iso2", "ioda_name", "worldbank_iso3", "worldbank_name", "mapping_status", "year", "release_date_known"]
    dlep, capability = [], []
    statuses = Counter()
    for country in crosswalk:
        for year in range(2022, 2026):
            base = {field: country[field] for field in base_fields[:5]}
            base.update(year=year, release_date_known=0)
            matched = country["mapping_status"] == "exact_iso2_match" and bool(country["worldbank_iso3"].strip())
            iso3 = country["worldbank_iso3"].strip() if matched else ""
            selected = choose_indicator(index, iso3, year, "IT.NET.USER.ZS")
            if not matched:
                selected["internet_status"] = "unmatched_crosswalk"
            statuses[selected["internet_status"]] += 1
            dlep.append(dict(base, **selected))
            prior = dict(base)
            for indicator, (prefix, _, _) in INDICATORS.items():
                values = choose_indicator(index, iso3, year, indicator, prior_only=True)
                if not matched:
                    values[prefix + "_status"] = "unmatched_crosswalk"
                prior.update(values)
            capability.append(prior)
    dlep_path = output_dir / "worldbank_dlep_2022_2025.csv"
    prior_path = output_dir / "worldbank_prior_year_capability_2022_2025.csv"
    indicator_fields = lambda prefix, value: [value, prefix + "_source_year", prefix + "_lag_years", prefix + "_source_row", prefix + "_status"]
    write_csv(dlep_path, base_fields + indicator_fields("internet", "internet_share"), dlep)
    write_csv(prior_path, base_fields + [field for prefix, value, _ in INDICATORS.values() for field in indicator_fields(prefix, value)], capability)
    summary = {"source_rows": len(rows), "rows": len(rows), "output": clean_path.name,
               "qa_counts": qa, "dlep_rows": len(dlep), "dlep_output": dlep_path.name,
               "dlep_status_counts": dict(statuses), "capability_rows": len(capability),
               "capability_output": prior_path.name, "crosswalk_units": len(crosswalk),
               "crosswalk_unmatched_units": sum(row["mapping_status"] != "exact_iso2_match" or not row["worldbank_iso3"].strip() for row in crosswalk)}
    return summary, rows


NOTES = [
    "Raw columns and all records are retained; source_row is a one-based data record index excluding the header, not a physical line number.",
    "STOP dates retain the source calendar date; no timezone is asserted. Missing or free-text end dates are never filled, extended, or treated as infinite intervals.",
    "STOP scope is normalized only from geo_scope; area_name or country matching never implies national exposure. Bounded interval eligibility is a date-quality flag, not an exclusion rule.",
    "STOP country names use exact case-sensitive trimmed names from the supplied crosswalk and World Bank table; ambiguous, multi-country, and unmatched names remain unresolved.",
    "IBTrACS timestamps without an explicit offset are UTC as specified by the source filename. Longitude representations in [-180,360] are normalized to [-180,180); invalid sentinels stay missing.",
    "IBTrACS duplicate groups use normalized SID and UTC timestamp; conflicts mean any raw field differs. Every duplicate is retained. Wind values retain source units and no agency conversion is applied.",
    "World Bank DLEP internet share uses the latest nonmissing valid percentage at target year or up to three years earlier, divided by 100; no future backfill, no missing-to-zero conversion.",
    "Prior-year capability uses only source years target_year-1 through target_year-3. Source years and lags are explicit; publication/release dates are unknown and no real-time availability claim is made.",
    "Conflicting World Bank country-year duplicates are retained in the cleaned table and excluded from both selection indices. Identical duplicates select the first source record.",
]


def prepare(data_root, output_dir):
    data_root, output_dir = Path(data_root).resolve(), Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {"state": "running", "updated_utc": now(), "stop": {}, "ibtracs": {}, "worldbank": {}, "notes": NOTES}
    def progress(stage, rows=0, state="running"):
        value = {"state": state, "stage": stage, "processed_rows": rows, "updated_utc": now(), "pid": os.getpid()}
        atomic_json(output_dir / "progress.json", value)
    progress("validate_inputs")
    atomic_json(output_dir / "summary.json", summary)
    try:
        sources = {key: data_root / relative for key, relative in INPUTS.items()}
        inputs = {key: fingerprint(path) for key, path in sources.items()}
        crosswalk = load_crosswalk(sources["crosswalk"])
        progress("worldbank")
        summary["worldbank"], wb_rows = prepare_worldbank(sources["worldbank"], output_dir, crosswalk)
        progress("stop")
        summary["stop"] = prepare_stop(sources["stop"], output_dir / "stop_cleaned.csv", country_name_index(crosswalk, wb_rows))
        progress("ibtracs_index")
        summary["ibtracs"] = prepare_ibtracs(sources["ibtracs"], output_dir / "ibtracs_cleaned.csv", progress)
        for key, path in sources.items():
            if fingerprint(path) != inputs[key]:
                raise RuntimeError("Source changed during preparation: " + str(path))
        summary.update(state="complete", updated_utc=now())
        atomic_json(output_dir / "summary.json", summary)
        outputs = ["stop_cleaned.csv", "ibtracs_cleaned.csv", "worldbank_cleaned.csv",
                   "worldbank_dlep_2022_2025.csv", "worldbank_prior_year_capability_2022_2025.csv", "summary.json"]
        manifest = {"schema_version": 1, "state": "complete", "updated_utc": now(),
                    "script_sha256": sha256(Path(__file__)), "inputs": inputs,
                    "outputs": {name: fingerprint(output_dir / name) for name in outputs},
                    "parameters": {"target_years": [2022, 2023, 2024, 2025], "maximum_lag_years": 3}}
        atomic_json(output_dir / "manifest.json", manifest)
        progress("complete", state="complete")
        return summary
    except Exception as error:
        summary.update(state="failed", updated_utc=now(), error_type=type(error).__name__, error=str(error))
        atomic_json(output_dir / "summary.json", summary)
        progress("failed", state="failed")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = prepare(args.data_root, args.output_dir)
    print(json.dumps({"state": summary["state"], "output_dir": str(args.output_dir.resolve()), "updated_utc": summary["updated_utc"]}))


if __name__ == "__main__":
    main()
