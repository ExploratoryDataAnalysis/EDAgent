"""Snapshot the public Allegheny PennDOT segment layer for review, not release."""
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = 'https://gis.penndot.pa.gov/gis/rest/services/opendata/roadwaysegments/MapServer/0'
OUT = Path('.repro/penndot_roadwaysegments')


def fetch(url, params):
    with urllib.request.urlopen(url + '?' + urllib.parse.urlencode(params), timeout=90) as f:
        result = json.load(f)
    if 'error' in result:
        raise RuntimeError(result['error'])
    return result


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    metadata = fetch(ROOT, {'f': 'json'})
    ids_result = fetch(ROOT + '/query', {'where': "CTY_CODE='02'", 'returnIdsOnly': 'true', 'f': 'json'})
    ids = sorted(ids_result['objectIds'])
    features = []
    for start in range(0, len(ids), 50):
        result = fetch(ROOT + '/query', {'objectIds': ','.join(map(str, ids[start:start+50])),
                      'outFields': 'OBJECTID,CTY_CODE,ST_RT_NO,SEG_NO,SEG_LNGTH_FEET,DIR_IND,CUR_AADT,GIS_UPDATE_DATE',
                      'returnGeometry': 'true', 'outSR': 4326, 'f': 'geojson'})
        features.extend(result['features'])
    if len(features) != len(ids) or len({f['properties']['OBJECTID'] for f in features}) != len(ids):
        raise ValueError('PennDOT feature IDs did not reconcile')
    OUT.mkdir(parents=True)
    (OUT / 'metadata.json').write_text(json.dumps(metadata, sort_keys=True), encoding='utf8')
    (OUT / 'segments.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': features}, sort_keys=True), encoding='utf8')
    print(f'Snapshotted {len(features)} features to {OUT}; historical validity and AADT year are unverified.')


if __name__ == '__main__':
    main()
