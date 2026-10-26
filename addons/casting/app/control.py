#!/usr/bin/python3
"""Native frontend helper, private bounded JSON stdin and tab-separated status."""
import sys,json,os
import common

def main():
 action=sys.argv[1] if len(sys.argv)>1 else 'status';raw=sys.stdin.buffer.read(4097)
 if len(raw)>4096:raise ValueError('Request too large')
 req=json.loads(raw or b'{}');result=common.rpc(action,req,timeout=6)
 if os.environ.get('SNES_CAST_JSON'):print(json.dumps(result));return
 if action=='status':
  cfg=result['settings']
  for key,value in [('NAME',cfg['name']),('YOUTUBE',cfg['youtube']),('LOCAL',cfg['local']),('AIRPLAY',cfg['airplay']),('MAX_HEIGHT',cfg['max_height']),('STATE',result['state']),('SOURCE',result['source'] or 'None'),('PHASE',result['phase']),('YOUTUBE_STATUS','Connected to YouTube' if result['youtube_online'] else 'Connecting / disabled'),('DISCOVERY','DIAL advertised' if result['discovery'] else 'Off'),('PAIRED_PHONES',result['paired_phones']),('LAN_CLIENTS',result['lan_clients']),('TV_CODE',result['tv_code']),('PIN',result['pin']),('AIRPLAY_AUDIO',result['airplay_audio']),('AIRPLAY_MIRROR',result['airplay_mirroring']),('AIRPLAY_PASSWORD',result['airplay_password']),('AIRPLAY_STATUS',result.get('airplay_status','disabled')),('ERROR',result['error'])]:print(str(key)+'\t'+str(value).replace('\n',' ').replace('\t',' '))
 else:
  for k,v in result.items():
   if k!='ok':print(str(k).upper()+'\t'+str(v).replace('\n',' ').replace('\t',' '))
  print('OK\tYES')
if __name__=='__main__':
 try:main()
 except Exception as e:print('ERROR\t'+(str(e) if isinstance(e,ValueError) else 'Casting service is unavailable. Retry or restart it from Settings.'));sys.exit(1)
