"""Summarize an existing review-only crosswalk without changing its manifest."""
import csv
import json
from collections import Counter
from pathlib import Path
import sys

out = Path(sys.argv[1]).resolve()
root = (Path(__file__).resolve().parent.parent / '.repro').resolve()
if not out.is_relative_to(root):
    raise ValueError('Expected a staging directory under .repro')
counts = Counter(); distance = Counter(); samples = {}; strata = Counter()
with (out / 'crosswalk.csv').open(encoding='utf8', newline='') as f:
    for row in csv.DictReader(f):
        counts[row['decision_reason']] += 1
        strata[(row['crash_year'], row['road_class'], row['match_status'], row['decision_reason'])] += 1
        if row['candidate_distance_m']:
            d = float(row['candidate_distance_m'])
            distance['0–10m' if d <= 10 else '10–25m' if d <= 25 else '25–50m'] += 1
        samples.setdefault(row['decision_reason'], row)
report = {'status':'PROVISIONAL_NOT_APPROVED', 'decision_reason_counts':dict(counts),
          'nearest_candidate_distance_bins':dict(distance), 'sample_records':list(samples.values()),
          'note':'Distances are to snapshot lines, not validated historical assignments.'}
(out / 'review_summary.json').write_text(json.dumps(report, indent=2), encoding='utf8')
with (out / 'qa_by_year_road_method.csv').open('w', encoding='utf8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['year', 'road_class', 'status', 'decision_reason', 'count'])
    writer.writerows((*key, value) for key, value in sorted(strata.items()))
print(json.dumps(report['decision_reason_counts']))
