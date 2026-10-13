import json, hashlib, pathlib

m = json.load(open('C:/æ/site/teologia/platform-manifest.json'))
print(f'Artefactos actuales: {len(m["artifacts"])}')

# Add new artifacts
new = [
    {'file': 'heidelberg.html', 'id': 'heidelberg'},
    {'file': 'los-dos-tipos-de-justicia.html', 'id': 'justicia'},
    {'file': 'lauterbuch.html', 'id': 'lauterbuch'}
]

for n in new:
    html = pathlib.Path(f'C:/æ/site/teologia/{n["file"]}')
    if html.exists():
        digest = hashlib.sha256(html.read_bytes()).hexdigest()
        m['artifacts'].append({
            'file': n['file'],
            'sha256': digest,
            'sha256_prefix': digest[:16],
            'bytes': html.stat().st_size
        })
        print(f'  Añadido: {n["file"]}')

print(f'Total artefactos: {len(m["artifacts"])}')

# Remove sha256 at root if exists (it's computed)
if 'sha256' in m:
    del m['sha256']
    
json.dump(m, open('C:/æ/site/teologia/platform-manifest.json', 'w'), indent=2, ensure_ascii=False)
print('Manifest actualizado')