"""Build review-only candidates from the 2024 snapshot; never publish assignments.

Run with PYTHONPATH including src and the dependencies in requirements-provisional.txt.
The output directory must be new and below .repro, away from release exports.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from edagent.coordinates.validator import CoordinateValidator
from edagent.coordinates.models import ValidationStatus
from edagent.roadway.normalization import map_road_class

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv'
NETWORK = ROOT / 'data/reference/street_centerlines/AlleghenyCounty_StreetCenterlines202412.zip'
CONFLICTS = ROOT / 'analysis/outputs/spatial/candidate_coordinate_disagreements_review.csv'
SNAPSHOT_HASH = '8364f54192898cc776560069745db5f5903e9f9afd8a939d3c7dc93081a948af'
VERSION = 'provisional-pasda-202412-v1'
FEET_TO_METRES = 1200 / 3937


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_network(path):
    with zipfile.ZipFile(path) as z:
        files = {Path(n).suffix.lower(): n for n in z.namelist()}
        crs = CRS.from_wkt(z.read(files['.prj']).decode())
        if crs.to_epsg() != 2272:
            raise ValueError('Expected EPSG:2272 US survey feet')
        reader = shapefile.Reader(shp=io.BytesIO(z.read(files['.shp'])),
                                  shx=io.BytesIO(z.read(files['.shx'])),
                                  dbf=io.BytesIO(z.read(files['.dbf'])))
        sites, geometry, endpoints = [], [], defaultdict(list)
        for item in reader.iterShapeRecords():
            record = item.record.as_dict()
            key = record.get('FEATURE_KE')
            if key is None:
                raise ValueError('Missing FEATURE_KE')
            site_id = f'PASDA202412:SEG:{key}'
            line = shape(item.shape.__geo_interface__)
            if line.geom_type not in ('LineString', 'MultiLineString') or line.is_empty:
                raise ValueError(f'Invalid line geometry for {site_id}')
            sites.append({'site_id': site_id, 'feature_key': str(key),
                          'street': str(record.get('FULL_NAME') or ''),
                          'fcc': str(record.get('FCC') or ''), 'oneway': str(record.get('ONEWAY') or ''),
                          'length_m': round(line.length * FEET_TO_METRES, 3)})
            geometry.append(line)
            parts = list(line.geoms) if line.geom_type == 'MultiLineString' else [line]
            for part in parts:
                for x, y, *_ in (part.coords[0], part.coords[-1]):
                    endpoints[(round(x, 1), round(y, 1))].append(len(sites) - 1)
        if len({s['site_id'] for s in sites}) != len(sites):
            raise ValueError('Duplicate feature keys')
        return sites, geometry, endpoints


def candidate_for_point(point, tree, sites):
    """Return all actual line candidates within 50 m; distance is not attribution."""
    indices = tree.query(point, predicate='dwithin', distance=50 / FEET_TO_METRES)
    return sorted(((float(point.distance(tree.geometries[i])) * FEET_TO_METRES, sites[i]['site_id'])
                   for i in indices), key=lambda x: (x[0], x[1]))


def build(out):
    root = (ROOT / '.repro').resolve()
    out = out.resolve()
    if not out.is_relative_to(root) or out == root or out.exists():
        raise ValueError('Output must be a new directory under .repro')
    manifest = json.loads((ROOT / 'analysis/outputs/run_manifest.json').read_text(encoding='utf8'))
    if digest(RAW) != manifest['data']['sha256'] or digest(NETWORK) != SNAPSHOT_HASH:
        raise ValueError('Frozen input or pinned network checksum mismatch')
    with CONFLICTS.open(encoding='utf8', newline='') as f:
        conflict_rows = list(csv.DictReader(f))
    conflicts = {r['CRASH_CRN'] for r in conflict_rows}
    if len(conflicts) != 2146 or len(conflict_rows) != 2146:
        raise ValueError('Unexpected v6 conflict set')
    out.mkdir(parents=True)
    sites, lines, endpoints = load_network(NETWORK)
    tree = STRtree(lines)
    to_wgs = Transformer.from_crs(2272, 4326, always_xy=True).transform
    to_plane = Transformer.from_crs(4326, 2272, always_xy=True)
    with (out / 'site_inventory.csv').open('w', encoding='utf8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['site_id','feature_key','street','fcc','oneway','length_m'])
        w.writeheader(); w.writerows(sites)
    with (out / 'network.geojson').open('w', encoding='utf8') as f:
        f.write('{"type":"FeatureCollection","features":[')
        for i, (s, line) in enumerate(zip(sites, lines)):
            if i: f.write(',')
            json.dump({'type':'Feature','properties':s,'geometry':mapping(transform(to_wgs, line))}, f, separators=(',', ':'))
        f.write(']}')
    with (out / 'candidate_junctions.csv').open('w', encoding='utf8', newline='') as f:
        w = csv.writer(f); w.writerow(['junction_id','x_ft','y_ft','segment_ids','review_status'])
        for (x, y), indices in sorted(endpoints.items()):
            ids = sorted({sites[i]['site_id'] for i in indices})
            names = {sites[i]['street'].strip().upper() for i in indices if sites[i]['street'].strip()}
            if len(ids) < 2 or len(names) < 2: continue
            jid = hashlib.sha256((f'{x:.1f},{y:.1f}|' + '|'.join(ids)).encode()).hexdigest()[:20]
            w.writerow([f'PASDA202412:JUNC:{jid}', x, y, '|'.join(ids), 'REVIEW_GRADE_AND_TOPOLOGY'])
    validator = CoordinateValidator()
    counts = Counter(); by_year = Counter(); by_road = Counter(); seen = set(); seen_conflicts = set()
    fields = ['crash_id','crash_year','road_class','match_status','primary_site_id','candidate_site_id','candidate_distance_m','candidate_count','candidates','route','segment','offset','reference_version','decision_reason']
    with RAW.open(encoding='utf8', newline='') as source, (out / 'crosswalk.csv').open('w', encoding='utf8', newline='') as dest:
        w = csv.DictWriter(dest, fieldnames=fields); w.writeheader()
        for row in csv.DictReader(source):
            crn = row['CRASH_CRN']; year = row['CRASH_YEAR']
            if not crn or crn in seen: raise ValueError(f'Invalid or duplicate CRN {crn}')
            seen.add(crn)
            road = map_road_class(road_owner=row.get('ROAD_OWNER'), route=row.get('ROUTE') or '').value
            reason = 'HISTORICAL_VALIDITY_AND_TOPOLOGY_UNREVIEWED'; status = 'UNMATCHED'; candidates = []
            if crn in conflicts:
                status = 'AMBIGUOUS'; reason = 'V6_COORDINATE_CONFLICT_WITHHELD'; seen_conflicts.add(crn)
            else:
                coord = validator.process_crash_record(crash_crn=int(crn), crash_year=int(year), raw_latitude=row.get('LATITUDE'), raw_longitude=row.get('LONGITUDE'), raw_dec_lat=row.get('DEC_LAT'), raw_dec_long=row.get('DEC_LONG'), is_state_route=bool(row.get('ROUTE')))
                if coord.validation_status == ValidationStatus.CONFLICT:
                    status = 'AMBIGUOUS'; reason = 'COORDINATE_CONFLICT_WITHHELD'
                elif coord.validation_status in (ValidationStatus.VALID, ValidationStatus.WARNING) and coord.decoded_latitude is not None and coord.decoded_longitude is not None:
                    x, y = to_plane.transform(coord.decoded_longitude, coord.decoded_latitude)
                    candidates = candidate_for_point(Point(x, y), tree, sites)
                    if not candidates: reason = 'NO_LINE_WITHIN_50M_OR_HISTORY_UNVERIFIED'
                else:
                    reason = 'MISSING_OR_INVALID_COORDINATES'
            counts[status] += 1; by_year[(year,status)] += 1; by_road[(road,status)] += 1
            w.writerow({'crash_id':crn,'crash_year':year,'road_class':road,'match_status':status,'primary_site_id':'',
                        'candidate_site_id':candidates[0][1] if candidates else '', 'candidate_distance_m':round(candidates[0][0],3) if candidates else '',
                        'candidate_count':len(candidates), 'candidates':';'.join(f'{s}@{d:.3f}m' for d,s in candidates),
                        'route':row.get('ROUTE',''),'segment':row.get('SEGMENT',''),'offset':row.get('OFFSET',''),
                        'reference_version':VERSION,'decision_reason':reason})
    if seen_conflicts != conflicts or len(seen) != manifest['data']['rows']:
        raise ValueError('Crash population or v6 conflict set did not reconcile')
    for name, data, column in [('qa_by_year.csv',by_year,'year'),('qa_by_road_class.csv',by_road,'road_class')]:
        with (out / name).open('w', encoding='utf8', newline='') as f:
            w=csv.writer(f); w.writerow([column,'status','count']); w.writerows((a,b,n) for (a,b),n in sorted(data.items()))
    hashes = {p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()}
    (out / 'manifest.json').write_text(json.dumps({'status':'PROVISIONAL_NOT_APPROVED','reference_version':VERSION,'source_sha256':digest(RAW),'network_sha256':digest(NETWORK),'conflicts_sha256':digest(CONFLICTS),'counts':dict(counts),'site_count':len(sites),'output_sha256':hashes}, indent=2), encoding='utf8')
    print(json.dumps({'output':str(out), 'counts':dict(counts), 'sites':len(sites)}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output', required=True, type=Path)
    build(parser.parse_args().output)
