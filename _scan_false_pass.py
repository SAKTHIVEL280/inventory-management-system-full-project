import json, re, pathlib
p = pathlib.Path(r"docs/TEST_CASES_NORMALIZED_2026-04-08.json")
data = json.loads(p.read_text(encoding='utf-8'))
rows = [r for r in data['rows'] if r.get('TC ID','').strip()]
pass_rows = [r for r in rows if r.get('Status','').strip().lower() == 'pass']
keywords = [
    r'\bfail', r'\berror', r'\bincorrect', r'\bissue', r'\bnot fixed',
    r'\bneeds?\b', r'\bhave to\b', r'\ballowing\b', r'\bmissing\b', r'\bbug\b'
]
pat = re.compile('|'.join(keywords), re.IGNORECASE)
flagged = []
for r in pass_rows:
    txt = f"{r.get('Test Case Description','')} || {r.get('Remarks / Notes','')}"
    if pat.search(txt):
        flagged.append(r)
print(f"PASS_ROWS={len(pass_rows)}")
print(f"FLAGGED_PASS_ROWS={len(flagged)}")
for r in flagged:
    print(f"{r.get('TC ID')} | {r.get('Module')} | {r.get('Test Case Description')} | remark={r.get('Remarks / Notes','')[:140].replace(chr(10),' ')}")
