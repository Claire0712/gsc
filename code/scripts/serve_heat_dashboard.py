#!/usr/bin/env python3
"""Private, read-only HeatSignal workbench; no raw-directory serving."""
import argparse
import calendar
import csv
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit


def now():
    return datetime.now(timezone.utc).isoformat()


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def check_liveness(state):
    state = dict(state)
    if state.get('state') == 'running' and isinstance(state.get('pid'), int):
        try:
            os.kill(state['pid'], 0)
            proc = Path('/proc') / str(state['pid']) / 'stat'
            if proc.exists() and proc.read_text().split(') ', 1)[1].startswith('Z '):
                raise ProcessLookupError('Zombie process')
        except ProcessLookupError:
            state.update(state='interrupted', note='进程已结束，但尚未写入完成状态，请检查日志')
        except PermissionError:
            state.update(state='unknown', note='无法核验进程状态')
    return state


def job_status(directory):
    candidates = []
    summary = None
    for name in ('summary.json', 'progress.json'):
        path = directory / name
        if path.exists():
            try:
                value = read_json(path)
                candidates.append((str(value.get('updated_utc', '')), path.stat().st_mtime_ns, value))
                if name == 'summary.json':
                    summary = value
            except (ValueError, OSError):
                return {'state': 'error', 'note': '状态文件无法读取'}
    if not candidates:
        return {'state': 'pending'}
    latest = max(candidates, key=lambda item: item[:2])[2]
    complete = {'complete', 'completed'}
    if summary and summary.get('state') in complete and latest.get('state') in complete:
        latest = {**summary, **latest}
    return check_liveness(latest)


