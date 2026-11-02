"""Resolve immutable original monthly provenance through the alternative batch."""
import json
from pathlib import Path

def resolve_sources(heat,batch,original,sources):
    def entry(manifest,path):
        matches=[v for k,v in manifest.get('inputs',{}).items() if Path(k).resolve()==Path(path).resolve()]
        if len(matches)!=1:raise ValueError('Missing or ambiguous provenance: '+str(path))
        return matches[0]
    bm=json.loads(sources.read(batch,entry(heat,batch)))
    if bm.get('status')!='completed':raise ValueError('Incomplete alternative batch')
    om=json.loads(sources.read(original,entry(bm,original)))
    if om.get('state')!='complete' or not isinstance(om.get('sources'),list):raise ValueError('Invalid original monthly provenance')
    return om['sources']
