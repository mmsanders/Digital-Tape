"""Cost admission only; original state/model predicates are unchanged."""
import math
CPU_CAP=7200;BYTE_CAP=2*1024**3
def reserve(projections):
 assert type(projections) is int and 0<=projections<=2
 return 120+6*projections,(16+8*projections)*1024**2
def admit(cpu,storage,next_cpu,next_storage,finish_cpu=0,finish_storage=0):
 v=(cpu,storage,next_cpu,next_storage,finish_cpu,finish_storage)
 return all(type(n) in (int,float) and math.isfinite(n) and n>=0 for n in v) and cpu+next_cpu+finish_cpu<=CPU_CAP and storage+next_storage+finish_storage<=BYTE_CAP
