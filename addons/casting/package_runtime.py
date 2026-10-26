from pathlib import Path
import hashlib,json,tarfile,gzip,os,io,shutil
B=Path(__file__).resolve().parent;R=B/'runtime';P=B/'app/payload';P.mkdir(exist_ok=True)
# Runtime notices accompany every isolated third-party executable.
L=R/'licenses';L.mkdir(exist_ok=True)
shutil.copy2(B/'research/rpiplay/LICENSE',L/'RPiPlay-GPL3.txt');shutil.copy2(B/'research/ytdlpcast/LICENSE.txt',L/'YouTubeReceiver-MIT.txt')
for p in (B/'research/extracted/usr/share/doc').rglob('copyright'):
 shutil.copy2(p,L/(p.parent.name+'-copyright.txt'))
shutil.copy2(B/'research/node-patch.json',L/'Node-private-loader-provenance.json')
shutil.copy2(B/'research/provenance.json',L/'upstream-commits.json')
groups={'native':[p for p in R.rglob('*') if p.is_file() and (str(p.relative_to(R)).startswith(('native/','licenses/')) or p.name=='rpiplay')],'youtube':[p for p in R.rglob('*') if p.is_file() and (str(p.relative_to(R)).startswith(('ytdlp/','compat/')) or p.name=='ytdlp-run')],'node':[R/'node',R/'NODE-LICENSE',R/'node-run']}
manifest=dict(schema=1,versions=dict(yt_dlp='2026.10.21',node='22.23.4',rpiplay='1.2',shairport='3.2.2',ffmpeg='4.1.9'),components={})
for group,files in groups.items():
 archive=P/(group+'-runtime.tar.gz');entries={}
 with archive.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as gz,tarfile.open(fileobj=gz,mode='w',format=tarfile.GNU_FORMAT) as tar:
  for p in sorted(files):
   n=str(p.relative_to(R));data=p.read_bytes();mode=0o755 if n in ['node','node-run','ytdlp-run','rpiplay','ytdlp/yt-dlp_linux_armv7l','native/usr/bin/ffmpeg','native/usr/bin/ffprobe','native/usr/bin/shairport-sync'] else 0o644
   h=hashlib.sha256(data).hexdigest();entries[n]=dict(size=len(data),sha256=h,mode=mode);member=tarfile.TarInfo(n);member.size=len(data);member.mode=mode;member.mtime=0;tar.addfile(member,io.BytesIO(data))
 manifest['components'][group]=dict(archive=archive.name,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=entries);print(group,len(files),archive.stat().st_size)
(P/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
