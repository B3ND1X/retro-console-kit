#!/usr/bin/python3
"""Fixed Shairport session hook. No phone-supplied arguments or commands."""
import sys,time
import common
if len(sys.argv)==2 and sys.argv[1]=='prepare':
 try:
  common.rpc('airplay-prepare')
  for _ in range(140):
   if common.rpc('airplay-readiness').get('ready'):break
   time.sleep(.1)
  else:sys.exit(1)
 except Exception:sys.exit(1)
elif len(sys.argv)==2 and sys.argv[1] in ('started','ended'):
 common.BASE.mkdir(mode=0o700,parents=True,exist_ok=True);p=common.BASE/('airplay-'+sys.argv[1]);p.write_text('1');p.chmod(0o600)
