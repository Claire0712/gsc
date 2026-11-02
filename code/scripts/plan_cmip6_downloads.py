"""Discover exact official S3 objects; do not manufacture data object URLs."""
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import re
import requests
import xml.etree.ElementTree as ET

BUCKET = 'https://nex-gddp-cmip6.s3.us-west-2.amazonaws.com/'
MODELS = ['ACCESS-CM2', 'ACCESS-ESM1-5', 'BCC-CSM2-MR', 'CanESM5',
          'CMCC-ESM2', 'CNRM-CM6-1', 'EC-Earth3', 'GFDL-ESM4',
          'IPSL-CM6A-LR', 'MIROC6']
NS = {'s': 'http://s3.amazonaws.com/doc/2006-03-01/'}
OUT = Path(__file__).resolve().parents[1] / 'downloads'


def listing(session, prefix, delimiter=None):
    params = {'list-type': '2', 'prefix': prefix, 'max-keys': '1000'}
    if delimiter:
        params['delimiter'] = delimiter
    entries, prefixes = [], []
    while True:
        r = session.get(BUCKET, params=params, timeout=60)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        entries.extend({'key': x.findtext('s:Key', namespaces=NS),
                        'bytes': int(x.findtext('s:Size', namespaces=NS)),
                        'etag': x.findtext('s:ETag', namespaces=NS).strip('"'),
                        'last_modified': x.findtext('s:LastModified', namespaces=NS)}
                       for x in root.findall('s:Contents', NS))
        prefixes.extend(x.text for x in root.findall('s:CommonPrefixes/s:Prefix', NS))
        if root.findtext('s:IsTruncated', namespaces=NS) != 'true':
            return entries, prefixes
        params['continuation-token'] = root.findtext('s:NextContinuationToken', namespaces=NS)


def discover(model):
    session = requests.Session()
    session.trust_env = False
    experiments = ['historical', 'ssp245', 'ssp585']
    members = {}
    for experiment in experiments:
        _, prefixes = listing(session, 'NEX-GDDP-CMIP6/%s/%s/' % (model, experiment), '/')
        members[experiment] = {p.rstrip('/').split('/')[-1] for p in prefixes}
    common = set.intersection(*members.values())
    if not common:
        raise ValueError('No common ensemble member for ' + model)
    member = 'r1i1p1f1' if 'r1i1p1f1' in common else sorted(common)[0]
    tasks = []
    for experiment in experiments:
        years = list(range(1991, 2015)) if experiment == 'historical' else (
            list(range(2015, 2021)) + list(range(2041, 2061)) + list(range(2081, 2101)))
        for variable in ['tasmin', 'tasmax']:
            prefix = 'NEX-GDDP-CMIP6/%s/%s/%s/%s/' % (model, experiment, member, variable)
            entries, _ = listing(session, prefix)
            for year in years:
                matches = [e for e in entries if re.search(r'_%d_v2\.0\.nc$' % year, e['key'])]
                if len(matches) != 1:
                    raise ValueError('Expected one v2.0 object: %s %d; got %d' % (prefix, year, len(matches)))
                e = matches[0]
                key = 'cmip6_%s_%s_%s_%s_%d_v2.0' % (model, experiment, member, variable, year)
                tasks.append(dict(e, id=key, url=BUCKET + e['key'],
                                  target_stem='cmip6/full_v2/' + e['key'][len('NEX-GDDP-CMIP6/'): -3],
                                  model=model, experiment=experiment, member=member,
                                  variable=variable, year=year, version='2.0',
                                  role='baseline' if year <= 2020 else 'future'))
    print(model, member, len(tasks), flush=True)
    return tasks


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        groups = list(pool.map(discover, MODELS))
    tasks = [t for group in groups for t in group]
    assert len(tasks) == 2320 and len({t['id'] for t in tasks}) == len(tasks)
    manifest = {'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'source': BUCKET, 'models': MODELS, 'version': '2.0', 'tasks': tasks,
                'total_bytes': sum(t['bytes'] for t in tasks),
                'scope': '10 models, one common member per model, tasmin/tasmax, both SSPs, 2041-2060 and 2081-2100; 1991-2020 model baselines included for comparable anomalies',
                'selection': 'Fixed available-model subset selected before outcomes; not a statistically independent or exhaustive ensemble'}
    (OUT / 'cmip6_plan.json').write_text(json.dumps(manifest, indent=2))
    print('TOTAL', len(tasks), manifest['total_bytes'], flush=True)
