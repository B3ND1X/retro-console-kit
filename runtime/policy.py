"""Strict release schema and local, administrator-owned destination policy."""
import re,os,stat,hashlib,tarfile
from pathlib import Path,PurePosixPath
from auth import loads
from transactions import digest,checked_path
PROTOCOL=1
TARGET='retropie48-raspbian10-armhf-zero2w'
MAX_PACKAGE=96*1024*1024
MAX_UNPACKED=192*1024*1024
class UpdateError(Exception):pass

def version(value):
 if not isinstance(value,str) or len(value)>32 or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)',value):raise UpdateError('Use a stable numeric major.minor.patch version')
 return tuple(map(int,value.split('.')))

def repository(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}',value) or value.split('/')[1] in ('.','..'):raise UpdateError('Enter GitHub owner/repository, not a URL')
 return value

def canonical(data):
 import json
 return (json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode()

def forbidden(path):
 parts=[p.lower() for p in PurePosixPath(path).parts]
 if any(p in {'roms','bios','saves','states','secrets','.ssh','.git','node_modules','__pycache__','cache','logs','userdata','sessions'} for p in parts):return True
 return bool(re.search(r'(?i)(\.srm|\.sav|\.state\d*|\.nes|\.sfc|\.smc|\.gba|\.iso|\.chd|\.cue|\.bin|\.log|\.pyc|\.pem|\.key)$',path))

def catalogue(path):
 data=loads(Path(path).read_bytes())
 if set(data)!={'schema','files'} or data['schema']!=1:raise UpdateError('Unsupported local allowlist')
 destinations=set()
 for name,e in data['files'].items():
  if not re.fullmatch(r'[A-Za-z0-9_./-]+',name) or forbidden(name) or '..' in name.split('/') or any(v in ('','.') for v in name.split('/')):raise UpdateError('Invalid allowlisted asset')
  if set(e)!={'destination','mode','license','license_file','redistributable','component'}:raise UpdateError('Invalid allowlist fields')
  dest=e['destination']
  if not isinstance(dest,str) or not dest.startswith('/') or dest in destinations or '..' in dest.split('/') or '\\' in dest:raise UpdateError('Invalid managed destination')
  destinations.add(dest)
  # User configuration and identity are never destinations, even if accidentally added to the catalogue.
  if dest.startswith(('/home/','/root/','/boot/','/var/','/etc/ssh/','/etc/NetworkManager/','/etc/wpa_supplicant/','/opt/retropie/configs/','/usr/local/lib/snes-updater/','/etc/snes-updater/')):raise UpdateError('User state or updater trust boundary is forbidden')
  if not (dest.startswith('/usr/local/lib/snes-console/') or dest.startswith('/usr/local/share/snes-console/') or dest=='/opt/retropie/supplementary/emulationstation/emulationstation' or dest=='/opt/retropie/supplementary/runcommand/runcommand.sh' or dest=='/usr/local/sbin/snes-console-settings' or dest.startswith('/etc/emulationstation/themes/')):raise UpdateError('Destination is outside approved application areas')
  if e['mode'] not in (0o644,0o755) or not isinstance(e['redistributable'],bool):raise UpdateError('Unsafe application file mode')
 return data['files']

def validate_manifest(m,cat,repo,target,installed,floor):
 expected={'schema','protocol','version','repository','target','notes','archive','files','migrations'}
 if not isinstance(m,dict) or set(m)!=expected or m['schema']!=1 or m['protocol']!=PROTOCOL:raise UpdateError('Unsupported signed manifest schema')
 if repository(m['repository']).lower()!=repository(repo).lower():raise UpdateError('Signed release is for a different repository')
 if m['target']!=target:raise UpdateError('Release is incompatible with this console target')
 v=version(m['version'])
 if v<=max(version(installed),version(floor)):raise UpdateError('Already installed, previously rolled back, or downgrade rejected')
 if not isinstance(m['notes'],str) or len(m['notes'])>16000 or any(ord(c)<32 and c not in '\n\r\t' for c in m['notes']):raise UpdateError('Invalid release notes')
 archive=m['archive']
 if not isinstance(archive,dict) or set(archive)!={'name','size','sha256'} or archive['name']!='software-'+target+'.tar.gz':raise UpdateError('Invalid archive declaration')
 if type(archive['size']) is not int or not 0<archive['size']<=MAX_PACKAGE or not re.fullmatch('[a-f0-9]{64}',str(archive['sha256'])):raise UpdateError('Invalid signed archive size/hash')
 if not isinstance(m['files'],list) or not 1<=len(m['files'])<=256:raise UpdateError('Invalid file count')
 if any(not isinstance(r,dict) or not isinstance(r.get('path'),str) for r in m['files']):raise UpdateError('Malformed file declaration')
 seen=set();total=0
 for row in m['files']:
  if not isinstance(row,dict) or set(row)!={'path','size','sha256'} or row['path'] not in cat or row['path'] in seen:raise UpdateError('Unexpected, duplicate or unapproved release file')
  seen.add(row['path']);e=cat[row['path']]
  if not e['redistributable'] or not e['license'] or not e['license_file'] or e['license_file'] not in [r.get('path') for r in m['files']]:raise UpdateError('File lacks confirmed redistribution permission/licence')
  if type(row['size']) is not int or not 0<=row['size']<=64*1024*1024 or not re.fullmatch('[a-f0-9]{64}',str(row['sha256'])):raise UpdateError('Invalid file size/hash')
  total+=row['size']
 if total>MAX_UNPACKED:raise UpdateError('Expanded update exceeds resource limit')
 if 'app/VERSION' not in seen:raise UpdateError('Release must carry its authoritative version file')
 if not isinstance(m['migrations'],list) or len(set(m['migrations']))!=len(m['migrations']) or any(x not in ['updater-preferences-v1'] for x in m['migrations']):raise UpdateError('Unknown migration; release-provided commands are forbidden')
 return total

def unpack(package,m,stage):
 if Path(package).stat().st_size!=m['archive']['size'] or digest(package)!=m['archive']['sha256']:raise UpdateError('Archive checksum/size mismatch')
 expected={r['path']:r for r in m['files']};seen=set();stage=Path(stage);stage.mkdir(mode=0o700,exist_ok=True)
 with tarfile.open(str(package),'r|gz') as archive:
  for member in archive:
   name=member.name
   if name not in expected or name in seen or not member.isreg() or member.pax_headers or member.mode&0o7000 or member.size!=expected[name]['size']:raise UpdateError('Unsafe, unexpected or duplicate archive entry')
   seen.add(name);dest=checked_path(stage,name);dest.parent.mkdir(parents=True,exist_ok=True)
   with archive.extractfile(member) as src,dest.open('xb') as out:
    h=hashlib.sha256();remaining=member.size
    while remaining:
     block=src.read(min(1024*1024,remaining))
     if not block:raise UpdateError('Truncated archive file')
     out.write(block);h.update(block);remaining-=len(block)
    out.flush();os.fsync(out.fileno())
   if h.hexdigest()!=expected[name]['sha256']:raise UpdateError('Payload checksum mismatch')
 if seen!=set(expected):raise UpdateError('Signed payload has missing files')
 if (stage/'app/VERSION').read_text().strip()!=m['version']:raise UpdateError('Version file does not match signed release')
 return stage
