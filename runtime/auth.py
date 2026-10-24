"""Ed25519 verification using the system OpenSSL implementation (1.1.1+)."""
import ctypes,ctypes.util,base64,json
PUBLIC_TEST_KEY='d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'

def loads(data):
 def unique(pairs):
  out={}
  for k,v in pairs:
   if k in out:raise ValueError('Duplicate JSON key')
   out[k]=v
  return out
 return json.loads(data,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Non-finite JSON')))

def verify(public,signature,data):
 if len(public)!=32 or len(signature)!=64 or not data:raise ValueError('Invalid Ed25519 input')
 lib=ctypes.CDLL(ctypes.util.find_library('crypto'));ptr=ctypes.c_void_p;size=ctypes.c_size_t
 lib.OBJ_sn2nid.argtypes=[ctypes.c_char_p];lib.OBJ_sn2nid.restype=ctypes.c_int
 lib.EVP_PKEY_new_raw_public_key.argtypes=[ctypes.c_int,ptr,ptr,size];lib.EVP_PKEY_new_raw_public_key.restype=ptr
 lib.EVP_MD_CTX_new.argtypes=[];lib.EVP_MD_CTX_new.restype=ptr
 lib.EVP_DigestVerifyInit.argtypes=[ptr,ptr,ptr,ptr,ptr];lib.EVP_DigestVerifyInit.restype=ctypes.c_int
 lib.EVP_DigestVerify.argtypes=[ptr,ptr,size,ptr,size];lib.EVP_DigestVerify.restype=ctypes.c_int
 lib.EVP_MD_CTX_free.argtypes=[ptr];lib.EVP_PKEY_free.argtypes=[ptr]
 keybuf=ctypes.create_string_buffer(public);sigbuf=ctypes.create_string_buffer(signature);msg=ctypes.create_string_buffer(data);key=lib.EVP_PKEY_new_raw_public_key(lib.OBJ_sn2nid(b'ED25519'),None,keybuf,len(public));ctx=lib.EVP_MD_CTX_new()
 try:
  if not key or not ctx or lib.EVP_DigestVerifyInit(ctx,None,None,None,key)!=1 or lib.EVP_DigestVerify(ctx,sigbuf,len(signature),msg,len(data))!=1:raise ValueError('Release signature is invalid')
 finally:
  if ctx:lib.EVP_MD_CTX_free(ctx)
  if key:lib.EVP_PKEY_free(key)

def authenticated(raw,sig,keys,production=True):
 if len(raw)>256*1024:raise ValueError('Manifest too large')
 envelope=loads(sig)
 if set(envelope)!={'key_id','signature'} or envelope['key_id'] not in keys:raise ValueError('Untrusted signing key')
 public=bytes.fromhex(keys[envelope['key_id']])
 if production and public.hex()==PUBLIC_TEST_KEY:raise ValueError('Public test key is forbidden for production')
 verify(public,base64.b64decode(envelope['signature'],validate=True),raw)
 return loads(raw)
