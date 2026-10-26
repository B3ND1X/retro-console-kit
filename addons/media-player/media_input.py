"""Read existing EmulationStation SDL joystick mappings; never remap or grab devices."""
import ctypes,ctypes.util,xml.etree.ElementTree as ET
from pathlib import Path
class GUID(ctypes.Structure):_fields_=[('data',ctypes.c_uint8*16)]
class Controller:
 def __init__(self):
  __import__('os').environ['SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS']='1'
  self.lib=ctypes.CDLL(ctypes.util.find_library('SDL2') or 'libSDL2-2.0.so.0');l=self.lib
  l.SDL_Init.argtypes=[ctypes.c_uint32];l.SDL_Init.restype=ctypes.c_int
  l.SDL_JoystickOpen.argtypes=[ctypes.c_int];l.SDL_JoystickOpen.restype=ctypes.c_void_p
  l.SDL_JoystickGetGUID.argtypes=[ctypes.c_void_p];l.SDL_JoystickGetGUID.restype=GUID
  l.SDL_JoystickGetGUIDString.argtypes=[GUID,ctypes.c_void_p,ctypes.c_int]
  l.SDL_JoystickInstanceID.argtypes=[ctypes.c_void_p];l.SDL_JoystickInstanceID.restype=ctypes.c_int
  l.SDL_JoystickName.argtypes=[ctypes.c_void_p];l.SDL_JoystickName.restype=ctypes.c_char_p
  l.SDL_JoystickClose.argtypes=[ctypes.c_void_p];l.SDL_PollEvent.argtypes=[ctypes.c_void_p]
  if l.SDL_Init(0x200)!=0:raise RuntimeError('Controller input unavailable')
  self.handles=[];self.maps={};self.states={}
  try:configs=ET.parse(str(Path.home()/'.emulationstation/es_input.cfg')).getroot().findall('inputConfig')
  except (OSError,ET.ParseError):configs=[]
  for index in range(l.SDL_NumJoysticks()):
   h=l.SDL_JoystickOpen(index)
   if not h:continue
   self.handles.append(h);buffer=ctypes.create_string_buffer(33);l.SDL_JoystickGetGUIDString(l.SDL_JoystickGetGUID(h),buffer,33);guid=buffer.value.decode();name=(l.SDL_JoystickName(h) or b'').decode(errors='replace')
   config=next((c for c in configs if c.get('deviceGUID','').lower()==guid.lower()),None)
   if config is None:config=next((c for c in configs if c.get('deviceName')==name),None)
   if config is not None:self.maps[l.SDL_JoystickInstanceID(h)]={c.get('name'):(c.get('type'),int(c.get('id')),int(c.get('value'))) for c in config.findall('input') if c.get('name') in ['a','b','x','y','left','right','up','down']}
 def poll(self):
  import struct
  out=[];event=ctypes.create_string_buffer(64)
  while self.lib.SDL_PollEvent(event):
   data=event.raw;kind=int.from_bytes(data[:4],'little')
   if kind not in (0x600,0x602,0x603,0x604):continue
   instance=struct.unpack_from('<i',data,8)[0];index=data[12];value=struct.unpack_from('<h',data,16)[0] if kind==0x600 else data[13]
   for action,(typ,number,expected) in self.maps.get(instance,{}).items():
    if index!=number:continue
    active=(typ=='button' and kind==0x603 and bool(value)) or (typ=='axis' and kind==0x600 and value*expected>16000) or (typ=='hat' and kind==0x602 and bool(value&expected))
    key=(instance,action)
    if active and not self.states.get(key):out.append(action)
    if (typ=='button' and kind in (0x603,0x604)) or (typ=='axis' and kind==0x600) or (typ=='hat' and kind==0x602):self.states[key]=active
  return out
 def close(self):
  for h in self.handles:self.lib.SDL_JoystickClose(h)
  self.lib.SDL_Quit()
