#!/usr/bin/python3
"""Unprivileged, one-launch RetroArch Netplay adapter. No persistent RA edits."""
import argparse, contextlib, ctypes, struct, fcntl, hashlib, json, os, re, shlex, socket, sys, tempfile, time, urllib.request, zipfile, zlib
from pathlib import Path

BASE = Path(os.environ.get('SNES_NETPLAY_HOME', str(Path.home()/'.config/snes-netplay')))
CONFIG = Path(os.environ.get('CONSOLE_CONFIG_ROOT', '/opt/retropie/configs'))
SUPPORTED = {'lr-fceumm','lr-nestopia','lr-snes9x2010','lr-snes9x2005',
 'lr-snes9x2005-plus','lr-snes9x','lr-genesis-plus-gx','lr-picodrive',
 'lr-fbneo','lr-fbalpha2012','lr-gambatte','lr-stella2014','lr-beetle-pce-fast'}
DEFAULTS = dict(nickname='SNES Console', port=55435, relay='nyc', address='')

def atomic(path, data):
 path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
 fd,tmp=tempfile.mkstemp(dir=str(path.parent), prefix='.netplay-')
 try:
  with os.fdopen(fd,'w') as f: json.dump(data,f,indent=2);f.flush();os.fsync(f.fileno())
  os.chmod(tmp,0o600);os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

@contextlib.contextmanager
def locked():
 BASE.mkdir(parents=True,exist_ok=True,mode=0o700)
 with (BASE/'.lock').open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX);yield

def prefs():
 p=BASE/'settings.json';return dict(DEFAULTS,**(json.loads(p.read_text()) if p.exists() else {}))

def clean(value, limit=48):
 if not value.strip() or len(value)>limit or any(ord(c)<32 or c in '\\"' for c in value):raise ValueError('Use plain text without quotes or backslashes.')
 return value.strip()

def address(value):
 # IPv4/hostname, optional :port; raw IPv6 also accepted (default port).
 value=value.strip();port=None
 if value.count(':')==1:
  value,p=value.rsplit(':',1);port=int(p)
 if not value or value.startswith('-') or len(value)>253 or not re.fullmatch(r'[A-Za-z0-9.:%_-]+',value):raise ValueError('Enter an IP address or hostname, optionally followed by :port.')
 if port is not None and not 1<=port<=65535:raise ValueError('Port must be 1 to 65535.')
 return value,port

def launcher(system,rom):
 import console_experience as ce
 _,_,default,selected,_=ce.options(system,rom)
 return selected or default

def selection(system, rom):
 import console_experience as ce
 _,_,default,selected,available=ce.options(system,rom)
 emulator=selected or default
 # RetroArch 1.10 allocates 124 serialized states for a host. The installed
 # SNES9x 2010 exceeds this board's RAM budget; choose only a session core.
 if emulator=='lr-snes9x2010':
  if 'lr-snes9x2005' not in available:raise ValueError('SNES Netplay needs the lighter installed SNES9x 2005 core on this Pi.')
  emulator='lr-snes9x2005'
 if emulator not in available:raise ValueError('Selected emulator is unavailable.')
 if emulator not in SUPPORTED:raise ValueError('This emulator is not enabled for Netplay. Choose a supported Libretro core in Emulator. Standalone and MAME cores are excluded.')
 command=ce.read_config(CONFIG/system/'emulators.cfg')[emulator]
 args=shlex.split(command);core=Path(args[args.index('-L')+1])
 if '--subsystem' in args:raise ValueError('Netplay for this core subsystem is not supported by this console menu.')
 return emulator,core

def identity(system, rom):
 if not re.fullmatch(r'[A-Za-z0-9_-]+',system):raise ValueError('Invalid system')
 p=Path(rom).resolve()
 if not p.is_file() or any(c in str(p) for c in '\0\r\n'):raise ValueError('Game is unavailable')
 return system,str(p)

def relay_endpoint(region):
 with urllib.request.urlopen('http://lobby.libretro.com/tunnel?name='+region,timeout=7) as response:data=response.read(4097)
 if len(data)>4096:raise ValueError('Invalid relay response')
 fields=dict(line.split('=',1) for line in data.decode().splitlines() if '=' in line)
 host,_=address(fields.get('tunnel_addr',''));port=int(fields.get('tunnel_port','0'))
 if fields.get('status')!='OK' or not 1<=port<=65535:raise ValueError('Relay unavailable; try another region or direct hosting.')
 return host,port

