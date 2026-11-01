#!/usr/bin/python3
"""Bounded, allowlisted console settings operations; no shell or secret argv."""
import os,sys,json,socket,tempfile,subprocess,time,re,hashlib,shutil,fcntl,urllib.request
from pathlib import Path
WPA=Path('/etc/wpa_supplicant/wpa_supplicant.conf')
ROOT=Path('/var/lib/snes-console-settings')
ALSA=Path('/etc/asound.conf')
CARDS=Path('/proc/asound')
class Error(Exception):pass

def run(args,timeout=8):
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout,env=dict(os.environ,LC_ALL='C'))
 return p.stdout.decode('utf-8','replace')
def emit(*cols):print('\t'.join(str(c).replace('\t',' ').replace('\n',' ') for c in cols))
def clean(s,n=128):
 if not isinstance(s,str) or len(s.encode())>n or any(ord(c)<32 for c in s):raise Error('Invalid text. Please try again.')
 return s
class Wpa:
 def __enter__(self):
  self.dir=tempfile.TemporaryDirectory(prefix='console-wpa-',dir='/run');self.path=self.dir.name+'/control';self.s=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);self.s.settimeout(4);self.s.bind(self.path);self.s.connect('/run/wpa_supplicant/wlan0');return self
 def __exit__(self,*args):self.s.close();self.dir.cleanup()
 def command(self,s,ok=False):
  self.s.send(s.encode());r=self.s.recv(65536).decode('utf-8','replace').strip()
  if ok and r!='OK':raise Error('Wi-Fi could not apply this setting.')
  return r

def status(w):return dict(x.split('=',1) for x in w.command('STATUS').splitlines() if '=' in x)
def unescape(s):
 # wpa_supplicant encodes nonprintable/UTF-8 bytes as \\xNN.
 data=bytearray();i=0
 while i<len(s):
  if s[i:i+2]=='\\x' and re.match(r'^[0-9a-fA-F]{2}$',s[i+2:i+4]):data.append(int(s[i+2:i+4],16));i+=4
  elif s[i:i+2]=='\\\\':data.append(92);i+=2
  else:data.extend(s[i].encode());i+=1
 return data.decode('utf-8','replace')
def parse_scan(text):
 found={}
 for line in text.splitlines()[1:]:
  r=line.split('\t',4)
  if len(r)!=5:continue
  try:signal=int(r[2])
  except ValueError:continue
  ssid=unescape(r[4]);flags=r[3]
  if not ssid:continue
  security='WPA2 / WPA' if 'PSK' in flags else 'Open' if not any(x in flags for x in ['WEP','EAP','SAE','OWE']) else 'Unsupported security'
  if ssid not in found or signal>found[ssid][0]:found[ssid]=(signal,security)
 return sorted(((s,*v) for s,v in found.items()),key=lambda x:-x[1])
def wifi_scan():
 with Wpa() as w:
  w.command('SCAN');time.sleep(3)
  for ssid,signal,security in parse_scan(w.command('SCAN_RESULTS')):emit('NETWORK',ssid,signal,security)
 emit('NOTE','Select a network. WPA/WPA2 personal and open networks are supported. Hidden networks: use Enter network name.')
