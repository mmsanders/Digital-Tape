"""Literal independent frozen §§6.2/6.3/8 model; no Product state or source."""
import struct
import bisect
import fixtures as fx

class PCM:
    def __init__(self,f,side='A',resume=0):
        self.f=f;self.side=side;self.rate=0;self.end=False;self.start=False
        self.pos=min(resume,fx.length(f,side))<<32
        self.replacement=None
        self.timeline_override=None
        self._map_side=None
    def contiguous_pcm(self,first,n):
        # Independent oracle acceleration only. At grid-aligned +1x the frozen
        # interpolation fraction is zero, so output is exactly frame a.
        if self._map_side!=self.side:
            self._starts=[];self._physical=[];offset=0
            for chunk,start,count in self.f['sides'][self.side]:
                self._starts.append(offset);self._physical.append((chunk*fx.CF+start,count));offset+=count
            self._map_side=self.side
        chunks=[]
        while n:
            k=bisect.bisect_right(self._starts,first)-1;physical,count=self._physical[k]
            into=first-self._starts[k];take=min(n,count-into)
            chunks.append(b''.join(fx.coordinate(physical+into+i,self.f['seed']) for i in range(take)))
            first+=take;n-=take
        return b''.join(chunks)
    def seek(self,n): self.pos=min(n,self.total)<<32;self.end=self.start=False
    def set_rate(self,r): self.rate=r;self.end=self.start=False
    def set_side(self,s): self.side=s;self.pos=0;self.end=self.start=False
    @property
    def total(self):
        return len(self.timeline_override)//4 if self.timeline_override is not None and self.side=='B' else fx.length(self.f,self.side)
    def sample(self,i):
        if self.timeline_override is not None and self.side=='B':return self.timeline_override[i*4:(i+1)*4]
        if self.replacement and self.side=='B':
            start,raw=self.replacement
            if start<=i<start+len(raw)//4:return raw[(i-start)*4:(i-start+1)*4]
        return fx.frame(self.f,self.side,i)
    def render(self,n):
        out=bytearray();m=self.total<<32;s=self.rate*65536
        if not self.total:self.end=True;return bytes(out)
        if not s:return bytes(out)
        if self.rate==65536 and not (self.pos&0xffffffff) and self.timeline_override is None and self.replacement is None:
            first=self.pos>>32;take=min(n,max(0,self.total-first))
            raw=self.contiguous_pcm(first,take)
            if take:self.start=False;self.pos+=take<<32
            if (take or n) and self.pos>=m:self.end=True
            return raw
        if s<0 and self.pos>=m:self.pos=(self.total-1)<<32
        for _ in range(n):
            if s>0 and self.pos>=m:self.end=True;break
            if s<0 and self.start:break
            i=self.pos>>32;f=self.pos&0xffffffff
            a=struct.unpack('<hh',self.sample(i));b=struct.unpack('<hh',self.sample(min(i+1,self.total-1)))
            out+=struct.pack('<hh',*(a[k]+((b[k]-a[k])*f)//(1<<32) for k in (0,1)))
            if s>0:
                self.start=False
                if self.pos>=m or s>=m-self.pos:self.pos=m;self.end=True
                else:self.pos+=s
            else:
                self.end=False
                if self.pos==0:self.start=True
                elif self.pos<=-s:self.pos=0
                else:self.pos+=s
        return bytes(out)
