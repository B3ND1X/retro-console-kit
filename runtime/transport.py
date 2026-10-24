"""Root-side HTTPS orchestration; network handling runs under nobody."""
import subprocess,os,pwd,tempfile
from pathlib import Path
from network import GitHub,safe_url
from policy import UpdateError
class UnprivilegedGitHub(GitHub):
 def fetch(self,url,out,limit,progress=None):
  safe_url(url);nobody=pwd.getpwnam('nobody')
  def drop():os.setgroups([]);os.setgid(nobody.pw_gid);os.setuid(nobody.pw_uid)
  proc=subprocess.Popen(['/usr/bin/python3','-I','/usr/local/lib/snes-updater/fetch.py',url,str(limit),str(out.fileno())],pass_fds=(out.fileno(),),stdout=subprocess.PIPE,stderr=subprocess.PIPE,preexec_fn=drop,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
  try:
   for line in proc.stdout:
    if len(line)>32 or not line.strip().isdigit():raise UpdateError('Invalid download progress')
    if progress:progress(int(line),limit)
   result=proc.wait(timeout=15)
   if result:raise UpdateError('Internet unavailable, incomplete download or HTTPS verification failed. Check Wi-Fi and the console clock.')
  finally:
   if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
   proc.stdout.close();proc.stderr.close()
 def small(self,url,limit):
  with tempfile.TemporaryFile() as out:self.fetch(url,out,limit);out.seek(0);return out.read(limit+1)
 def download(self,url,dest,size,progress=None,cancelled=None):
  dest=Path(dest);part=dest.with_name(dest.name+'.partial')
  try:
   with part.open('xb') as out:self.fetch(url,out,size,progress)
   if part.stat().st_size!=size:raise UpdateError('Interrupted or incomplete download')
   os.replace(part,dest)
  finally:
   if part.exists():part.unlink()
