"""Exact archived World Bank metadata groups; never infer a missing region."""
def region_samples(rows,metadata):
    if not isinstance(metadata,list) or len(metadata)!=2 or metadata[0].get('total')!=len(metadata[1]):
        raise ValueError('Incomplete country metadata')
    index={};labels={}
    for item in metadata[1]:
        key=item.get('id')
        if not isinstance(key,str) or not key or key in index:raise ValueError('Duplicate or missing source country code')
        index[key]=item
    regions={}
    for country in {r['country_id'] for r in rows}:
        if country not in index:raise ValueError('Unmapped sample country')
        region=index[country].get('region',{});code=region.get('id');label=region.get('value')
        if not code or code=='NA' or not label:raise ValueError('Unknown or aggregate sample region')
        if code in labels and labels[code]!=label:raise ValueError('Inconsistent region label')
        regions[country]=code;labels[code]=label
    for region in sorted(labels):
        yield region,[r for r in rows if regions[r['country_id']]!=region]
