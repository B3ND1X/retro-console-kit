"""Small authenticated LAN send-to-console page, bounded requests and no CORS."""
import http.server,threading,json,urllib.parse,secrets,hmac,time,collections
import common,policy
PAGE='''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>SNES Console Casting</title><style>body{font:18px system-ui;background:#101821;color:#eee;max-width:600px;margin:40px auto;padding:20px}input,button{font:inherit;padding:12px;margin:6px;border-radius:8px;max-width:90%}button{background:#245a7e;color:white;border:0}small{color:#aac}</style><h1>SNES Console</h1><p>Enter the pairing PIN shown in Settings &gt; Casting &amp; AirPlay.</p><input id="pin" type="password" inputmode="numeric" placeholder="Pairing PIN"><button onclick="pair()">Connect</button><hr><input id="url" placeholder="Direct MP4/HLS URL or YouTube URL"><button onclick="send(false)">Play</button><button onclick="send(true)">Queue</button><p><button onclick="act('pause')">Pause</button><button onclick="act('resume')">Play</button><button onclick="act('next')">Next</button><button onclick="act('disconnect')">Stop / Disconnect</button></p><input id="seek" type="number" min="0" placeholder="Seek to seconds"><button onclick="act('seek',+document.getElementById('seek').value)">Seek</button><input id="vol" type="range" min="0" max="100" value="100" onchange="act('volume',+this.value)"><p id="state">Not connected</p><small>Trusted local network only. H.264/AAC MP4 and compatible HLS. Close games before casting.</small><script>let token='';async function api(path,data){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(data)});let x=await r.json();if(!r.ok||!x.ok)throw Error(x.error||'Request failed');return x}function status(t){document.getElementById('state').textContent=t}async function pair(){try{let x=await api('/pair',{pin:document.getElementById('pin').value});token=x.token;document.getElementById('pin').value='';status('Connected')}catch(e){status(e.message)}}async function send(append){try{await api('/api/play',{url:document.getElementById('url').value,append});status('Request accepted')}catch(e){status(e.message)}}async function act(action,value){try{await api('/api/control',{action,value});}catch(e){status(e.message)}}setInterval(async()=>{if(!token)return;try{let x=await api('/api/status',{});status(x.source+' '+x.state+' '+Math.floor(x.position)+'s'+(x.error?' — '+x.error:''))}catch(e){status(e.message)}},3000)</script>'''.encode('utf-8')
class LAN:
 def __init__(self,c):self.c=c;self.pin=secrets.token_hex(3);self.pin_expiry=0;self.tokens={};self.attempts=collections.defaultdict(list);self.server=None;self.slots=threading.BoundedSemaphore(8)
 def new_pin(self):self.pin='%06d'%secrets.randbelow(1000000);self.pin_expiry=time.monotonic()+600;return self.pin
 def start(self,host="0.0.0.0",port=8010):
  owner=self
  class Server(http.server.ThreadingHTTPServer):
   daemon_threads=True;allow_reuse_address=True
   def process_request(server,request,address):
    if not owner.slots.acquire(False):request.close();return
    def work():
     try:server.process_request_thread(request,address)
     finally:owner.slots.release()
    threading.Thread(target=work,daemon=True).start()
  class Handler(http.server.BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def setup(self):super().setup();self.connection.settimeout(4)
   def reply(self,code,value):
    b=json.dumps(value).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
   def admitted(self):return policy.local_client(self.client_address[0],owner.c.net)
   def do_GET(self):
    if not self.admitted():return self.reply(403,dict(ok=False,error='Local network only'))
    if self.path!='/':return self.reply(404,dict(ok=False,error='Not found'))
    self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'");self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(PAGE)));self.end_headers();self.wfile.write(PAGE)
   def do_POST(self):
    if not self.admitted():return self.reply(403,dict(ok=False,error='Local network only'))
    origin=self.headers.get('Origin')
    if origin and urllib.parse.urlsplit(origin).netloc!=self.headers.get('Host'):return self.reply(403,dict(ok=False,error='Cross-origin request rejected'))
    try:
     length=int(self.headers.get('Content-Length','0'))
     if not 0<length<=16384:raise policy.CastError('Invalid request size')
     data=json.loads(self.rfile.read(length));now=time.monotonic();ip=self.client_address[0]
     if not isinstance(data,dict):raise policy.CastError('Invalid request')
     if self.path=='/pair':
      owner.attempts[ip]=[t for t in owner.attempts[ip] if now-t<60]
      if len(owner.attempts[ip])>=5:return self.reply(429,dict(ok=False,error='Wait one minute before pairing again'))
      owner.attempts[ip].append(now)
      if now>owner.pin_expiry or not hmac.compare_digest(str(data.get('pin','')),owner.pin):raise policy.CastError('Wrong or expired pairing PIN')
      token=secrets.token_urlsafe(32);owner.tokens[token]=(ip,now+3600);return self.reply(200,dict(ok=True,token=token))
     token=self.headers.get('Authorization','').removeprefix('Bearer ') if hasattr(str,'removeprefix') else self.headers.get('Authorization','')[7:] if self.headers.get('Authorization','').startswith('Bearer ') else ''
     if owner.tokens.get(token,('',0))[0]!=ip or owner.tokens.get(token,('',0))[1]<now:return self.reply(401,dict(ok=False,error='Pair this phone from the console first'))
     if self.path=='/api/play':
      url=data.get('url','');u=urllib.parse.urlsplit(url)
      if u.hostname in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be'):
       if u.scheme!='https':raise policy.CastError('Use an HTTPS YouTube link')
       video=u.path.strip('/') if u.hostname=='youtu.be' else urllib.parse.parse_qs(u.query).get('v',[''])[0];r=owner.c.submit('youtube',video,append=bool(data.get('append')))
      else:r=owner.c.submit('local',url,append=bool(data.get('append')))
     elif self.path=='/api/control':r=owner.c.control(data.get('action'),data.get('value'))
     elif self.path=='/api/status':
      r=owner.c.status();r={k:r[k] for k in ['ok','phase','source','state','position','duration','queued','error']}
     else:return self.reply(404,dict(ok=False,error='Not found'))
     self.reply(200,r)
    except policy.CastError as e:self.reply(400,dict(ok=False,error=str(e)[:240]))
    except (ValueError,TypeError,KeyError,OSError):self.reply(400,dict(ok=False,error='Request rejected. Check the URL, receiver settings and whether a game is active.'))
  self.server=Server((host,port),Handler);threading.Thread(target=self.server.serve_forever,name='cast-lan',daemon=True).start()
 def stop(self):
  if self.server:self.server.shutdown();self.server.server_close();self.server=None
