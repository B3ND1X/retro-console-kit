"""Lazy isolated yt-dlp, media probing and copy-only remux. Never logs URLs."""
from pathlib import Path
import subprocess,json,time,tempfile,os,signal,threading,http.server,secrets,socket,urllib.parse
import common,policy
ROOT=common.ROOT/'runtime';NATIVE=ROOT/'native';LIB=NATIVE/'usr/lib/arm-linux-gnueabihf'
def initialize(source):
 global ROOT,NATIVE,LIB
 import runtime_store
 ROOT=runtime_store.prepare(common.ROOT,common.BASE,('native','youtube','node') if source=='youtube' else ('native',));NATIVE=ROOT/'native';LIB=NATIVE/'usr/lib/arm-linux-gnueabihf'
def native_env():
 env=dict(os.environ,LD_LIBRARY_PATH=str(LIB));env.pop('LD_PRELOAD',None);return env

def bounded(command,timeout=60,cancel=None,max_bytes=8*1024*1024,env=None):
 common.BASE.mkdir(mode=0o700,parents=True,exist_ok=True)
 with tempfile.TemporaryFile(dir=str(common.BASE)) as output,tempfile.TemporaryFile(dir=str(common.BASE)) as errors:
  p=subprocess.Popen(command,stdout=output,stderr=errors,env=env,start_new_session=True)
  start=time.monotonic()
  try:
   while p.poll() is None:
    if time.monotonic()-start>timeout or (cancel and cancel.is_set()) or os.fstat(output.fileno()).st_size>max_bytes:raise policy.CastError('Media lookup timed out or was cancelled')
    time.sleep(.15)
   if p.returncode:raise policy.CastError('Media lookup failed. The provider may require login, updated extraction support, or a different video.')
   output.seek(0);data=output.read(max_bytes+1)
   if len(data)>max_bytes:raise policy.CastError('Media response exceeded its size limit')
   return data
  finally:
   if p.poll() is None:
    os.killpg(p.pid,signal.SIGTERM)
    try:p.wait(timeout=8)
    except subprocess.TimeoutExpired:raise policy.CastError('Media lookup did not stop cleanly')

def youtube(video_id,height=720,cancel=None):
 video_id=policy.youtube_id(video_id)
 exe=ROOT/'ytdlp-run'
 if not exe.is_file():raise policy.CastError('The isolated YouTube extractor is unavailable')
 cmd=[str(exe),'--ignore-config','--no-playlist','--no-warnings','--skip-download','--dump-single-json','--js-runtimes','node:'+str(ROOT/'node'),'--socket-timeout','12','--retries','1','https://www.youtube.com/watch?v='+video_id]
 data=json.loads(bounded(cmd,timeout=100,cancel=cancel,max_bytes=16*1024*1024))
 if not isinstance(data,dict):raise policy.CastError('YouTube returned no authorized video metadata')
 if data.get('is_live'):raise policy.CastError('YouTube live playback is not enabled. Use a compatible direct HLS source instead.')
 formats=[f for f in data.get('formats',[]) if isinstance(f,dict) and isinstance(f.get('url'),str) and f['url'].startswith('https://')]
 videos=[f for f in formats if str(f.get('vcodec','')).startswith(('avc1','h264')) and 0<int(f.get('height') or 0)<=height and float(f.get('fps') or 30)<=60 and not f.get('has_drm')]
 combined=[f for f in videos if str(f.get('acodec','')).startswith(('mp4a','aac'))]
 score=lambda f:(f.get('height') or 0,f.get('tbr') or 0)
 if combined:v=max(combined,key=score);a=None
 else:
  if not videos:raise policy.CastError('This video has no compatible H.264 source at the selected quality')
  v=max(videos,key=score);audio=[f for f in formats if str(f.get('acodec','')).startswith(('mp4a','aac')) and f.get('vcodec')=='none' and not f.get('has_drm')]
  if not audio:raise policy.CastError('This video has no compatible AAC audio source')
  a=max(audio,key=lambda f:f.get('abr') or f.get('tbr') or 0)
 nets=policy.networks();url=policy.media_url(v['url'],nets);audio_url=policy.media_url(a['url'],nets) if a else None
 return dict(url=url,audio=audio_url,title=str(data.get('title','YouTube video'))[:240],duration=float(data.get('duration') or 0),height=v.get('height'),source='youtube')

