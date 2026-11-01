"""Text-preserving Xbox LE compatibility migration; no device identity export."""
import re

def migrate(text):
 # Preserve deliberate administrator settings. Only supply the missing default.
 if re.search(r'^\s*Privacy\s*=',text,re.M):return text
 match=re.search(r'^\[General\][ \t]*$',text,re.M)
 if not match:raise ValueError('Bluetooth General section missing')
 return text[:match.end()]+'\n# Console Xbox LE identity exchange\nPrivacy = device\n'+text[match.end():]
