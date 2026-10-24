"""Authenticated application-update orchestration over the recovery installer's journal."""
import os,json,time,shutil,fcntl,stat,subprocess,ast,uuid,importlib.util
from pathlib import Path
from auth import loads,authenticated
from policy import UpdateError,catalogue,validate_manifest,version,repository,TARGET,unpack,MAX_PACKAGE
from transactions import digest,atomic_install,sync_dir,checked_path,rollback,durable_mkdir

def save(path,value,mode=0o600):
 path=Path(path);durable_mkdir(path.parent);atomic_install(path,(json.dumps(value,sort_keys=True)+'\n').encode(),mode)
def load(path,default=None):return loads(Path(path).read_bytes()) if Path(path).exists() else ({} if default is None else default)

class Engine:
 def __init__(self,root,transport=None,validate=None,fault=None):
  self.root=Path(root).resolve();self.fixture=self.root!=Path('/')
  if self.fixture and (os.geteuid()==0 or not (self.root/'.snes-ota-test-root').is_file()):raise UpdateError('Alternate roots require an unprivileged marked fixture')
  self.state=self.at('/var/lib/snes-updater');self.config_path=self.at('/etc/snes-updater/config.json');self.cat=catalogue(self.at('/etc/snes-updater/catalogue.json'));self.transport=transport;self.validation=validate;self.fault=fault
  self.state.mkdir(parents=True,exist_ok=True);self.active=self.state/'active.json'
 def at(self,path):return self.root/path.lstrip('/')
 def config(self):
  cfg=load(self.config_path);cfg.setdefault('auto_check',False);cfg.setdefault('check_interval_hours',24);return cfg
 def installed(self):
  current=load(self.state/'installed.json',dict(version='1.0.0',floor='1.0.0',managed={},migrations=[]))
  current['floor']=max(current['floor'],load(self.state/'highest.json',{'version':'1.0.0'})['version'],key=version)
  return current
 def retain_floor(self,v):
  current=load(self.state/'highest.json',{'version':'1.0.0'})['version'];save(self.state/'highest.json',{'version':max(current,v,key=version)})
 def status(self,phase,message='',**fields):
  current=load(self.state/'status.json');current.update(phase=phase,message=message,updated=time.time(),**fields);save(self.state/'status.json',current,0o644)
 def history(self,event,**fields):
  from transactions import append_journal
  append_journal(self.state/'history.jsonl',dict(time=time.time(),event=event,**fields))
 def lock(self):
  lock=(self.state/'operation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);return lock
 def facts(self):
  if self.fixture:return load(self.root/'fixture.json')
  import re,platform
  fields=dict(re.findall(r'^([A-Z_]+)=["\']?([^\n"\']*)',self.at('/etc/os-release').read_text(),re.M));arch=subprocess.check_output(['dpkg','--print-architecture']).decode().strip();model=self.at('/proc/device-tree/model').read_bytes().rstrip(b'\0').decode()
  return dict(os_id=fields.get('ID'),os_version=fields.get('VERSION_ID'),architecture=arch,model=model)
 def compatible(self):
  c=self.config();f=self.facts();expected=c['compatibility']
  if any(f.get(k)!=v for k,v in expected.items()):raise UpdateError('OS, architecture or Pi model does not match this update target')
  return c['target']
 def client(self):
  if self.transport:return self.transport
  from transport import UnprivilegedGitHub
  return UnprivilegedGitHub(self.config()['repository'])
 def trust(self):
  keys=load(self.at('/etc/snes-updater/trusted-keys.json'))
  if not keys:raise UpdateError('Updates are disabled until the owner enrolls a trusted public signing key')
  return keys
 def authentic(self,raw,sig):
  m=authenticated(raw,sig,self.trust(),production=not self.fixture);state=self.installed();validate_manifest(m,self.cat,self.config()['repository'],self.compatible(),state['version'],state['floor']);return m
 def check(self):
  c=self.config();repository(c.get('repository',''));self.trust();self.compatible();client=self.client();self.status('CHECKING','Checking signed GitHub Releases',progress=0);releases=client.releases();candidates=[];rejected=[]
  for release in releases:
   tag=release.get('tag_name','')
   try:v=version(tag[1:]) if tag.startswith('v') else None
   except UpdateError:continue
   if v and v>max(version(self.installed()['version']),version(self.installed()['floor'])):candidates.append((v,tag,release))
  for _,tag,r in sorted(candidates,reverse=True)[:6]:
   names={a.get('name') for a in r.get('assets',[]) if isinstance(a,dict)};stem='manifest-'+c['target']
   if not {stem+'.json',stem+'.sig'}<=names:continue
   try:
    raw=client.small(client.asset_url(tag,stem+'.json'),256*1024);sig=client.small(client.asset_url(tag,stem+'.sig'),2048);m=self.authentic(raw,sig)
    if 'v'+m['version']!=tag:raise UpdateError('Signed version does not match release tag')
    cache=self.state/'available';cache.mkdir(exist_ok=True,mode=0o700);atomic_install(cache/'manifest.json',raw,0o600);atomic_install(cache/'manifest.sig',sig,0o600);save(cache/'source.json',dict(repository=c['repository'],tag=tag,manifest_sha256=digest(cache/'manifest.json')))
    self.status('AVAILABLE','Verified update available',available=m['version'],notes=m['notes'],size=m['archive']['size'],progress=0);return m
   except Exception as e:rejected.append(str(e))
  if rejected:raise UpdateError('Release rejected: '+rejected[0])
  self.status('CURRENT','No compatible newer signed release is published',available='',notes='',size=0);return None
 def package(self,progress=None):
  cache=self.state/'available';raw=(cache/'manifest.json').read_bytes();sig=(cache/'manifest.sig').read_bytes();m=self.authentic(raw,sig);source=load(cache/'source.json')
  if source['repository']!=self.config()['repository'] or source['tag']!='v'+m['version']:raise UpdateError('Repository changed; check for updates again')
  required=sum(r['size'] for r in m['files'])*3+m['archive']['size']+64*1024*1024
  if shutil.disk_usage(self.state).free<required:raise UpdateError('Insufficient storage for download, staged files and rollback')
  work=self.state/('job-'+uuid.uuid4().hex);work.mkdir(mode=0o700);archive=work/m['archive']['name'];client=self.client();self.status('DOWNLOADING','Downloading verified release archive',progress=0)
  try:
   client.download(client.asset_url(source['tag'],m['archive']['name']),archive,m['archive']['size'],progress or (lambda n,t:self.status('DOWNLOADING','Downloading update',progress=int(100*n/t))))
   self.status('VERIFYING','Verifying every signed payload file',progress=0);unpack(archive,m,work/'payload');return m,work
  except Exception:
   shutil.rmtree(work);raise
 def secure_destination(self,path):
  p=checked_path(self.root,path.lstrip('/'))
  if not self.fixture:
   for parent in [p.parent]+list(p.parent.parents):
    if not parent.exists():continue
    st=parent.stat()
    if st.st_uid!=0 or st.st_mode&0o022:raise UpdateError('Managed directory is not administrator-owned and protected: '+str(parent))
    if parent==self.root:break
  return p
 def plan(self,m,work):
  previous=self.installed();files=[];next_managed=dict(previous['managed'])
  for row in m['files']:
   source=checked_path(work/'payload',row['path'])
   if not source.is_file() or source.stat().st_size!=row['size'] or digest(source)!=row['sha256']:raise UpdateError('Staged payload changed after signature verification')
   e=self.cat[row['path']];dest=self.secure_destination(e['destination']);source=work/'payload'/row['path'];current=digest(dest) if dest.is_file() else None;baseline=previous['managed'].get(row['path'])
   if dest.exists() and not dest.is_file():raise UpdateError('Managed destination is not a regular file')
   if dest.exists() and current!=row['sha256'] and current!=baseline:raise UpdateError('Local customization preserved; update conflicts with '+row['path'])
   if current!=row['sha256']:files.append((e['destination'].lstrip('/'),source,e['mode']))
   next_managed[row['path']]=row['sha256']
  return files,next_managed
 def validate_files(self,files):
  for relative,_,mode in files:
   p=self.at('/'+relative)
   if p.suffix=='.py':ast.parse(p.read_text(),filename=relative)
   if p.suffix=='.sh':subprocess.run(['/bin/bash','--noprofile','--norc','-n',str(p)],check=True,timeout=8,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
   if p.name=='emulationstation':
    with p.open('rb') as f:data=f.read(64)
    if data[:6]!=b'\x7fELF\x01\x01' or int.from_bytes(data[18:20],'little')!=40:raise UpdateError('Frontend binary is not compatible ARM32 ELF')
    if not self.fixture:
     import re
     dynamic=subprocess.check_output(['/usr/bin/readelf','-d',str(p)],timeout=12,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'}).decode()
     needed=re.findall(r'\(NEEDED\).*?\[([^\]]+)\]',dynamic);cache=subprocess.check_output(['/sbin/ldconfig','-p'],timeout=8).decode()
     missing=[n for n in needed if not re.fullmatch(r'[A-Za-z0-9_.+-]+',n) or not re.search(r'(?m)^\s*'+re.escape(n)+r'\s',cache)]
     if missing:raise UpdateError('Missing frontend shared libraries: '+', '.join(missing))
 def apply(self,m,work):
  # Reauthenticate the on-disk manifest immediately before using any payload.
  raw=(self.state/'available/manifest.json').read_bytes();sig=(self.state/'available/manifest.sig').read_bytes();again=self.authentic(raw,sig)
  if again!=m:raise UpdateError('Staged update metadata changed')
  files,next_managed=self.plan(m,work)
  backup_bytes=sum(self.at('/'+p).stat().st_size for p,_,_ in files if self.at('/'+p).exists())
  if shutil.disk_usage(self.state).free<backup_bytes+sum(source.stat().st_size for _,source,_ in files)+32*1024*1024:raise UpdateError('Insufficient storage for actual rollback preimages')
  previous=self.installed();journal=self.state/('transactions/'+uuid.uuid4().hex);durable_mkdir(journal)
  save(journal/'previous-installed.json',previous);save(self.active,dict(phase='APPLYING',journal=str(journal.relative_to(self.state)),version=m['version']))
  self.status('INSTALLING','Backing up and applying application files',progress=0)
  try:
   # Import the same application-only installer used by the recovery kit.
   import restore
   allowed=[p for p,_,_ in files]
   def progress(n,total):
    self.status('INSTALLING','Applying application files',progress=int(n*100/max(1,total)))
    if self.fault:self.fault(n)
   restore.apply_software_update(self.root,journal,files,allowed,progress)
   migrations=list(previous.get('migrations',[]))
   for migration in m['migrations']:
    if migration in migrations:continue
    # Built-in defaults are interpreted at read time; never replace user preferences.
    migrations.append(migration)
   save(self.active,dict(phase='VALIDATING',journal=str(journal.relative_to(self.state)),version=m['version']));self.status('VALIDATING','Restarting and validating the new frontend',progress=100)
   self.validate_files(files)
   if self.validation:self.validation()
   elif not self.fixture:raise UpdateError('Live frontend readiness validator is required')
   # Commit metadata in the same journal, then write a durable commit marker last.
   from transactions import FileTransaction
   tx=FileTransaction(self.root,journal,['var/lib/snes-updater/installed.json']);new=dict(version=m['version'],floor=m['version'],managed=next_managed,migrations=migrations,previous=str(journal.relative_to(self.state)))
   tx.write('var/lib/snes-updater/installed.json',(json.dumps(new,sort_keys=True)+'\n').encode(),0o600,(0,0) if not self.fixture else None)
   if self.fault:self.fault('before-commit')
   atomic_install(journal/'COMMITTED',b'committed\n',0o600)
   if self.fault:self.fault('after-commit')
   self.retain_floor(m['version']);self.active.unlink();sync_dir(self.state);self.history('installed',version=m['version']);self.status('SUCCESS','Update installed and frontend validated',installed=m['version'],progress=100)
  except Exception as e:
   if (journal/'COMMITTED').exists():raise UpdateError('Update committed; recovery must finalize its durable metadata') from e
   rollback(journal,self.root,strict=True);save(self.state/'installed.json',previous);self.active.unlink();sync_dir(self.state);self.history('failed',version=m['version'],reason=str(e));self.status('FAILED','Update failed; previous application files restored: '+str(e),progress=0);raise
  finally:
   if not self.active.exists() and work.exists():shutil.rmtree(work)
 def recover(self):
  if not self.active.exists():
   stale=load(self.state/'status.json').get('phase')
   if stale in ['QUEUED','CHECKING','DOWNLOADING','VERIFYING','INSTALLING','VALIDATING','ROLLING_BACK']:
    self.status('RECOVERED','An interrupted operation ended; installed application files are ready',progress=0)
   for job in self.state.glob('job-*'):
    if job.is_dir() and not job.is_symlink():shutil.rmtree(job)
   return False
  active=load(self.active);relative=active.get('journal','')
  if not relative.startswith('transactions/') or len(Path(relative).parts)!=2:raise UpdateError('Invalid interrupted-update journal')
  journal=self.state/relative
  if (journal/'COMMITTED').exists() and active.get('phase')!='ROLLING_BACK':self.retain_floor(active['version']);self.active.unlink();sync_dir(self.state);self.status('SUCCESS','Committed update recovered successfully',installed=active['version'],progress=100);return False
  rollback(journal,self.root,strict=True);save(self.state/'installed.json',load(journal/'previous-installed.json'));self.active.unlink();sync_dir(self.state);self.history('recovered',version=active.get('version'));self.status('RECOVERED','Interrupted update rolled back before frontend startup',progress=0);return True
 def previous(self):
  installed=self.installed();relative=installed.get('previous')
  if not relative or not relative.startswith('transactions/') or len(Path(relative).parts)!=2:raise UpdateError('No previous application version is available')
  journal=self.state/relative
  by_destination={e['destination'].lstrip('/'):name for name,e in self.cat.items()}
  for line in (journal/'journal.jsonl').read_text().splitlines():
   entry=loads(line);name=by_destination.get(entry['path'])
   if entry['kind']=='file' and name:
    current=self.secure_destination('/'+entry['path']);expected=installed['managed'].get(name)
    if not current.is_file() or digest(current)!=expected:raise UpdateError('Local customization preserved; rollback conflicts with '+name)
  before=load(journal/'previous-installed.json');self.retain_floor(installed['floor']);save(self.active,dict(phase='ROLLING_BACK',journal=relative,version=before['version']))
  rollback(journal,self.root,strict=True);before['floor']=max(installed['floor'],before['floor'],key=version);before.pop('previous',None);save(self.state/'installed.json',before)
  if self.validation:self.validation()
  self.active.unlink();sync_dir(self.state);self.history('rollback',version=before['version']);self.status('ROLLED_BACK','Previous application version restored',installed=before['version']);return before
