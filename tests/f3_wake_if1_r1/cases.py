"""F3-IF/1 public wake-sim inputs and explicit independent expected outputs."""
import copy
ID='a'*32

def scenario():
 return dict(cpu_hz=600000000,t0_cycles=1000,t0_ms=100,inject_us=0,trigger='button',mount=0,warm=1,position=44100,id=ID,blocks=[dict(cycles=59401000,ms=199,engine_frames=128,nonzero=True)])

def cases():
 out=[]
 def add(name,edit=lambda s:None,**want):
  s=scenario();edit(s);out.append(dict(name=name,scenario=s,expected=dict(trigger=s['trigger'],warm=str(s['warm']),mount=str(s['mount']),position=str(s['position']),inject_us=str(s['inject_us']),id=ID,**want)))
 add('warm-button-99ms',status='ok',elapsed_us='99000',cycles='59400000',cpu_hz='600000000',millis='99',engine_us='99000')
 add('serial-trigger-stays-diagnostic',lambda s:s.update(trigger='serial'),status='ok',elapsed_us='99000')
 add('cold-fallback-remains-observed',lambda s:s.update(warm=0),status='ok',elapsed_us='99000')
 def blocks(s):s['blocks']=[dict(cycles=6001000,ms=110,engine_frames=0,nonzero=False),dict(cycles=12001000,ms=120,engine_frames=128,nonzero=False),dict(cycles=58801600,ms=198,engine_frames=128,nonzero=True),dict(cycles=60001000,ms=200,engine_frames=128,nonzero=True)]
 add('first-engine-block-is-not-first-nonsilent',blocks,status='ok',elapsed_us='98001',cycles='58800600',millis='98',engine_us='20000')
 for label,cycles,ms,expected in [('one-cycle',1,0,1),('exact-microsecond',600,0,1),('ceil-not-floor',601,0,2),('100ms-target-equality',60000000,100,100000),('120ms-exact-twenty-percent',72000000,120,120000),('120001us-over-twenty-percent',72000600,120,120001)]:
  add(label,lambda s,cycles=cycles,ms=ms:s.update(blocks=[dict(cycles=s['t0_cycles']+cycles,ms=s['t0_ms']+ms,engine_frames=128,nonzero=True)]),status='ok',elapsed_us=str(expected),cycles=str(cycles),millis=str(ms),engine_us=str(expected))
 for hz in (24000000,150000000,600000000):
  add('clock-'+str(hz),lambda s,hz=hz:s.update(cpu_hz=hz,blocks=[dict(cycles=s['t0_cycles']+hz//1000,ms=s['t0_ms']+1,engine_frames=128,nonzero=True)]),status='ok',elapsed_us='1000',cycles=str(hz//1000),cpu_hz=str(hz),millis='1')
 def wrap(s):s.update(t0_cycles=4294967200,blocks=[dict(cycles=(4294967200+600000)%2**32,ms=101,engine_frames=128,nonzero=True)])
 add('short-counter-rollover-modulo-not-negative',wrap,status='ok',elapsed_us='1000',cycles='600000',millis='1',engine_us='1000')
 def mswrap(s):s.update(t0_ms=4294967295,blocks=[dict(cycles=601000,ms=0,engine_frames=128,nonzero=True)])
 add('millis-short-rollover-modulo',mswrap,status='ok',elapsed_us='1000',millis='1')
 for elapsed in (149999,150000,150001):
  add('control-observed-'+str(elapsed),lambda s,elapsed=elapsed:s.update(inject_us=150000,blocks=[dict(cycles=1000+600*elapsed,ms=100+elapsed//1000,engine_frames=128,nonzero=True)]),status='ok',elapsed_us=str(elapsed),cycles=str(600*elapsed),engine_us=str(elapsed))
 add('control-ceil-149999-point5',lambda s:s.update(inject_us=150000,blocks=[dict(cycles=89999700+1000,ms=250,engine_frames=128,nonzero=True)]),status='ok',elapsed_us='150000',cycles='89999700')
 add('no-nonsilent-block-times-out',lambda s:s.update(blocks=[dict(cycles=1200001000,ms=2100,engine_frames=128,nonzero=False)]),status='timeout')
 add('fault-wrap-cannot-report-short-ok',lambda s:s.update(blocks=[dict(cycles=1000,ms=7100,engine_frames=128,nonzero=True)]),status='wrap',elapsed_us='-',cycles='-')
 add('mount-failed-is-not-ok',lambda s:s.update(mount=-1,blocks=[]),status='mount_failed')
 return out
