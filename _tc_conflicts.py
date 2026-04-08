import json, pathlib
from collections import defaultdict
p = pathlib.Path('docs/TEST_CASES_NORMALIZED_2026-04-08.json')
rows = [r for r in json.loads(p.read_text(encoding='utf-8'))['rows'] if r.get('TC ID','').strip()]
by_id = defaultdict(list)
for r in rows:
    by_id[r['TC ID'].strip()].append((r.get('Status','').strip() or '[blank]', r.get('Test Case Description','').strip()))
conflicts = {k:v for k,v in by_id.items() if len(set(s for s,_ in v))>1}
print(f'DUPLICATE_TC_IDS={sum(1 for k,v in by_id.items() if len(v)>1)}')
print(f'STATUS_CONFLICT_TC_IDS={len(conflicts)}')
for tcid, entries in sorted(conflicts.items()):
    st = ', '.join(sorted(set(s for s,_ in entries)))
    print(f"{tcid} => {st}")
