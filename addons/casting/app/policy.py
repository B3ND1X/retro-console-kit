"""LAN admission and media-URL validation. No shell command interpolation."""
from pathlib import Path
import ipaddress,socket,urllib.parse,re,subprocess,json,fcntl,os
class CastError(ValueError):pass
def networks():
 try:
  entries=json.loads(subprocess.check_output(['/sbin/ip','-j','-4','addr','show'],timeout=2));return [ipaddress.ip_network(a['local']+'/'+str(a['prefixlen']),strict=False) for e in entries if e.get('operstate')=='UP' for a in e.get('addr_info',[]) if a.get('scope')=='global' and ipaddress.ip_address(a['local']).is_private]
 except Exception:return []
def local_client(address,nets):
 try:a=ipaddress.ip_address(address);return a.is_private and not a.is_loopback and any(a in n for n in nets)
 except ValueError:return False
def media_url(value,nets,resolve=socket.getaddrinfo):
 if not isinstance(value,str) or len(value)>8192 or any(ord(c)<33 or ord(c)==127 for c in value):raise CastError('Invalid media URL')
 try:u=urllib.parse.urlsplit(value);port=u.port
 except ValueError:raise CastError('Invalid media URL')
 if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.fragment:raise CastError('Use a direct HTTP or HTTPS media URL without credentials')
 if port is not None and (not 1<=port<=65535 or port in [22,23,25,53,111,139,445,2375,2376,3306,5432,6379]):raise CastError('This destination port is not allowed')
 try:addrs={ipaddress.ip_address(r[4][0]) for r in resolve(u.hostname,port or (443 if u.scheme=='https' else 80),type=socket.SOCK_STREAM)}
 except (OSError,ValueError):raise CastError('Media hostname could not be resolved')
 if not addrs:raise CastError('Media hostname could not be resolved')
 for a in addrs:
  if a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified or (a.is_private and not any(a in n for n in nets)):raise CastError('Media destination is outside the allowed network')
 return value

def youtube_id(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',value):raise CastError('Invalid YouTube video ID')
 return value

def game_busy():
 for p in Path('/proc').glob('[0-9]*'):
  try:
   exe=os.readlink(str(p/'exe'))
   if exe.startswith('/opt/retropie/emulators/') or exe=='/usr/bin/omxplayer.bin':return True
  except OSError:pass
 try:
  fd=os.open('/run/snes-updater/game.lock',os.O_RDONLY)
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);return False
  except BlockingIOError:return True
  finally:os.close(fd)
 except OSError:return True
