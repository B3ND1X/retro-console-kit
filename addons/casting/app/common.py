"""Private per-console state and bounded unprivileged casting RPC."""
from pathlib import Path
import os,json,socket,secrets,time,re
ROOT=Path(__file__).resolve().parent
HOME=Path.home();BASE=Path(os.environ.get('SNES_CAST_HOME',str(HOME/'.local/share/snes-casting')))
SETTINGS=Path(os.environ.get('SNES_CAST_SETTINGS',str(HOME/'.config/snes-casting/settings.json')))
SOCKET=os.environ.get('SNES_CAST_SOCKET','/run/snes-casting/control.sock')
STATUS=Path('/dev/shm')/('snes-casting-%d.json'%os.getuid())
DEFAULT=dict(schema=1,youtube=False,local=False,airplay=False,name='SNES Console',max_height=720,game_policy='block',music='pause',airplay_password='')
def config_section(name,values):
 """Serialize a fixed libconfig section, escaping every dynamic string value."""
 if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name):raise ValueError('Invalid configuration section')
 entries=[]
 for key,value in values.items():
  if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',key) or type(value) not in (str,int,bool):raise ValueError('Invalid configuration field')
  entries.append(key+' = '+json.dumps(value)+';')
 return name+' = { '+' '.join(entries)+' };\n'
def atomic(p,value):
 p=Path(p);p.parent.mkdir(parents=True,mode=0o700,exist_ok=True);tmp=p.with_name('.'+p.name+'.'+secrets.token_hex(5));fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 try:
  with os.fdopen(fd,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
 finally:
  if tmp.exists():tmp.unlink()
def load(p,default=None):
 try:return json.loads(Path(p).read_text())
 except (OSError,ValueError):return {} if default is None else default

def settings():return dict(DEFAULT,**{k:v for k,v in load(SETTINGS).items() if k in DEFAULT})
def rpc(action,data=None,timeout=5):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
  s.settimeout(timeout);s.connect(SOCKET);s.sendall((json.dumps(dict(action=action,data=data or {}))+'\n').encode());out=b''
  while b'\n' not in out:
   b=s.recv(4096)
   if not b:break
   out+=b
   if len(out)>131072:raise ValueError('Casting response too large')
 result=json.loads(out)
 if not result.get('ok'):raise ValueError(result.get('error','Casting request failed'))
 return result
