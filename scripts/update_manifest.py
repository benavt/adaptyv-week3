from pathlib import Path
import hashlib
root=Path(__file__).resolve().parents[1]
files=sorted(p for p in root.rglob('*') if p.is_file() and not any(x in {'.git','__pycache__','.venv','_private','.pytest_cache'} for x in p.relative_to(root).parts) and p.name!='SHA256SUMS')
(root/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root))+'\n' for p in files))
print('Hashed',len(files),'published files')
