import json, pathlib, collections
p = pathlib.Path('docs/TEST_CASES_NORMALIZED_2026-04-08.json')
data = json.loads(p.read_text(encoding='utf-8'))
rows = [r for r in data['rows'] if r.get('TC ID','').strip()]
status_groups = collections.OrderedDict()
for r in rows:
    s = (r.get('Status') or '').strip()
    key = s if s else '[blank]'
    status_groups.setdefault(key, []).append(r)
print('TOTAL_TCIDS', len(rows))
for k,v in sorted(status_groups.items(), key=lambda kv: len(kv[1]), reverse=True):
    print(f'STATUS::{k}::{len(v)}')
for target in ['Fail','Pending','[blank]','changed','Changed','Changed | Already Covered']:
    vals = status_groups.get(target, [])
    if not vals:
        continue
    print(f'LIST::{target}')
    for r in vals:
        print(f"{r['TC ID']}|{r['Module']}|{r['Test Case Description']}")
