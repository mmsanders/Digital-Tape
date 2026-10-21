import copy,struct
from oracle import support,phase,coordinates,bind_gain,ieee
assert phase(-1)==(-1,255) and phase(-257)==(-2,255)
assert support(0)==(-255,256)
good=dict(signed_phase=-1,n0=-1,q=255,support=[-256,255],source_start=256,source_local=1,global_sample=257,block_lo=0,buffer_local=515)
assert coordinates(good)
for key,value in [('q',0),('support',[-255,256]),('global_sample',1),('buffer_local',257),('block_lo',1)]:
 bad=copy.deepcopy(good);bad[key]=value
 try:coordinates(bad)
 except AssertionError:pass
 else:raise AssertionError('mutant admitted: '+key)
a=struct.pack('<d',1.0).hex();b=struct.pack('<d',1.0+1e-10).hex()
assert format(ieee(a,'f64'),'.6f')==format(ieee(b,'f64'),'.6f')
assert not bind_gain(a,'f64',b,'f64') and bind_gain(a,'f64',a,'f64')
assert not bind_gain(struct.pack('<f',1.0).hex(),'f32',a,'f64')
print('PASS: signed phase/support/global/block and rounded-gain controls; no meter/driver execution')