def display(value,limit=96):
 return ''.join(c if 32<=ord(c)!=127 else ' ' for c in str(value))[:limit]

def requirement(core):
 name,version=core_info(core)
 return display(name)+' '+display(version)

def probe(host,port):
 """Read host INFO only; never send game/state/input data or join a player slot."""
 deadline=time.monotonic()+5
 def receive(sock,size):
  data=b''
  while len(data)<size:
   remaining=deadline-time.monotonic()
   if remaining<=0:raise ValueError('Host compatibility check timed out.')
   sock.settimeout(remaining);part=sock.recv(size-len(data))
   if not part:raise ValueError('Host closed the compatibility check. It may require a matching platform or password.')
   data+=part
  return data
 def connect():
  remaining=deadline-time.monotonic()
  if remaining<=0:raise ValueError('Host compatibility check timed out.')
  return socket.create_connection((host,port),timeout=remaining)
 # POKE asks RetroArch for its header without joining the game.
 with connect() as sock:
  sock.sendall(struct.pack('!I',0x504f4b45));header=list(struct.unpack('!6I',receive(sock,24)))
 if header[0]!=0x52414e50:raise ValueError('The address is not an available RetroArch Netplay host.')
 # Probe only the documented nickname/INFO handshake, then close before SYNC.
 with connect() as sock:
  platform=((int(sys.byteorder=='big'))<<30)|(ctypes.sizeof(ctypes.c_size_t)<<15)|ctypes.sizeof(ctypes.c_long)
  sock.sendall(struct.pack('!6I',0x52414e50,platform,1,header[4],header[4],header[5]))
  answer=struct.unpack('!6I',receive(sock,24))
  if answer[0]!=0x52414e50:raise ValueError('Host is full or uses an unsupported Netplay protocol.')
  if answer[3]:raise ValueError('This host requires a password; its core requirements cannot be checked by this menu.')
  nick=b'Compatibility Check'.ljust(32,b'\0');sock.sendall(struct.pack('!II',0x20,32)+nick)
  for _ in range(4):
   command,size=struct.unpack('!II',receive(sock,8))
   if size>1024:raise ValueError('Unsupported host compatibility response.')
   data=receive(sock,size)
   if command==0x22:
    if len(data)!=68:raise ValueError('Host has no game loaded or uses an unsupported INFO format.')
    crc=struct.unpack('!I',data[:4])[0]
    text=lambda b:display(b.split(b'\0',1)[0].decode('utf-8','replace'))
    return dict(name=text(data[4:36]),version=text(data[36:68]),crc='%08X'%crc)
   if command!=0x20:raise ValueError('Host could not provide its core requirements.')
 raise ValueError('Host did not provide core information.')

def check_host(core,rom,host,port):
 own_name,own_version=core_info(core)
 try:peer=probe(host,port)
 except (OSError,ValueError) as e:
  raise ValueError('Could not verify this host.\n'+str(e)+'\nThis console uses: '+requirement(core)+'\nAsk the host to confirm the exact core/version and start hosting, then retry.')
 if (peer['name'],peer['version'])!=(own_name,own_version):
  raise ValueError('CORE MISMATCH - game not launched.\nHost requires: '+peer['name']+' '+peer['version']+'\nThis console uses: '+display(own_name)+' '+display(own_version)+'\nBoth players need the host core and exact version/build. Change Emulator if the required core is installed; otherwise install matching compatible binaries. Nothing was changed automatically.')
 crc=content_crc(rom)
 if crc and peer['crc']!='00000000' and crc!=peer['crc']:
  raise ValueError('GAME MISMATCH - game not launched.\nThe core matches: '+requirement(core)+'\nHost game CRC: '+peer['crc']+'\nYour game CRC: '+crc+'\nUse the identical game revision/region on both devices.')
 return peer

def arm(system,rom,mode,target='',room_verified=False):
 system,rom=identity(system,rom);emulator,core=selection(system,rom)
 if mode not in ('host-relay','host-lan','join'):raise ValueError('Invalid connection mode')
 p=prefs();host='';port=p['port']
 if mode=='join':
  host,custom=address(target or p['address']);port=custom or port
  if not room_verified:check_host(core,rom,host,port)
 intent=dict(system=system,rom=rom,emulator=emulator,launcher=launcher(system,rom),mode=mode,host=host,port=port,nickname=p['nickname'],relay=p['relay'],expires=time.time()+300)
 if mode=='host-relay':intent['relayhost'],intent['relayport']=relay_endpoint(p['relay'])
 with locked():atomic(BASE/'pending.json',intent)
 return intent

