"""Read RT_MANIFEST leaves of a PE file without loading or executing it."""
import argparse, hashlib, json, struct
import xml.etree.ElementTree as ET
from pathlib import Path

def inspect(data):
    def u16(n): return struct.unpack_from('<H',data,n)[0]
    def u32(n): return struct.unpack_from('<I',data,n)[0]
    assert data[:2]==b'MZ'; pe=u32(0x3c); assert data[pe:pe+4]==b'PE\0\0'
    opt=pe+24; magic=u16(opt); assert magic in (0x10b,0x20b)
    directory=opt+(112 if magic==0x20b else 96)
    resource=u32(directory+16); size=u32(directory+20)
    sections=[]
    for i in range(u16(pe+6)):
        off=opt+u16(pe+20)+i*40
        sections.append((u32(off+12),max(u32(off+8),u32(off+16)),u32(off+20)))
    def fileoff(rva):
        for start,length,raw in sections:
            if start<=rva<start+length:return raw+rva-start
        raise AssertionError('unmapped RVA')
    leaves=[]
    if resource and size:
        base=fileoff(resource)
        def entries(rel):
            at=base+rel
            return [(u32(at+16+8*i),u32(at+20+8*i)) for i in range(u16(at+12)+u16(at+14))]
        def walk(rel,path):
            for name,target in entries(rel):
                if target&0x80000000:walk(target&0x7fffffff,path+[name])
                else:
                    at=base+target; start=fileoff(u32(at)); length=u32(at+4)
                    raw=data[start:start+length]; xml=ET.fromstring(raw)
                    levels=[e.attrib for e in xml.iter() if e.tag.split('}')[-1]=='requestedExecutionLevel']
                    leaves.append(dict(resource=path+[name],sha256=hashlib.sha256(raw).hexdigest(),levels=levels,xml=raw.decode('utf-8-sig')))
        for kind,target in entries(0):
            if kind==24:
                assert target&0x80000000; walk(target&0x7fffffff,[24])
    return dict(manifests=leaves,levels=[v for leaf in leaves for v in leaf['levels']])

def invoker(result):
    # Absence is recorded as absence, not an invented explicit manifest node.
    # Ordinary CreateProcess inherits its Medium parent; ShellExecute runas is
    # separately restricted to make. C2 confirms normal app launch on Win11.
    assert all(x.get('level')=='asInvoker' and x.get('uiAccess','false')=='false' for x in result['levels'])
    for m in result['manifests']:
        xml=ET.fromstring(m['xml'])
        assert not any(e.tag.split('}')[-1]=='autoElevate' and (e.text or '').strip().lower()=='true' for e in xml.iter())
    return 'explicit-asInvoker' if result['levels'] else 'no-elevation-request; default-invoker'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary',type=Path);a=p.parse_args()
    b=a.binary.read_bytes();print(json.dumps(dict(name=a.binary.name,sha256=hashlib.sha256(b).hexdigest(),**inspect(b)),indent=2))