def wifi_join(data,wait=45):
 ssid=clean(data.get('ssid',''),32);password=clean(data.get('password',''),64)
 if not ssid:raise Error('Enter a network name.')
 if password and not (8<=len(password)<=63 or re.fullmatch('[0-9a-fA-F]{64}',password)):raise Error('Wi-Fi passwords must be 8–63 characters, or a 64-digit hexadecimal key.')
 ROOT.mkdir(mode=0o700,parents=True,exist_ok=True);ROOT.chmod(0o700)
 with (ROOT/'wifi.lock').open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise Error('Another network change is still running.')
  if WPA.exists():shutil.copyfile(WPA,ROOT/'wifi-before.conf');(ROOT/'wifi-before.conf').chmod(0o600)
  with Wpa() as w:
   previous=status(w).get('id');networks=[line.split('\t') for line in w.command('LIST_NETWORKS').splitlines()[1:]];nid=w.command('ADD_NETWORK')
   if not nid.isdigit():raise Error('Could not create the Wi-Fi connection.')
   try:
    w.command('SET_NETWORK '+nid+' ssid '+ssid.encode().hex(),True)
    w.command('SET_NETWORK '+nid+' scan_ssid 1',True)
    priorities=[w.command('GET_NETWORK '+n[0]+' priority') for n in networks if n and n[0].isdigit()]
    priority=min(9999,max([int(v) for v in priorities if re.fullmatch(r'-?[0-9]+',v)]+[0])+1)
    w.command('SET_NETWORK '+nid+' priority '+str(priority),True)
    if password:
     psk=password if len(password)==64 else hashlib.pbkdf2_hmac('sha1',password.encode(),ssid.encode(),4096,32).hex()
     w.command('SET_NETWORK '+nid+' key_mgmt WPA-PSK',True);w.command('SET_NETWORK '+nid+' psk '+psk,True)
    else:w.command('SET_NETWORK '+nid+' key_mgmt NONE',True)
    w.command('SELECT_NETWORK '+nid,True)
    deadline=time.monotonic()+wait
    while time.monotonic()<deadline:
     s=status(w)
     if s.get('id')==nid and s.get('wpa_state')=='COMPLETED' and s.get('ip_address'):
      # Keep saved fallback networks available for future boots.
      
      for network in networks:
       if len(network)>=4 and network[0].isdigit():w.command(('DISABLE_NETWORK ' if '[DISABLED]' in network[3] else 'ENABLE_NETWORK ')+network[0],True)
      w.command('SAVE_CONFIG',True);emit('OK','Connected to '+ssid+'. Settings saved.');return
     time.sleep(1)
    raise Error('Connection failed. The previous Wi-Fi connection has been restored. Check the password and signal.')
   except Exception:
    w.command('REMOVE_NETWORK '+nid)
    if previous and previous.isdigit():w.command('SELECT_NETWORK '+previous)
    
    for network in networks:
     if len(network)>=4 and network[0].isdigit():w.command(('DISABLE_NETWORK ' if '[DISABLED]' in network[3] else 'ENABLE_NETWORK ')+network[0])
    raise

def network():
 with Wpa() as w:s=status(w);signal=dict(x.split('=',1) for x in w.command('SIGNAL_POLL').splitlines() if '=' in x)
 emit('Connection','Connected' if s.get('wpa_state')=='COMPLETED' else 'Disconnected');emit('Wi-Fi network',s.get('ssid','Not connected'));emit('IP address',s.get('ip_address','Not assigned'));emit('Signal',signal.get('RSSI','Unknown')+' dBm')
 try:
  with socket.create_connection(('1.1.1.1',443),2):pass
  emit('Internet','Reachable')
 except OSError:emit('Internet','Not reachable (local Wi-Fi may still work)')
 emit('Hostname',socket.gethostname());emit('NOTE','Wi-Fi bars: green means internet reachable, amber means local connection only, grey means disconnected.')
def bt(cmd,timeout=8):return run(['/usr/bin/bluetoothctl']+cmd,timeout)
def mac(data):
 s=data.get('address','')
 if not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}',s):raise Error('Invalid Bluetooth device.')
 return s.upper()
