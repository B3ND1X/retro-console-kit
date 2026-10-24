"""Network child. Receives only an already-open output descriptor, no root identity."""
import sys,os,json,time
sys.path.insert(0,'/usr/local/lib/snes-updater')
def main():
 from network import GitHub,safe_url
 if os.geteuid()==0:raise RuntimeError('Network retrieval must be unprivileged')
 url=safe_url(sys.argv[1]);limit=int(sys.argv[2]);fd=int(sys.argv[3]);total=0;deadline=time.monotonic()+300;client=GitHub('B3ND1X/retro-console-kit')
 with client.response(url) as source,os.fdopen(fd,'wb') as out:
  while True:
   if time.monotonic()>deadline:raise RuntimeError('Download timed out')
   block=source.read(min(262144,limit-total+1))
   if not block:break
   total+=len(block)
   if total>limit:raise RuntimeError('Download exceeds signed size or metadata limit')
   out.write(block);print(total,flush=True)
  out.flush();os.fsync(out.fileno())
if __name__=='__main__':
 try:main()
 except Exception:print('ERROR: Internet unavailable, incomplete download or HTTPS verification failed',file=sys.stderr);sys.exit(1)
