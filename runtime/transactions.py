"""Shared recovery/OTA journal primitives. Per-file atomicity, not whole-update atomicity."""
import os,json,stat,shutil,hashlib,uuid
from pathlib import Path,PurePosixPath

def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def sync_dir(path):
 fd=os.open(str(path),os.O_DIRECTORY|os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)

def durable_mkdir(path,mode=0o700):
 path=Path(path)
 if path.exists():
  if path.is_symlink() or not path.is_dir():raise ValueError('Unsafe journal directory')
  return
 durable_mkdir(path.parent,mode);path.mkdir(mode=mode);sync_dir(path.parent)

def append_journal(path,entry):
 with Path(path).open('a') as f:f.write(json.dumps(entry,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
 sync_dir(Path(path).parent)

def durable_copy(source,target):
 with Path(source).open('rb') as src,Path(target).open('wb') as out:shutil.copyfileobj(src,out,1024*1024);out.flush();os.fsync(out.fileno())
 shutil.copystat(source,target)
 with Path(target).open('rb') as ready:os.fsync(ready.fileno())
 sync_dir(Path(target).parent)

def atomic_install(path,data,mode=0o644,owner=None,link=None):
 path=Path(path);temporary=path.with_name('.'+path.name+'.transaction-'+uuid.uuid4().hex)
 try:
  if link is not None:temporary.symlink_to(link)
  else:
   with os.fdopen(os.open(str(temporary),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:
    if isinstance(data,Path):
     with data.open('rb') as src:shutil.copyfileobj(src,f,1024*1024)
    else:f.write(data)
    f.flush();os.fsync(f.fileno())
   temporary.chmod(mode)
  if owner is not None:os.lchown(temporary,*owner)
  if link is None:
   with temporary.open('rb') as ready:os.fsync(ready.fileno())
  os.replace(temporary,path);sync_dir(path.parent)
 finally:
  if temporary.exists() or temporary.is_symlink():temporary.unlink()

def safe_relative(name):
 if not isinstance(name,str) or not name or '\\' in name or '\x00' in name:raise ValueError('Invalid transaction path')
 p=PurePosixPath(name)
 if p.is_absolute() or any(v in ('','..','.') for v in name.split('/')):raise ValueError('Unsafe transaction path')
 return name

def checked_path(root,name):
 root=Path(root).resolve();p=root/safe_relative(name)
 # An update never follows even an in-root symlink; offline recovery can retain its own policy.
 for parent in [p]+list(p.parents):
  if parent==root:break
  if parent.is_symlink():raise ValueError('Symlink in managed path: '+name)
 if root!=p.parent.resolve() and root not in p.parent.resolve().parents:raise ValueError('Path leaves target')
 return p

class FileTransaction:
 def __init__(self,root,directory,allowed):
  self.root=Path(root).resolve();self.directory=Path(directory);self.allowed=set(allowed);durable_mkdir(self.directory);self.journal=self.directory/'journal.jsonl';self.seen=set()
 def mkdir(self,path):
  if path.exists():
   if not path.is_dir() or path.is_symlink():raise ValueError('Unsafe directory')
   return
  self.mkdir(path.parent);append_journal(self.journal,dict(path=str(path.relative_to(self.root)),kind='newdir'));path.mkdir(mode=0o755);sync_dir(path.parent)
 def remember(self,path):
  name=str(path.relative_to(self.root))
  if name not in self.allowed:raise ValueError('Unapproved transaction target')
  if name in self.seen:return
  self.seen.add(name);entry=dict(path=name,kind='file',existed=path.exists())
  if path.exists():
   if not path.is_file() or path.is_symlink():raise ValueError('Expected regular managed file')
   st=path.stat();entry.update(uid=st.st_uid,gid=st.st_gid,mode=stat.S_IMODE(st.st_mode),before_sha256=digest(path));backup=self.directory/'original'/name;durable_mkdir(backup.parent);durable_copy(path,backup)
  append_journal(self.journal,entry)
 def write(self,name,data,mode=0o644,owner=None):
  path=checked_path(self.root,name);self.mkdir(path.parent);self.remember(path);atomic_install(path,data,mode,owner)
 def rollback(self):rollback(self.directory,self.root,strict=True)

def rollback(directory,root,strict=False):
 root=Path(root).resolve();directory=Path(directory);journal=directory/'journal.jsonl';raw=journal.read_bytes().splitlines() if journal.exists() else [];rows=[]
 for index,line in enumerate(raw):
  try:rows.append(json.loads(line))
  except ValueError:
   if index!=len(raw)-1:raise ValueError('Corrupt transaction journal')
   # Power loss can truncate the last record. Replacement only follows a fully fsynced record.
 for row in reversed(rows):
  name=safe_relative(row['path']);path=checked_path(root,name) if strict else root/name
  if root!=path.parent.resolve() and root not in path.parent.resolve().parents:raise ValueError('Rollback path escape')
  if row['kind']=='newdir':
   try:path.rmdir();sync_dir(path.parent)
   except OSError:pass
   continue
  if row['existed']:
   source=directory/'original'/name
   if row.get('before_sha256') and digest(source)!=row['before_sha256']:raise ValueError('Rollback backup checksum mismatch')
   if source.is_symlink():atomic_install(path,None,owner=(row['uid'],row['gid']) if os.geteuid()==0 else None,link=os.readlink(source))
   else:atomic_install(path,source,row['mode'],(row['uid'],row['gid']) if os.geteuid()==0 else None)
  elif path.exists() or path.is_symlink():
   if path.is_dir() and not path.is_symlink():raise ValueError('Unexpected rollback directory')
   path.unlink();sync_dir(path.parent)