def bt_identity(address,listed_name,info):
 # BlueZ may publish Address before Name. Resolve properties while scanning;
 # never infer a controller brand solely from an address prefix.
 props={}
 for line in re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',info).splitlines():
  m=re.match(r'^\s*(Name|Alias|Icon|Class|Appearance|Modalias|RSSI):\s*(.*?)\s*$',line)
  if m:props[m[1]]=m[2]
 def useful(value):
  value=re.sub(r'[\x00-\x1f\x7f]',' ',value or '').strip()
  if value.upper().replace('-',':')==address.upper():return ''
  return value[:100]
 name=next((useful(v) for v in (props.get('Name'),props.get('Alias'),listed_name) if useful(v)),'Unnamed Bluetooth device')
 kind=''
 try:
  value=int(props.get('Appearance','0').split()[0],0)
  if value==964:kind='Gamepad'
  elif value==963:kind='Joystick'
  elif value==961:kind='Keyboard'
  elif value==962:kind='Mouse'
 except ValueError:pass
 if not kind:
  try:
   value=int(props.get('Class','0').split()[0],0)
   if value&0x1ffc==0x0508:kind='Gamepad'
   elif value&0x1ffc==0x0504:kind='Joystick'
  except ValueError:pass
 if not kind and props.get('Icon')=='input-gaming':kind='Game controller'
 state='Connected' if re.search(r'^\s*Connected: yes\s*$',info,re.M) else 'Paired' if re.search(r'^\s*Paired: yes\s*$',info,re.M) else 'Available'
 details=[kind] if kind else []
 rssi=props.get('RSSI','')
 if re.fullmatch(r'-?\d+',rssi):details.append('Signal '+rssi+' dBm')
 modalias=props.get('Modalias','')
 if re.fullmatch(r'(?:usb|bluetooth):v[0-9A-Fa-f]{4}p[0-9A-Fa-f]{4}d[0-9A-Fa-f]{4}',modalias):details.append('Device ID '+modalias)
 return name,state,details