def probe(url,height=1080,cancel=None):
 url=policy.media_url(url,policy.networks());exe=NATIVE/'usr/bin/ffprobe'
 if not exe.is_file():raise policy.CastError('The private media probe is unavailable')
 cmd=[str(exe),'-v','error','-rw_timeout','10000000','-protocol_whitelist','http,https,tcp,tls,crypto','-analyzeduration','2000000','-probesize','2097152','-show_streams','-show_format','-of','json',url]
 data=json.loads(bounded(cmd,timeout=18,cancel=cancel,env=native_env(),max_bytes=512*1024));video=next((s for s in data.get('streams',[]) if s.get('codec_type')=='video'),None);audio=next((s for s in data.get('streams',[]) if s.get('codec_type')=='audio'),None)
 if video:
  if video.get('codec_name')!='h264':raise policy.CastError('Use H.264 video. HEVC, AV1 and VP9 are unsupported by this lightweight receiver.')
  if int(video.get('width',0))>1920 or int(video.get('height',0))>height:raise policy.CastError('Video exceeds the selected resolution limit. Choose 1080p maximum or a smaller source.')
  try:n,d=video.get('avg_frame_rate','0/1').split('/');fps=float(n)/float(d)
  except (ValueError,ZeroDivisionError):fps=0
  if fps>60 or int(video.get('height',0))>720 and fps>30:raise policy.CastError('Use up to 720p60 or 1080p30 H.264 video')
 if not video and not audio:raise policy.CastError('No playable media stream was found')
 if audio and audio.get('codec_name') not in ('aac','mp3','alac','pcm_s16le','flac','vorbis'):raise policy.CastError('This audio codec is unsupported; use AAC or MP3')
 try:duration=float(data.get('format',{}).get('duration',0))
 except (ValueError,TypeError):duration=0
 return dict(url=url,audio=None,duration=duration,title='Network media',height=video.get('height',0) if video else 0,source='local')

class Remux:
 def __init__(self,video,audio,seconds=0):self.process=None;self.token=secrets.token_urlsafe(24);self.video=video;self.audio=audio;self.seconds=seconds;self.errors=None
 def start(self):
  owner=self
  class Handler(http.server.BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    if self.path!='/'+owner.token:self.send_error(404);return
    if owner.process:self.send_error(409);return
    cmd=[str(NATIVE/'usr/bin/ffmpeg'),'-nostdin','-v','error','-rw_timeout','10000000','-protocol_whitelist','http,https,tcp,tls,crypto']
    if owner.seconds:cmd+=['-ss',str(owner.seconds)]
    cmd+=['-i',owner.video]
    if owner.seconds:cmd+=['-ss',str(owner.seconds)]
    cmd+=['-rw_timeout','10000000','-protocol_whitelist','http,https,tcp,tls,crypto','-i',owner.audio,'-map','0:v:0','-map','1:a:0','-c','copy','-f','mpegts','pipe:1']
    owner.errors=tempfile.TemporaryFile(dir=str(common.BASE));owner.process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=owner.errors,env=native_env(),start_new_session=True);self.send_response(200);self.send_header('Content-Type','video/mp2t');self.end_headers()
    try:
     while True:
      b=owner.process.stdout.read(65536)
      if not b:break
      self.wfile.write(b)
    except (OSError,BrokenPipeError):pass
  self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True;threading.Thread(target=self.server.serve_forever,daemon=True).start();return 'http://127.0.0.1:%d/%s'%(self.server.server_port,self.token)
 def close(self):
  if self.process and self.process.poll() is None:
   os.killpg(self.process.pid,signal.SIGTERM)
   try:self.process.wait(timeout=8)
   except subprocess.TimeoutExpired:pass
  if self.process and self.process.stdout:self.process.stdout.close()
  self.server.shutdown();self.server.server_close()
  if self.errors:self.errors.close()