def core_info(core):
 class Info(ctypes.Structure):
  _fields_=[('name',ctypes.c_char_p),('version',ctypes.c_char_p),('extensions',ctypes.c_char_p),('fullpath',ctypes.c_bool),('blockextract',ctypes.c_bool)]
 lib=ctypes.CDLL(str(core));f=lib.retro_get_system_info;f.argtypes=[ctypes.POINTER(Info)];f.restype=None;i=Info();f(ctypes.byref(i))
 return i.name.decode(),i.version.decode()

def content_crc(rom):
 p=Path(rom)
 if p.suffix.lower()=='.zip':
  with zipfile.ZipFile(p) as z:
   entries=[i for i in z.infolist() if not i.is_dir()]
   if len(entries)!=1:return None
   return '%08X'%entries[0].CRC
 if p.stat().st_size>64*1024*1024:return None
 crc=0
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):crc=zlib.crc32(block,crc)
 return '%08X'%(crc&0xffffffff)

def rooms(system,rom):
 _,core=selection(system,rom);name,version=core_info(core);crc=content_crc(rom)
 if crc is None:raise ValueError('Room matching needs a single game file or a ZIP containing one game. Use Join by Address for arcade sets.')
 # This is the official endpoint used by the installed RetroArch. It offers HTTP, not HTTPS.
 request=urllib.request.Request('http://lobby.libretro.com/list',headers={'User-Agent':'SNES-Console-Netplay/1.0'})
 with urllib.request.urlopen(request,timeout=7) as response:
  data=response.read(2*1024*1024+1)
 if len(data)>2*1024*1024:raise ValueError('Lobby response too large')
 matching=[];incompatible=[]
 for row in json.loads(data):
  r=row.get('fields',{})
  if str(r.get('game_crc','')).upper()!=crc:continue
  if r.get('core_name')!=name or r.get('core_version')!=version:
   if not r.get('has_password') and len(incompatible)<30:incompatible.append((display(r.get('username','Player')),display(r.get('core_name','Unknown core')),display(r.get('core_version','Unknown version'))))
   continue
  if r.get('has_password') or not r.get('is_retroarch',True):continue
  relay=bool(r.get('mitm_ip'))
  if not relay and not r.get('connectable'):continue
  host,custom=address(str(r.get('mitm_ip') if relay else r.get('ip')))
  port=int(r.get('mitm_port') if relay else r.get('port'))
  if not 1<=port<=65535:continue
  session=str(r.get('mitm_session','')) if relay else ''
  if session and not re.fullmatch(r'[A-Za-z0-9+/=]{1,128}',session):continue
  matching.append(dict(id=str(r['id']),host=host,port=port,session=session,label=clean(str(r.get('username','Player')),100),expires=time.time()+120))
 with locked():atomic(BASE/'rooms.json',dict(system=system,rom=str(Path(rom).resolve()),rooms=matching))
 print('NOTE\tThis console requires: '+display(name)+' '+display(version))
 for label,peer_name,peer_version in incompatible:print('MISMATCH\t'+label+'\t'+peer_name+'\t'+peer_version+'\t'+display(name)+'\t'+display(version))
 for r in matching[:50]:print('ROOM\t'+r['id']+'\t'+r['label'])
 print('NOTE\t'+(str(len(matching))+' matching rooms. Same core version and game CRC.' if matching else 'No matching open rooms. A friend must host the same game and core version. Refresh to check again.'))

def arm_room(system,rom,roomid):
 cache=json.loads((BASE/'rooms.json').read_text());assert (system,str(Path(rom).resolve()))==(cache['system'],cache['rom'])
 room=next((r for r in cache['rooms'] if r['id']==roomid and r['expires']>=time.time()),None)
 if room is None:raise ValueError('Room expired. Refresh the room list.')
 intent=arm(system,rom,'join',room['host'],room_verified=True)
 intent.update(port=room['port'],session=room['session'])
 with locked():atomic(BASE/'pending.json',intent)

