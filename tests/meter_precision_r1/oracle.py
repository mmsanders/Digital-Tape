"""Independent integer-coordinate and precision-binding controls, no meter."""
import math,struct
def support(n0):return (n0-255,n0+256)
def phase(z):return divmod(z,256)
def global_sample(start,local):return start+local
def streamed_sample(lo,local):return lo-258+local
def ieee(raw,kind):
 assert kind in ('f32','f64')
 assert len(raw)==(8 if kind=='f32' else 16)
 b=bytes.fromhex(raw);v=struct.unpack('<f' if kind=='f32' else '<d',b)[0]
 assert math.isfinite(v)
 return v
def bind_gain(raw,kind,expected_raw,expected_kind):
 ieee(raw,kind);ieee(expected_raw,expected_kind)
 return kind==expected_kind and raw==expected_raw
def coordinates(row):
 n,q=phase(row['signed_phase'])
 assert (n,q)==(row['n0'],row['q'])
 assert list(support(n))==row['support']
 assert global_sample(row['source_start'],row['source_local'])==row['global_sample']
 assert streamed_sample(row['block_lo'],row['buffer_local'])==row['global_sample']
 return True
