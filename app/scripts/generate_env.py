"""Create local deployment secrets without printing them or overwriting an existing .env."""
from pathlib import Path
import os
import secrets
p=Path(__file__).resolve().parents[1]/'.env'
text=(p.parent/'.env.example').read_text().replace('RUBBER_DB_PASSWORD=\n','RUBBER_DB_PASSWORD='+secrets.token_urlsafe(36)+'\n',1)
try:
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
except FileExistsError:
    raise SystemExit('.env sudah ada; tidak ditimpa.')
with os.fdopen(fd,'w') as f:f.write(text)
print('.env dibuat dengan izin 0600. Password tidak dicetak. Jangan commit atau bagikan file ini.')
