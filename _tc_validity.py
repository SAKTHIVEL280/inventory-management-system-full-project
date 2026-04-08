import json, re, pathlib, collections
rows = json.loads(pathlib.Path('docs/TEST_CASES_NORMALIZED_2026-04-08.json').read_text(encoding='utf-8'))['rows']
pattern = re.compile(r'^[A-Za-z]{2,4}\s*-\s*\d+$')
valid = []
invalid = []
for r in rows:
    tc = (r.get('TC ID') or '').strip()
    if not tc:
        continue
    if pattern.match(tc):
        valid.append(r)
    else:
        invalid.append(r)
print(f'VALID_TC_COUNT={len(valid)}')
print(f'NONSTANDARD_TCID_ROWS={len(invalid)}')
for r in invalid[:20]:
    print(f"{r.get('TC ID')} | SNo={r.get('S.No')} | Module={r.get('Module')}")
status_counter = collections.Counter((r.get('Status') or '').strip() or '[blank]' for r in valid)
print('VALID_STATUS_BREAKDOWN')
for k,v in status_counter.most_common():
    print(f"{k} => {v}")
