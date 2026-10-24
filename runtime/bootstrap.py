#!/usr/bin/python3
import sys
sys.path.insert(0,'/usr/local/lib/snes-updater')
from manager import main,clean
try:main()
except Exception as e:print('ERROR\t'+clean(e));sys.exit(1)