class Dashboard:
    def __init__(self, era5_dir, prep_dir, assets):
        self.era = Path(era5_dir)
        self.prep = Path(prep_dir)
        self.assets = Path(assets)
        with (self.era / 'weights/country_metadata.csv').open() as handle:
            self.countries = [{**row, 'total_population': number(row['total_population'])}
                              for row in csv.DictReader(handle)]
        self.ids = {row['country_id'] for row in self.countries}
        if len(self.ids) != len(self.countries):
            raise ValueError('Duplicate country IDs in metadata')
        self.invalid_months = []

    @lru_cache(maxsize=192)
    def _verified(self, month, csv_mtime, csv_size, audit_mtime, audit_size):
        path = self.era / 'country_daily' / f'era5_country_daily_{month}.csv'
        try:
            audit = read_json(path.with_suffix('.audit.json'))
            with path.open('rb') as handle:
                digest = hashlib.file_digest(handle, 'sha256').hexdigest()
            return digest == audit.get('output_sha256')
        except (ValueError, OSError):
            return False

    def months(self, year=None, verify=False):
        months = []
        invalid = []
        for p in sorted((self.era / 'country_daily').glob('era5_country_daily_*.csv')):
            month = p.stem.removeprefix('era5_country_daily_')
            if not re.fullmatch(r'20\d{2}(0[1-9]|1[0-2])', month):
                continue
            if not 2018 <= int(month[:4]) <= 2025:
                continue
            if year is not None and int(month[:4]) != year:
                continue
            if p.with_suffix('.audit.json').exists():
                if verify:
                    cstat = p.stat()
                    astat = p.with_suffix('.audit.json').stat()
                    if not self._verified(month, cstat.st_mtime_ns, cstat.st_size, astat.st_mtime_ns, astat.st_size):
                        invalid.append(month)
                        continue
                months.append(month)
        if verify:
            self.invalid_months = invalid
        return months

    def status(self):
        status_path = self.era / 'status.json'
        state = check_liveness(read_json(status_path)) if status_path.exists() else {'state': 'pending'}
        state = {key: state[key] for key in ('state', 'updated_utc', 'stage') if key in state}
        months = self.months(verify=True)
        state.update(completed_months=len(months), total_months=96,
                     latest_month=months[-1] if months else None, invalid_months=self.invalid_months)
        if self.invalid_months:
            state.update(state='error', note='存在校验失败的月度输出，已从完成数量中排除')
        return {'updated_utc': now(), 'era5': state,
                'ioda': job_status(self.prep / 'ioda'),
                'auxiliary': job_status(self.prep / 'auxiliary'),
                'analysis': {'state': 'pending', 'note': '热事件、连接基线和韧性指标尚未计算'}}

    @lru_cache(maxsize=24)
    def _month_rows(self, month, country, csv_mtime, audit_mtime):
        path = self.era / 'country_daily' / f'era5_country_daily_{month}.csv'
        payload = path.read_bytes()
        audit = read_json(path.with_suffix('.audit.json'))
        if hashlib.sha256(payload).hexdigest() != audit.get('output_sha256'):
            raise ValueError('ERA5 monthly output failed checksum verification')
        rows = []
        dates = set()
        for row in csv.DictReader(payload.decode('utf-8').splitlines()):
            if row['country_id'] != country:
                continue
            date = datetime.strptime(row['date'], '%Y-%m-%d').date()
            if date.strftime('%Y%m') != month or row['date'] in dates:
                raise ValueError('Unexpected or duplicate date in ERA5 output')
            dates.add(row['date'])
            rows.append({'date': row['date'], **{key: number(row.get(key)) for key in
                                                 ('tmax_c', 'tmin_c', 'dewpoint_c')}})
        return sorted(rows, key=lambda row: row['date'])

    def climate(self, country, year):
        if country not in self.ids or not 2018 <= year <= 2025:
            raise ValueError('Invalid country or year')
        months = self.months(year)
        rows = []
        for month in months:
            path = self.era / 'country_daily' / f'era5_country_daily_{month}.csv'
            rows.extend(self._month_rows(month, country, path.stat().st_mtime_ns,
                                        path.with_suffix('.audit.json').stat().st_mtime_ns))
        complete = len(months) == 12 and len(rows) == (366 if calendar.isleap(year) else 365)
        return {'country_id': country, 'year': year, 'rows': rows, 'day_definition': 'UTC',
                'available_months': months, 'complete_year': complete,
                'source': 'ERA5 pixel-first daily extrema, fixed WorldPop 2025 weights',
                'note': 'Tmax 为人口加权的像元日最高温，不是全国单点最高温。零人口单元结果缺失。'}

    def selection(self, query):
        params = parse_qs(query, keep_blank_values=True)
        if set(params) != {'country', 'year'} or any(len(v) != 1 for v in params.values()):
            raise ValueError('Exactly one country and year required')
        country, year_raw = params['country'][0], params['year'][0]
        if country not in self.ids or not re.fullmatch(r'20\d{2}', year_raw):
            raise ValueError('Invalid selection')
        year = int(year_raw)
        if not 2018 <= year <= 2025:
            raise ValueError('Year outside available period')
        return country, year

    def route(self, target):
        url = urlsplit(target)
        static = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/index.html': ('index.html', 'text/html; charset=utf-8'),
                  '/app.css': ('app.css', 'text/css; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/map.geojson': ('map.geojson', 'application/geo+json')}
        if url.path in static:
            name, mime = static[url.path]
            path = self.assets / name
            if path.is_file() and not path.is_symlink():
                return 200, mime, path.read_bytes()
        routes = {'/api/status', '/api/countries', '/api/climate', '/api/quality', '/api/events'}
        if url.path not in routes:
            return 404, 'text/plain; charset=utf-8', b'Not found'
        if url.path in {'/api/climate', '/api/events'}:
            try:
                country, year = self.selection(url.query)
            except ValueError:
                return 400, 'application/json', b'{"error":"Invalid country/year selection"}'
        if url.path == '/api/status':
            result = self.status()
        elif url.path == '/api/countries':
            result = {'countries': self.countries}
        elif url.path == '/api/climate':
            result = self.climate(country, year)
        elif url.path == '/api/events':
            result = {'state': 'pending', 'events': [], 'note': '热事件与韧性指标尚未计算'}
        else:
            result = {key: job_status(self.prep / folder) for key, folder in
                      [('ioda', 'ioda'), ('auxiliary', 'auxiliary')]}
        return 200, 'application/json; charset=utf-8', json.dumps(result, ensure_ascii=False, allow_nan=False).encode()


def handler_for(app, port):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'HeatSignal/0.1'

        def do_GET(self):
            # Loopback binding + host allowlist prevent accidental public use / DNS rebinding.
            host = self.headers.get('Host', '').split(':')[0]
            if host not in ('127.0.0.1', 'localhost'):
                self.send_error(403)
                return
            try:
                code, mime, body = app.route(self.path)
            except Exception as exc:
                print(json.dumps({'utc': now(), 'error': type(exc).__name__, 'message': str(exc)}), flush=True)
                code, mime, body = 503, 'application/json', b'{"error":"Data unavailable or validation failed"}'
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)
    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--era5-dir', type=Path, required=True)
    p.add_argument('--prep-dir', type=Path, required=True)
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--port', type=int, default=8787)
    args = p.parse_args()
    app = Dashboard(args.era5_dir, args.prep_dir, args.assets)
    server = HTTPServer(('127.0.0.1', args.port), handler_for(app, args.port))
    server.timeout = 10
    print(json.dumps({'state': 'serving', 'pid': os.getpid(), 'bind': '127.0.0.1', 'port': args.port, 'utc': now()}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
