"""Actual sparse-image outcome/control. Linux CI only, no physical target."""
import argparse, hashlib, json, subprocess, tempfile, wave
from pathlib import Path

def run(product):
    product=product.resolve(); baseline=product/'build/host/tapectl'
    observations=[]
    def invoke(binary,*args):
        p=subprocess.run([str(binary),*map(str,args)],capture_output=True)
        observations.append(dict(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),argv=list(map(str,args)),exit=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode()))
        return p
    with tempfile.TemporaryDirectory(prefix='c1-a6-') as tmp:
        root=Path(tmp); image=root/'large.img'; wav=root/'source.wav'
        with wave.open(str(wav),'wb') as w:
            w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\x01\x00\x02\x00'*44100)
        p=invoke(baseline,'provision',image,'--image-bytes',64_000_000_000,'--label','C1 A6','--length-s',60,'--uuid','0123456789abcdef0123456789abcdef','--epoch',315532800);assert p.returncode==0,p.stderr
        assert invoke(baseline,'load',image,wav).returncode==0
        assert invoke(baseline,'verify',image).returncode==0
        # Verify checks BOTH superblocks. A narrowed read loses the final-sector
        # mirror and must fail that same pristine-image OK assertion.
        with image.open('rb') as f:
            f.seek(64_000_000_000-512); mirror=f.read(512)
            f.seek((64_000_000_000-512)&0xffffffff); wrapped=f.read(512)
        assert mirror[:8]==b'TAPEFS\0\x01' and wrapped!=mirror
        assert invoke(baseline,'verify',image).returncode==0
        for side in ('A','B'):
            out=root/(side+'.wav');assert invoke(baseline,'dump',image,'--side',side,'-o',out).returncode==0
            assert out.read_bytes()==wav.read_bytes()
        # Compile the same covered port with only the read offset narrowed to uint32.
        port=product/'host/port/hport_posix.c'; original=port.read_bytes()
        needle=b'pread(p->fd, b, len, (off_t)off)';assert original.count(needle)==1
        mutant=product/'build/c1-mutant/tapectl'
        try:
            port.write_bytes(original.replace(needle,b'pread(p->fd, b, len, (off_t)(uint32_t)off)'))
            subprocess.run(['make','-C',str(product/'host'),'BUILD=../build/c1-mutant','../build/c1-mutant/tapectl'],check=True)
        finally:port.write_bytes(original)
        bad=invoke(mutant,'verify',image)
        assert bad.returncode!=0 and b'OK\n' not in bad.stdout, '32-bit read-offset mutant survived'
    return dict(scope='private sparse 64GB image and real narrowed-read negative control',mirror_offset=64_000_000_000-512,control='killed',observations=observations)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('product',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.write_text(json.dumps(run(a.product),indent=2)+'\n')