def bt_list(scan=False):
 show=bt(['show']);emit('STATUS','Bluetooth on' if 'Powered: yes' in show else 'Bluetooth off or unavailable')
 process=None
 try:
  if scan:
   # Keep discovery alive during property reads so delayed names can arrive.
   process=subprocess.Popen(['/usr/bin/bluetoothctl'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,text=True)
   process.stdin.write('power on\nscan on\n');process.stdin.flush();time.sleep(12)
  deadline=time.monotonic()+12
  for line in bt(['devices'],4).splitlines():
   m=re.search(r'Device ([0-9A-F:]{17})(?: (.*))?$',line,re.I)
   if not m:continue
   address=m[1].upper();info=''
   if time.monotonic()<deadline:
    try:info=bt(['info',address],min(2,max(.1,deadline-time.monotonic())))
    except (OSError,subprocess.SubprocessError):pass
   name,state,details=bt_identity(address,m[2] or '',info)
   emit('DEVICE',address,name+' ['+address+']',state)
   if details:emit('NOTE',' / '.join(details))
  emit('NOTE','Each device shows its Bluetooth address in brackets. Names and controller type appear when advertised. Unnamed means the device has not supplied a name; keep pairing mode active and Scan again. PIN-free pairing only; existing mappings are kept.')
 finally:
  if process is not None:
   try:
    if process.poll() is None:process.stdin.write('scan off\nquit\n');process.stdin.flush();process.wait(timeout=3)
   except (OSError,subprocess.SubprocessError):
    if process.poll() is None:process.terminate();process.wait(timeout=3)
def bt_pair(data):
 address=mac(data);info=bt(['info',address]);paired='Paired: yes' in info
 if not paired:
  p=subprocess.Popen(['/usr/bin/bluetoothctl'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,text=True)
  try:
   p.stdin.write('power on\nagent NoInputNoOutput\ndefault-agent\nscan on\npair '+address+'\n');p.stdin.flush();deadline=time.monotonic()+30
   while time.monotonic()<deadline:
    if 'Paired: yes' in bt(['info',address]):paired=True;break
    time.sleep(1)
   p.stdin.write('scan off\nquit\n');p.stdin.flush();p.wait(timeout=5)
  finally:
   if p.poll() is None:p.terminate();p.wait(timeout=5)
 if not paired:raise Error('Pairing did not finish. Put the controller in pairing mode and try again. PIN-based devices need administrator setup.')
 bt(['trust',address]);bt(['connect',address],12)
 if 'Connected: yes' not in bt(['info',address]):raise Error('Paired and saved, but not connected. Wake the controller and choose Connect again.')
 info=bt(['info',address]);name=bt_identity(address,'',info)[0]
 emit('MAPPING_DEVICE',name)
 emit('OK','Bluetooth connected. Checking whether this controller needs button setup. Existing mappings are kept.')
def audio():
 cards=(CARDS/'cards').read_text();emit('NOTE','Only connected, detected audio devices are listed. Output changes affect menu and game audio after restarting EmulationStation.')
 for m in re.finditer(r'^\s*(\d+) \[([^\]]+)\].*?: (.+)$',cards,re.M):emit('OUTPUT',m[1],m[2].strip(),'HDMI' if 'HDMI' in m[3] else m[3])
 emit('INFO','HDMI is the currently detected output. Use Volume to adjust sound.')
def audio_select(data):
 card=str(data.get('card',''))
 if not re.fullmatch('[0-9]{1,2}',card) or not (CARDS/('card'+card)).exists():raise Error('This audio device is no longer connected.')
 # ALSA defaults are inherited by RetroArch, music player and EmulationStation.
 target=ALSA;ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
 backup=ROOT/'asound-before.conf'
 if not (ROOT/'audio-original.json').exists():
  (ROOT/'audio-original.json').write_text(json.dumps({'existed':target.exists()}))
  if target.exists():shutil.copy2(target,backup)
 card_id=(CARDS/('card'+card)/'id').read_text().strip()
 if not re.fullmatch('[A-Za-z0-9_-]+',card_id):raise Error('Unsupported audio device identifier.')
 text='''# Managed by SNES console Settings. Previous configuration retained for rollback.\npcm.!default {\n type plug\n slave.pcm "dmix:CARD=%s,DEV=0"\n}\nctl.!default {\n type hw\n card %s\n}\n'''%(card_id,json.dumps(card_id))
 atomic(target,text,0o644)
 controls=run(['/usr/bin/amixer','-c',card,'scontrols']);names=re.findall(r"Simple mixer control '([^']+)'",controls);mixer=next((x for x in ['Master','PCM','HDMI','Speaker','Headphone'] if x in names),names[0] if names else '')
 if mixer:emit('MIXER',mixer)
 emit('OK','Audio output saved. Restart EmulationStation from the Power menu to apply it to all audio.')
def atomic(path,text,mode=0o600):
 fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',dir=str(path.parent))
 try:
  os.fchmod(fd,mode)
  with os.fdopen(fd,'w') as f:f.write(text);f.flush();os.fsync(f.fileno())
  os.replace(name,str(path))
 finally:
  if os.path.exists(name):os.unlink(name)
def audio_store():
 subprocess.run(['/usr/sbin/alsactl','store'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
 emit('OK','Volume saved.')
def info():
 addresses=run(['/sbin/ip','-4','-o','addr','show','scope','global']);ips=re.findall(r'\binet ([0-9.]+)/',addresses);emit('IP address',', '.join(ips) if ips else 'Not connected')
 cpu=Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq');emit('CPU clock',str(int(cpu.read_text())//1000)+' MHz' if cpu.exists() else 'Unavailable')
 gpu=run(['/opt/vc/bin/vcgencmd','measure_clock','v3d']);m=re.search(r'=(\d+)',gpu);emit('GPU clock',str(int(m[1])//1000000)+' MHz' if m else 'Unavailable')
 flags=run(['/opt/vc/bin/vcgencmd','get_throttled']);m=re.search(r'=(0x[0-9a-f]+)',flags);f=int(m[1],16) if m else None;emit('Power / thermal','Unavailable' if f is None else 'Low voltage' if f&1 else 'Throttling' if f&12 else 'CPU capped' if f&2 else 'Prior power/heat event' if f&0xf0000 else 'OK')
 emit('Console',Path('/proc/device-tree/model').read_text().strip('\0'));emit('Operating system',next((s.split('=',1)[1].strip('"') for s in Path('/etc/os-release').read_text().splitlines() if s.startswith('PRETTY_NAME=')),'Linux'))
 mem={k:int(v.split()[0]) for k,v in (s.split(':',1) for s in Path('/proc/meminfo').read_text().splitlines())};emit('Memory available','%d MB / %d MB'%(mem['MemAvailable']//1024,mem['MemTotal']//1024));d=shutil.disk_usage('/');emit('Storage free','%.1f GB / %.1f GB'%(d.free/2**30,d.total/2**30));emit('Temperature',str(round(int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000,1))+' C');display=run(['/opt/vc/bin/tvservice','-s']);match=re.search(r'(\d+x\d+) @ ([0-9.]+)Hz',display);emit('Display',match[1]+' / '+match[2]+' Hz' if match else 'Unknown');emit('Uptime',str(int(float(Path('/proc/uptime').read_text().split()[0]))//60)+' minutes');emit('NOTE','SSH remains available for maintenance. No changes are made by this screen.')
def update_check():
 repo=Path('/home')
 # Resolve the invoking console user without trusting a writable path argument.
 import pwd
 home=Path(pwd.getpwnam(os.environ.get('SUDO_USER') or 'snes').pw_dir);repo=home/'RetroPie-Setup'
 current=run(['/usr/bin/git','-c','safe.directory='+str(repo),'-C',str(repo),'rev-parse','HEAD']).strip()
 if not re.fullmatch('[0-9a-f]{40}',current):current='Recovery build'
 req=urllib.request.Request('https://api.github.com/repos/RetroPie/RetroPie-Setup/commits/master',headers={'User-Agent':'SNES-Console-Settings','Accept':'application/vnd.github+json'})
 try:
  with urllib.request.urlopen(req,timeout=6) as r:latest=json.loads(r.read(1024*1024))['sha']
  emit('STATUS','RetroPie-Setup is current' if latest==current else 'Upstream revision available' if current=='Recovery build' else 'RetroPie-Setup changes are available');emit('Installed',current if current=='Recovery build' else current[:12]);emit('Latest',latest[:12])
 except Exception:emit('STATUS','Could not check online. Existing software is unchanged.')
 emit('NOTE','Check only. This customized console uses verified recovery-kit updates. Automatic OS, emulator and frontend upgrades are disabled to preserve this build.')
def main():
 action=sys.argv[1] if len(sys.argv)==2 else '';allowed={'network','wifi-scan','wifi-join','bluetooth','bluetooth-scan','bluetooth-pair','audio','audio-select','audio-store','info','updates'}
 if action not in allowed:raise Error('Unsupported setting.')
 if os.geteuid()!=0:raise Error('Settings permission is unavailable. Contact the administrator.')
 data={}
 if action in {'wifi-join','bluetooth-pair','audio-select'}:
  data=json.loads(sys.stdin.read(4097));assert isinstance(data,dict)
 {'network':network,'wifi-scan':wifi_scan,'wifi-join':lambda:wifi_join(data),'bluetooth':bt_list,'bluetooth-scan':lambda:bt_list(True),'bluetooth-pair':lambda:bt_pair(data),'audio':audio,'audio-select':lambda:audio_select(data),'audio-store':audio_store,'info':info,'updates':update_check}[action]()
if __name__=='__main__':
 try:main()
 except (Error,OSError,ValueError,AssertionError,subprocess.SubprocessError):emit('ERROR','The setting could not be completed. Check the connection and try again.' if sys.exc_info()[0]!=Error else str(sys.exc_info()[1]));sys.exit(1)