def consume(system,emulator,rom):
 with locked():
  path=BASE/'pending.json'
  if not path.exists():return ''
  intent=json.loads(path.read_text());path.unlink()
  # Any other launch discards the intent, so it cannot unexpectedly affect a later game.
  if intent['expires']<time.time() or (system,str(Path(rom).resolve()),emulator)!=(intent['system'],intent['rom'],intent.get('launcher',intent['emulator'])):return ''
  selected,core=selection(system,rom)
  if selected!=intent['emulator']:raise ValueError('Netplay core changed; open Netplay again.')
  temp=Path(os.environ.get('CONSOLE_LAUNCH_CONFIG','/dev/shm/retroarch.cfg'))
  if not temp.is_file():raise ValueError('Runcommand launch configuration is unavailable')
  settings=dict(netplay_nickname=intent['nickname'],netplay_ip_port=str(intent['port']),
   netplay_use_mitm_server='true' if intent['mode']=='host-relay' else 'false',
   netplay_mitm_server=intent['relay'],netplay_public_announce='true' if intent['mode']=='host-relay' else 'false',
   netplay_nat_traversal='false',netplay_start_as_spectator='false',
   savestate_auto_load='false',savestate_auto_save='false',config_save_on_exit='false')
  if intent.get('relayhost'):settings.update(netplay_mitm_server='custom',netplay_custom_mitm_server=intent['relayhost']+'|'+str(intent['relayport']))
  text=temp.read_text()
  for key in settings:text=re.sub(r'^\s*'+re.escape(key)+r'\s*=.*\n?','',text,flags=re.M)
  temp.write_text(text+'\n# One-session Netplay; offline configuration is untouched.\n'+''.join(k+' = '+json.dumps(v)+'\n' for k,v in settings.items()))
  host=intent['host']
  if intent.get('session'):host+='|'+str(intent['port'])+'|'+intent['session']
  args=['--host'] if intent['mode'].startswith('host-') else ['--connect',host]
  if intent['emulator']!=intent.get('launcher',intent['emulator']):args+=['-L',str(core)]
  args+=['--port',str(intent['port']),'--nick',intent['nickname']]
  atomic(BASE/'last-session.json',dict(intent,prepared=time.time()))
  return ' '.join(shlex.quote(a) for a in args)

def status(system=None,rom=None):
 p=prefs()
 for k,v in p.items():print(k.upper()+'\t'+str(v))
 ips=[]
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
  for _,interface in socket.if_nameindex():
   if interface=='lo':continue
   try:ip=socket.inet_ntoa(fcntl.ioctl(sock.fileno(),0x8915,struct.pack('256s',interface.encode()[:15]))[20:24])
   except OSError:continue
   if ip not in ips:ips.append(ip)
 print('IP\t'+(', '.join(ips) if ips else 'See Settings > Network & Wi-Fi'))
 if system:
  try:
   emulator,core=selection(system,rom);print('CORE\t'+emulator+' / '+core_info(core)[1]);print('READY\ttrue')
   if emulator!=launcher(system,rom):print('NOTE\tNetplay uses '+emulator+' for this session to fit Pi memory. Your offline emulator is unchanged.')
  except ValueError as e:print('READY\tfalse');print('NOTE\t'+str(e))
 print('NOTE\tBoth players need the same game, core version and preferably RetroArch 1.10.0. Start with NES, SNES or Mega Drive. Handheld Netplay does not emulate a link cable.')

def main():
 a=sys.argv[1:];action=a.pop(0)
 if action=='status':status(*a)
 elif action=='set':
  key,value=a;p=prefs()
  if key=='nickname':value=clean(value,24)
  elif key=='address':address(value)
  elif key=='port':
   value=int(value)
   if not 1<=value<=65535:raise ValueError('Port must be 1 to 65535')
  elif key=='relay':
   if value not in ('nyc','madrid','saopaulo','singapore'):raise ValueError('Unknown relay region')
  else:raise ValueError('Unknown setting')
  with locked():p[key]=value;atomic(BASE/'settings.json',p)
  print('OK')
 elif action=='arm':arm(*a);print('OK')
 elif action=='rooms':rooms(*a)
 elif action=='room':arm_room(*a);print('OK')
 elif action=='consume':print(consume(*a))
 elif action=='cancel':
  with locked():
   p=BASE/'pending.json'
   if p.exists():p.unlink()
  print('OK')
 else:raise ValueError('Unknown operation')

if __name__=='__main__':
 try:main()
 except Exception as e:
  # Never contaminate a shell command suffix with error output.
  if len(sys.argv)>1 and sys.argv[1]=='consume':print('Netplay not started: '+str(e),file=sys.stderr)
  else:print('ERROR\t'+str(e))
  sys.exit(1)
