"""Independently authored INGEST-1 structural arithmetic; no Product import."""
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
import functools, hashlib, json, re, struct, unicodedata

RATE=44100
GAP=88200
SEED=0x6D2B79F5
RATES=(7350,8000,11025,12000,16000,22050,24000,32000,44100,48000,64000,88200,96000,176400,192000)
TOP=('schema','contract','tool_version','build_profile','libraries','resampler_profile','meter_profile','dither_profile','target_seconds','capacity_frames','total_frames','wav_sha256','folders','sources','gaps')
SOURCE=('logical_path','source_sha256','container','codec','codec_profile','input_rate','input_channels','raw_frames','trim_head','trim_tail','trim_evidence','effective_frames','output_frames','start_frame','input_lufs','input_dbtp','output_lufs','output_dbtp','target_gain_db','applied_gain_db','peak_limited','loudness_status','loudness_reason','gapless_status')

def digest(data): return hashlib.sha256(data).hexdigest()
def output_frames(n,r):
    assert isinstance(n,int) and n>=0 and r in RATES
    return (n*RATE+r//2)//r
def admitted_output_frames(name,n,r):
    """ADR-178 source admission only; not a complete ingest preflight."""
    if n<=0:raise ValueError(name+': zero effective decoded frames')
    count=output_frames(n,r)
    if count==0:
        raise ValueError(name+': too short to produce one 44.1kHz frame')
    return count
def overage(total,seconds):
    assert seconds>0
    e=max(0,total-seconds*RATE);s=(e+RATE-1)//RATE
    return e,'%02d:%02d'%divmod(s,60)
def fixed(value):
    if value is None: return None
    q=Decimal(str(value)).quantize(Decimal('.000001'),rounding=ROUND_HALF_EVEN)
    if q==0:q=abs(q)
    return format(q,'.6f')
def canonical(obj):
    return (json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
def draw(s):
    s=(s ^ ((s<<13)&0xffffffff))&0xffffffff
    s=(s ^ (s>>17))&0xffffffff
    s=(s ^ ((s<<5)&0xffffffff))&0xffffffff
    return s,(s+0.5)/4294967296
def quantize(rows,mono=False,silence=False,seed=SEED):
    out=bytearray();s=seed
    for row in rows:
        if silence:
            out.extend(bytes(4));continue
        vals=[]
        for x in row[:1] if mono else row:
            s,a=draw(s);first=s;s,b=draw(s)
            # Exact real formula on the observed binary floating input.
            numerator,denominator=float(x).as_integer_ratio()
            value=(numerator<<47)+(first-s)*denominator
            divisor=denominator<<32;q,remainder=divmod(value,divisor)
            if 2*remainder>divisor or 2*remainder==divisor and q&1:q+=1
            if not -32768<=q<=32767:raise OverflowError('quantizer overflow')
            vals.append(q)
        if mono: vals*=2
        if len(vals)!=2:raise ValueError('stereo output required')
        out.extend(struct.pack('<hh',*vals))
    return bytes(out)
def wav(pcm):
    assert len(pcm)%4==0 and len(pcm)+36<=0xffffffff
    return struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',len(pcm)+36,b'WAVE',b'fmt ',16,1,2,RATE,176400,4,16,b'data',len(pcm))+pcm
def pcm_from_wav(data):
    assert len(data)>=44 and data[:44]==wav(data[44:])[:44],'noncanonical WAV'
    return data[44:]

def name_key(name):
    n=unicodedata.normalize('NFC',name)
    tokens=[]
    for t in re.findall('[0-9]+|[^0-9]+',n):
        if t[0] in '0123456789':tokens.append((0,len(t.lstrip('0')),t.lstrip('0')))
        else:tokens.append((1,''.join(chr(ord(c)+32) if 'A'<=c<='Z' else c for c in t)))
    return tokens,n,name.encode('utf-8')
def natural(names):return sorted(names,key=name_key)
def logical_names(folders):
    result=[]
    for ordinal,names in enumerate(folders):
        ordered=natural(names)
        norm=[unicodedata.normalize('NFC',n) for n in ordered]
        if len(set(norm))!=len(norm):raise ValueError('normalized path collision')
        result.extend(str(ordinal)+'/'+n for n in norm)
    return result

def neutral_metadata(value,in_libraries=False):
    forbidden={'timestamp','created_at','generated_at','recorded_at','build_date','date','time','cpu','os','platform','architecture','hostname','cwd','uuid','random_id','locale'}
    if isinstance(value,dict):
        for key,item in value.items():
            assert in_libraries or key.lower() not in forbidden,'volatile identity key '+key
            neutral_metadata(item,in_libraries or key=='libraries')
    elif isinstance(value,list):
        for item in value:neutral_metadata(item,in_libraries)
    elif isinstance(value,str):
        assert not value.startswith(('/','\\\\')) and not re.match('^[A-Za-z]:[\\\\/]',value),'absolute path in manifest'

def check_manifest(raw,pcm,source_facts,folders,target_seconds,wav_sha256=None):
    m=json.loads(raw)
    neutral_metadata(m)
    assert canonical(m)==raw,'noncanonical JSON'
    assert set(TOP)<=m.keys(),'missing top-level fields'
    assert m['schema']==1 and m['contract']=='INGEST-1'
    assert m['target_seconds']==target_seconds and m['capacity_frames']==target_seconds*RATE
    assert all(type(m[k]) is int for k in ('schema','target_seconds','capacity_frames','total_frames'))
    assert isinstance(m['tool_version'],str) and m['tool_version']
    for name in ('build_profile','resampler_profile','meter_profile','dither_profile'):
        assert isinstance(m[name],str) and m[name],'missing profile'
    assert m['libraries'],'no pinned library census'
    assert m['wav_sha256']==(digest(wav(pcm)) if wav_sha256 is None else wav_sha256)
    assert len(m['sources'])==len(source_facts),'source omitted/added'
    assert m['folders']==[{'ordinal':i,'source_count':len(f)} for i,f in enumerate(folders)]
    assert all(type(folder[k])is int for folder in m['folders'] for k in ('ordinal','source_count')),'folder counts must be integers'
    assert all(type(gap[k])is int for gap in m['gaps'] for k in ('start_frame','frames')),'gap counts must be integers'
    assert [s['logical_path'] for s in m['sources']]==logical_names(folders),'order/path drift'
    at=0;gaps=[]
    for idx,(s,f) in enumerate(zip(m['sources'],source_facts)):
        assert set(SOURCE)<=s.keys(),'missing source fields'
        for field in ('source_sha256','input_rate','input_channels','raw_frames','trim_head','trim_tail','trim_evidence','effective_frames'):
            assert s[field]==f[field],field+' disagrees with fixture'
        assert s['output_frames']==admitted_output_frames(s['logical_path'],f['effective_frames'],f['input_rate'])
        assert s['raw_frames']-s['trim_head']-s['trim_tail']==s['effective_frames']
        assert s['trim_evidence'] in ('none','xing_lame','bmff_edit')
        assert s['trim_evidence']!='none' or s['trim_head']==s['trim_tail']==0
        for key in ('container','codec','codec_profile'):
            assert isinstance(s[key],str) and s[key],key+' empty'
        for key in ('input_rate','input_channels','raw_frames','trim_head','trim_tail','effective_frames','output_frames','start_frame'):
            assert type(s[key]) is int and s[key]>=0,key+' not nonnegative integer'
        assert s['start_frame']==at
        assert s['gapless_status'] in ('gapless_known','gapless_unknown')
        if not f.get('lossy'):assert s['gapless_status']=='gapless_known' and s['trim_evidence']=='none' and s['trim_head']==s['trim_tail']==0,'lossless status'
        if f.get('lossy'):assert s['gapless_status']==('gapless_known' if s['trim_evidence']!='none' else 'gapless_unknown')
        assert s['loudness_status'] in ('measured','unmeasurable','digital_silence')
        assert s['loudness_reason'] in (None,'too_short','gated_out')
        assert isinstance(s['peak_limited'],bool)
        for field in ('input_lufs','input_dbtp','output_lufs','output_dbtp','target_gain_db','applied_gain_db'):
            v=s[field]
            assert v is None or isinstance(v,str) and re.fullmatch('-?(0|[1-9][0-9]*)[.][0-9]{6}',v) and v!='-0.000000',field+' format'
        at+=s['output_frames']
        if idx+1<len(source_facts) and m['sources'][idx+1]['logical_path'].split('/')[0]!=s['logical_path'].split('/')[0]:
            gaps.append({'start_frame':at,'frames':GAP})
            assert pcm[at*4:(at+GAP)*4]==bytes(GAP*4),'noisy/wrong folder gap'
            at+=GAP
    assert m['gaps']==gaps and m['total_frames']==at and len(pcm)==at*4
    assert at<=target_seconds*RATE and at*4+36<=0xffffffff
    return m
