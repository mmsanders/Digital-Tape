"""Contract-admissible IEEE-f64 neighbours. No decoder/library implementation import."""
import math,struct
from pathlib import Path

def wav64(p,value):
 assert math.isfinite(value)
 data=struct.pack('<d',value)
 p.write_bytes(struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',36+len(data),b'WAVE',b'fmt ',16,3,1,44100,352800,8,64,b'data',len(data))+data)
def generate(root):
 rows=[]
 for name,value,expected in [('silence64',0.0,0),('quiet64',1e-30,0),('tiny64',1e-300,2)]:
  d=root/name;d.mkdir(parents=True,exist_ok=True);wav64(d/'x.wav',value);rows.append(dict(name=name,folder=str(d),value=value,expected_exit=expected))
 return rows
