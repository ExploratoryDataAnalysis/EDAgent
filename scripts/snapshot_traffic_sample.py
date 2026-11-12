"""Capture a small TIRe station sample for source review, not coverage estimation."""
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = 'https://gis.penndot.pa.gov/gis/rest/services/tds/tire/MapServer/0'
OUT = Path('.repro/tire_station_sample')


def fetch(url, params):
    with urllib.request.urlopen(url + '?' + urllib.parse.urlencode(params), timeout=60) as f:
        result = json.load(f)
    if 'error' in result:
        raise RuntimeError(result['error'])
    return result


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    metadata = fetch(ROOT, {'f': 'json'})
    sample = fetch(ROOT + '/query', {'where': '1=1', 'geometry': '-80.36,40.15,-79.67,40.68',
        'geometryType': 'esriGeometryEnvelope', 'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects',
        'outFields': '*', 'returnGeometry': 'true', 'outSR': 4326, 'resultRecordCount': 10, 'f': 'json'})
    OUT.mkdir(parents=True)
    (OUT / 'metadata.json').write_text(json.dumps(metadata, sort_keys=True), encoding='utf8')
    (OUT / 'sample.json').write_text(json.dumps(sample, sort_keys=True), encoding='utf8')
    print(f"Captured {len(sample.get('features', []))} station features for review; not a site-year exposure join.")


if __name__ == '__main__':
    main()
