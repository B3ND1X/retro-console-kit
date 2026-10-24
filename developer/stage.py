#!/usr/bin/env python3
"""Create clean staging from an explicit ID -> reviewed source-file map. No globs."""
import sys,json,argparse,shutil,os
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'runtime'),str(Path(__file__).resolve().parent)]
from policy import catalogue,UpdateError
from audit import audit
p=argparse.ArgumentParser();p.add_argument('--sources',type=Path,required=True);p.add_argument('--catalogue',type=Path,required=True);p.add_argument('--stage',type=Path,required=True);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
cat=catalogue(a.catalogue);sources=json.loads(a.sources.read_text());stage=a.stage.resolve()
if not isinstance(sources,dict) or not sources:raise UpdateError('An explicit source-file map is required')
if stage.exists() and any(stage.iterdir()):raise UpdateError('Staging must be empty')
for name,source in sources.items():
 if name not in cat:raise UpdateError('Unapproved file ID: '+str(name))
 path=Path(source)
 if path.is_symlink() or not path.is_file():raise UpdateError('Source must be a reviewed regular file: '+name)
 if not cat[name]['redistributable']:raise UpdateError('Redistribution is not approved: '+name)
print(json.dumps({'files':sorted(sources),'dry_run':a.dry_run},indent=2))
if not a.dry_run:
 stage.mkdir(mode=0o700,parents=True,exist_ok=True)
 try:
  for name,source in sorted(sources.items()):
   dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest);dest.chmod(cat[name]['mode'])
  audit(stage,cat)
 except Exception:
  # Keep evidence locally for correction; a failed stage cannot pass release.py.
  raise
