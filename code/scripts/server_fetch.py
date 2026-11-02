"""Fetch a single official climate artifact to the NAS; URL is supplied on stdin."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import urllib.request
import urllib.parse
import zipfile


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_path(root, relative):
    if Path(relative).is_absolute():
        raise ValueError('absolute target path')
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise ValueError('target escapes data root')
    return path


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def valid_range(status, header, offset, total):
    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', header or '')
    return bool(status == 206 and match and int(match[1]) == offset
                and int(match[2]) < total and int(match[3]) == total)


def inspect_format(path):
    with path.open('rb') as f:
        magic = f.read(8)
    if magic == b'\x89HDF\r\n\x1a\n' or magic[:3] == b'CDF':
        return '.nc'
    if magic[:2] == b'PK':
        with zipfile.ZipFile(path) as z:
            names = [x for x in z.namelist() if x.lower().endswith('.nc')]
            if not names or z.testzip() is not None:
                raise ValueError('ZIP has no NetCDF data or fails CRC')
            for name in names:
                with z.open(name) as f:
                    head = f.read(8)
                if not (head == b'\x89HDF\r\n\x1a\n' or head[:3] == b'CDF'):
                    raise ValueError('ZIP member is not NetCDF')
        return '.zip'
    raise ValueError('download is not a NetCDF/ZIP artifact')


def atomic_json(path, value):
    tmp = path.with_name(path.name + '.tmp.' + str(os.getpid()))
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def fetch(root, request):
    root = root.resolve()
    key = request['id']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', key):
        raise ValueError('invalid task identifier')
    url = request['url']
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password:
        raise ValueError('expected official HTTPS artifact URL')
    expected = int(request['bytes'])
    if expected <= 0:
        raise ValueError('invalid expected byte count')
    records = root / 'metadata/full_download_v2/records'
    records.mkdir(parents=True, exist_ok=True)
    record = records / (key + '.json')
    with (records / (key + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fetch_locked(root, request, record, parsed, expected)


def fetch_locked(root, request, record, parsed, expected):
    key, url = request['id'], request['url']
    if record.exists():
        old = json.loads(record.read_text())
        if old.get('status') in ['downloaded_verified', 'existing_verified', 'validated_pending_publish']:
            p = safe_path(root, old['file'])
            if p.exists() and p.stat().st_size == old['bytes'] and sha(p) == old['sha256']:
                if old['status'] == 'validated_pending_publish':
                    old.update(status='downloaded_verified', finished_utc=now())
                    old.pop('partial_file', None)
                    atomic_json(record, old)
                return old
            if p.exists() or old['status'] != 'validated_pending_publish':
                raise ValueError('previously verified artifact changed')
    stem = safe_path(root, request['target_stem'])
    stem.parent.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(str(request.get('job_id', url)).encode()).hexdigest()[:16]
    part = stem.with_name(stem.name + '.' + identity + '.part')
    offset = part.stat().st_size if part.exists() else 0
    if offset > expected:
        raise ValueError('partial file exceeds source size')
    if shutil.disk_usage(root).free < expected - offset + 10 * 2**30:
        raise OSError('insufficient free space with 10 GiB reserve')
    state = {k: v for k, v in request.items() if k != 'url'}
    state.update(status='downloading', source_host=parsed.hostname, started_utc=now(),
                 partial_file=str(part.relative_to(root)), received_bytes=offset,
                 source_url_without_query=urllib.parse.urlunparse(parsed._replace(query='',fragment='')))
    atomic_json(record, state)
    if offset < expected:
        headers = {'Accept-Encoding': 'identity'}
        if request.get('etag'):
            headers['If-Match'] = '"' + request['etag'].strip('"') + '"'
        if offset:
            headers['Range'] = 'bytes=%d-' % offset
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as response:
            if offset and not valid_range(response.status, response.headers.get('Content-Range'), offset, expected):
                raise ValueError('server did not honor safe resume range; partial preserved')
            if not offset and response.status != 200:
                raise ValueError('unexpected initial HTTP response')
            remaining = response.headers.get('Content-Length')
            if remaining is not None and int(remaining) != expected - offset:
                raise ValueError('HTTP content length differs from advertised result')
            last = time.monotonic()
            with part.open('ab' if part.exists() else 'xb') as output:
                received = offset
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    received += len(chunk)
                    if received > expected:
                        raise ValueError('response exceeds advertised size')
                    if time.monotonic() - last > 20:
                        state.update(received_bytes=received, checked_utc=now())
                        atomic_json(record, state)
                        print(json.dumps({'id': key, 'progress_bytes': received, 'expected_bytes': expected}), flush=True)
                        last = time.monotonic()
                output.flush()
                os.fsync(output.fileno())
    if part.stat().st_size != expected:
        raise ValueError('incomplete artifact; partial preserved')
    extension = inspect_format(part)
    digest = sha(part)
    target = stem.with_name(stem.name + extension)
    if target.exists():
        raise FileExistsError('refusing to overwrite unregistered existing artifact')
    state.update(status='validated_pending_publish', file=str(target.relative_to(root)), bytes=expected,
                 sha256=digest, format=extension[1:], finished_utc=now(), received_bytes=expected,
                 validation='Expected byte count, NetCDF signatures, ZIP CRC when applicable, SHA256; coordinate/content QA pending')
    atomic_json(record, state)
    part.rename(target)
    state.update(status='downloaded_verified', finished_utc=now())
    state.pop('partial_file', None)
    atomic_json(record, state)
    return state


if __name__ == '__main__':
    try:
        result = fetch(Path(sys.argv[1]).resolve(), json.load(sys.stdin))
        print(json.dumps({'result': result}), flush=True)
    except Exception as error:
        # Never echo a signed URL from a network exception.
        print(json.dumps({'error_type': type(error).__name__,
                          'http_status': getattr(error, 'code', None)}), flush=True)
        raise SystemExit(1)
