import unittest,socket,threading,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));import netplay as n
class ProbeTests(unittest.TestCase):
 def server(self,password=False,invalid_size=False):
  listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2);listener.settimeout(8);port=listener.getsockname()[1];observed=[];errors=[]
  def rec(c,size):
   data=b''
   while len(data)<size:
    part=c.recv(size-len(data))
    if not part:raise RuntimeError('Unexpected EOF')
    data+=part
   return data
  def run():
   try:
    with listener.accept()[0] as c:
     observed.append(rec(c,4));c.sendall(struct.pack('!6I',0x52414e50,131076,0,0,7,123))
    with listener.accept()[0] as c:
     c.settimeout(5);observed.append(struct.unpack('!6I',rec(c,24)));header=struct.pack('!6I',0x52414e50,131076,0,1 if password else 0,7,123)
     for i in range(0,len(header),5):c.sendall(header[i:i+5])
     if password:return
     observed.append(rec(c,40));c.sendall(struct.pack('!II',0x20,32)+b'Host'.ljust(32,b'\0'))
     data=struct.pack('!I',0xabcdef01)+b'FCEUmm'.ljust(32,b'\0')+b'(SVN) host123'.ljust(32,b'\0')
     c.sendall(struct.pack('!II',0x22,99999 if invalid_size else 68))
     if not invalid_size:c.sendall(data)
     observed.append(c.recv(100))
   except Exception as e:errors.append(str(e))
   finally:listener.close()
  thread=threading.Thread(target=run,daemon=True);thread.start();return port,thread,observed,errors
 def test_real_packet_exchange_reads_info_without_joining(self):
  port,t,seen,errors=self.server();info=n.probe('127.0.0.1',port);t.join(2);self.assertEqual(info,dict(name='FCEUmm',version='(SVN) host123',crc='ABCDEF01'));self.assertFalse(errors,errors);self.assertEqual(seen[0],b'POKE');self.assertEqual(seen[-1],b'')
 def test_password_is_unverified(self):
  port,t,seen,errors=self.server(password=True)
  with self.assertRaisesRegex(ValueError,'password'):n.probe('127.0.0.1',port)
  t.join(2);self.assertFalse(errors,errors)
 def test_unbounded_packet_rejected(self):
  port,t,seen,errors=self.server(invalid_size=True)
  with self.assertRaisesRegex(ValueError,'Unsupported'):n.probe('127.0.0.1',port)
  t.join(2)
if __name__=='__main__':unittest.main()
