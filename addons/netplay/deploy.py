from pathlib import Path
import os,json,hashlib,shutil,subprocess
assert os.geteuid()==0
base=Path(__file__).resolve().parent;src=base.parent/'experience-upgrade/source';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ui=json.loads((base/'compatibility-ui-report.json').read_text());game=json.loads((base/'game-report.json').read_text())
assert ui['success'] and ui['candidate_sha256']==sha(src/'emulationstation');assert game['success']
target=Path('/opt/retropie/supplementary/emulationstation/emulationstation');launcher=Path('/opt/retropie/supplementary/runcommand/runcommand.sh')
record=base/'deployment.json';r=json.loads(record.read_text()) if record.exists() else {'files':{}}
def write(p,data,mode):
 key=str(p)
 if key not in r['files']:
  existed=p.exists();e=dict(existed=existed)
  if existed:
   old=base/'backup'/p.relative_to('/');old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,old);st=p.stat();e.update(uid=st.st_uid,gid=st.st_gid,mode=st.st_mode&0o777)
  r['files'][key]=e
 e=r['files'][key];tmp=p.with_name(p.name+'.netplay-new');tmp.write_bytes(data);tmp.chmod(mode);os.chown(tmp,e.get('uid',0),e.get('gid',0));os.replace(tmp,p);e['sha256']=sha(p);record.write_text(json.dumps(r,indent=2))
assert sha(target)==sha(base/'original/emulationstation') or sha(target)==r.get('frontend_sha256'),'Frontend changed outside this task'
s=launcher.read_text();marker='# BEGIN SNES one-session Netplay'
if marker not in s:
 needle='    user_script "runcommand-onlaunch.sh"\n';assert s.count(needle)==1
 s=s.replace(needle,needle+'''    # BEGIN SNES one-session Netplay
    if [[ "$EMULATOR" == lr-* ]]; then
        local snes_netplay_args
        snes_netplay_args="$(python3 /usr/local/lib/snes-console/netplay.py consume "$SYSTEM" "$EMULATOR" "$ROM")" || snes_netplay_args=""
        COMMAND+=" $snes_netplay_args"
    else
        python3 /usr/local/lib/snes-console/netplay.py cancel >/dev/null
    fi
    # END SNES one-session Netplay
''',1)
staged=base/'runcommand-tested.sh';staged.write_text(s);subprocess.run(['bash','-n',str(staged)],check=True)
subprocess.run(['python3',str(base.parent/'game-settings/pause_frontend.py')],check=True)
try:
 write(launcher,s.encode(),0o755)
 write(Path('/usr/local/lib/snes-console/netplay.py'),(base/'netplay.py').read_bytes(),0o644)
 write(target,(src/'emulationstation').read_bytes(),0o755);r['frontend_sha256']=sha(target);record.write_text(json.dumps(r,indent=2));os.sync()
finally:subprocess.run(['systemctl','restart','getty@tty1'],check=True)
print('Netplay installed; rollback journal:',record)
