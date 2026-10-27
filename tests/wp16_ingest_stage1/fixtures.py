"""Generate CC0 source fixtures; persist exact hashes/metadata for candidate runs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import numpy as np
import formats
import model

HERE=Path(__file__).resolve().parent


def signal(rate,n,channels=2):
    t=np.arange(n)/rate
    # Non-periodic envelope and unequal channels make trim/order/mono faults causal.
    envelope=.4+.2*np.sin(2*np.pi*2.37*t)
    left=envelope*(.18*np.sin(2*np.pi*min(997,rate*.12)*t)+.07*np.sin(2*np.pi*min(2333,rate*.21)*t))
    right=.65*envelope*(.16*np.cos(2*np.pi*min(733,rate*.09)*t)+.06*np.sin(2*np.pi*min(1667,rate*.19)*t))
    return np.rint(np.stack((left,right),axis=1)[:,:channels]*2**24)/2**24


def decode(path,channels,manual=False,ignore_edit=False):
    args=['ffmpeg','-v','error','-nostdin','-xerror']
    if manual:args+=['-flags2','+skip_manual']
    if ignore_edit:args+=['-ignore_editlist','1']
    p=subprocess.run(args+['-i',str(path),'-map','0:a:0','-f','f64le','-acodec','pcm_f64le','-'],capture_output=True)
    if p.returncode:raise ValueError(p.stderr.decode(errors='replace'))
    return np.frombuffer(p.stdout,dtype='<f8').reshape(-1,channels)


def build(root,seed=None):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);assets=root/'assets';assets.mkdir(exist_ok=True)
    records={};encodings=[]
    seeds={}
    if seed:
        import tarfile
        with tarfile.open(seed) as t:
            t.extractall(root,filter='data')
        seeds=json.loads((root/'SEED-SOURCES.json').read_text(encoding='utf-8'))
        encodings=json.loads((root/'ENCODER.json').read_text(encoding='utf-8'))['runs']
    def add(name,data,rate,channels,n,container,codec,bits=None,**extra):
        path=assets/name;path.write_bytes(data)
        rec=dict(path='assets/'+name,sha256=model.digest(data),bytes=len(data),input_rate=rate,input_channels=channels,
                 raw_frames=n,trim_head=0,trim_tail=0,effective_frames=n,trim_evidence='none',
                 container=container,codec=codec,codec_profile=codec,licence='CC0-1.0',generator='fixtures.py',**extra)
        if bits is not None:rec['bits']=bits
        if name.startswith('sowt-') and bits!=16:rec['refuse']=True;rec['reason']='AIFC sowt sampleSize must be16'
        records[name]=rec;return path
    # Full issued lossless rate/channel combinations; bit depths cross every rate,
    # FLAC exercises every admitted integer precision rather than only multiples8.
    for rate in model.RATES:
        for channels in (1,2):
            x=signal(rate,256,channels)
            for bits in (8,16,24,32):
                name='wave-%d-%d-%d.wav'%(rate,channels,bits);add(name,formats.wave(x,rate,bits),rate,channels,256,'wave','pcm',bits)
            for bits in (32,64):
                name='float-%d-%d-%d.wav'%(rate,channels,bits);add(name,formats.wave(x,rate,bits,True),rate,channels,256,'wave','float',bits)
            for bits,floating in [(8,False),(16,False),(24,False),(32,False),(32,True),(64,True)]:
                name=('ext-float' if floating else 'ext')+'-%d-%d-%d.wav'%(rate,channels,bits);add(name,formats.wave(x,rate,bits,floating,True),rate,channels,256,'wave','float' if floating else 'pcm',bits)
            for compression in (None,b'NONE',b'sowt'):
                for bits in (8,16,24,32):
                    label='aiff' if compression is None else compression.decode()
                    name='%s-%d-%d-%d.aif'%(label,rate,channels,bits)
                    add(name,formats.aiff(x,rate,bits,compression),rate,channels,256,'aiff' if compression is None else 'aifc','pcm',bits)
            for bits in range(8,33):
                name='flac-%d-%d-%d.flac'%(rate,channels,bits);add(name,formats.flac(x,rate,bits),rate,channels,256,'flac','flac',bits)
    for ch in (1,2):
        x=signal(44100,256,ch)
        for valid in (16,24):
            q=np.rint(x*2**(valid-1))/2**(valid-1)
            data=bytearray(formats.wave(q,44100,32,False,True));struct.pack_into('<H',data,38,valid)
            add('ext-valid%d-in32-%d.wav'%(valid,ch),bytes(data),44100,ch,256,'wave','pcm',valid,container_bits=32)
    x=signal(44100,257,1)
    add('odd-pcm8.wav',formats.wave(x,44100,8),44100,1,257,'wave','pcm',8)
    add('odd-pcm8.aif',formats.aiff(x,44100,8),44100,1,257,'aiff','pcm',8)
    def encode(name,rate,channels,args,container,codec,trim):
        if name in seeds:
            data=(root/seeds[name]['path']).read_bytes()
            assert model.digest(data)==seeds[name]['sha256']
            records[name]=seeds[name];return
        x=signal(rate,rate+137,channels);source=root/'encoder-source.wav';source.write_bytes(formats.wave(x,rate,32,True))
        target=assets/name
        command=['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-map_metadata','-1',*args,str(target)]
        p=subprocess.run(command,capture_output=True)
        if p.returncode:raise ValueError((command,p.stderr.decode(errors='replace')))
        data=target.read_bytes();facts=trim(data) if trim else None
        raw=decode(target,channels,manual=True,ignore_edit=container=='bmff')
        n=len(raw)
        rec=dict(path='assets/'+name,sha256=model.digest(data),bytes=len(data),input_rate=rate,input_channels=channels,
                 raw_frames=n,trim_head=0,trim_tail=0,effective_frames=n,trim_evidence='none',container=container,
                 codec=codec,codec_profile=codec,licence='CC0-1.0',generator='fixtures.py/FFmpeg',original_frames=len(x),lossy=True)
        if facts:
            rec.update(facts);assert facts['raw_frames']==n,(name,facts,n)
            # Encoder-added presentation padding is not silently removed. The
            # declared validated interval, rather than the original source's
            # length, is the exact Product expectation (some12k LAME outputs
            # declare a few additional presentation samples).
            rec['presentation_frames_delta']=facts['effective_frames']-len(x)
        records[name]=rec
        encodings.append({'asset':name,'argv':[v.replace(str(root),'{ROOT}') for v in command],'exit':p.returncode,'stderr':p.stderr.decode(),'raw_decode_frames':n,
                          'default_decode_frames':len(decode(target,channels))})
    mp3rates=(8000,11025,12000,16000,22050,24000,32000,44100,48000)
    for rate in mp3rates:
        for ch in (1,2):
            for mode,opts in [('cbr',['-b:a','64k']),('vbr',['-q:a','3'])]:
                encode('mp3-%d-%d-%s.mp3'%(rate,ch,mode),rate,ch,['-c:a','libmp3lame',*opts,'-write_xing','1'],'mpeg','mp3',formats.mp3_interval)
    # AAC-LC supports the issued MPEG4 sampling frequency table (7350 included;
    #64k/88.2k/96k included;176.4k/192k have no AAC-LC ADTS frequency index).
    for rate in model.RATES[:13]:
        for ch in (1,2):
            encode('aac-%d-%d.m4a'%(rate,ch),rate,ch,['-c:a','aac','-profile:a','aac_low','-b:a','96k','-movie_timescale',str(rate),'-use_editlist','1'],'bmff','aac_lc',formats.bmff_interval)
            encode('adts-%d-%d.aac'%(rate,ch),rate,ch,['-c:a','aac','-profile:a','aac_low','-b:a','96k','-f','adts'],'adts','aac_lc',None)
    first,_=model.draw(model.SEED);second,_=model.draw(first)
    quantized_zero=np.array([[ -(first-second)/(2**47) ]])
    # Calibrated/audio-behavior sources retained separately from tiny matrix files.
    for name,x,rate in [
        ('ordinary.wav',signal(44100,88200),44100),
        ('silence.wav',np.zeros((8820,2)),44100),
        ('short.wav',signal(44100,17),44100),
        ('one-frame-quant-zero.wav',quantized_zero,44100),
        ('gated.wav',signal(44100,44100)*1e-5,44100),
        ('crest.wav',np.concatenate((signal(44100,44100)*.02,np.array([[.8,-.8]]),signal(44100,44100)*.02)),44100),
        ('dither-stereo.wav',np.array([[0,.25],[.125,-.125],[-.25,0],[.0625,.1875]]*16),44100),
        ('dither-mono.wav',np.array([[0],[.125],[-.25],[.0625]]*16),44100),
        ('zero-192-n1.wav',np.zeros((1,1)),192000),('zero-192-n2.wav',np.zeros((2,1)),192000),
        ('positive-192-n3.wav',np.zeros((3,1)),192000),('tie-88200.wav',np.zeros((1,1)),88200),
        ('exact-one-second.wav',np.zeros((44100,2)),44100),('one-frame-over.wav',np.zeros((44101,2)),44100),
    ]:add(name,formats.wave(x,rate,64,True),rate,x.shape[1],len(x),'wave','float',64,family='behavior')
    # Explicit steady-state SRC and endpoint probes. Signals on dyadic grid
    # make authoring replay independent of last-bit trigonometric libm drift.
    for rate in model.RATES:
        for frequency in sorted(set((20,997,min(18000,.4*rate)))):
            t=np.arange(rate*2)/rate
            x=np.rint((.25*np.sin(2*np.pi*frequency*t))*2**24)/2**24
            x=np.repeat(x[:,None],2,axis=1)
            name='src-%d-%s.wav'%(rate,str(frequency).replace('.','p'))
            add(name,formats.wave(x,rate,64,True),rate,2,len(x),'wave','float',64,family='src-quality',frequency=frequency,amplitude=.25,window_output_frames=4410)
        if rate>44100:
            for frequency in (22050,23000,rate*.47):
                if frequency>=rate/2:continue
                x=.25*np.sin(2*np.pi*frequency*np.arange(rate*2)/rate)
                x=np.repeat((np.rint(x*2**24)/2**24)[:,None],2,axis=1)
                name='alias-%d-%s.wav'%(rate,str(frequency).replace('.','p'))
                add(name,formats.wave(x,rate,64,True),rate,2,len(x),'wave','float',64,family='src-quality',frequency=frequency,amplitude=.25,window_output_frames=4410)
        for at in (0,256):
            x=np.zeros((257,2));x[at]=[.25,-.125]
            name='endpoint-%d-%d.wav'%(rate,at)
            add(name,formats.wave(x,rate,64,True),rate,2,len(x),'wave','float',64,family='endpoint')
    for name,sign in [('join-plus.wav',1),('join-minus.wav',-1)]:
        x=np.full((64,2),sign*.7)
        add(name,formats.wave(x,44100,64,True),44100,2,64,'wave','float',64,family='unsafe-join')
    for channels in (1,2):
        for protection in (False,True):
            name='minimal-adts-%d-%s.aac'%(channels,'crc' if protection else 'plain')
            value=formats.adts_silence(protection,channels=channels)
            add(name,value,44100,channels,4096,'adts','aac_lc',lossy=True,crc_protected=protection,family='adts-crc')
    import qualification
    for label,x,metric,expected in qualification.vectors():
        x=np.rint(x*2**24)/2**24
        add('qual-'+label+'.wav',formats.wave(x,44100,64,True),44100,2,len(x),'wave','float',64,family='qualification',qualification_metric=metric,qualification_expected=expected)
    # Strict byte-detected refusals with recognized family/type declarations.
    sample=signal(44100,256);good=formats.wave(sample,44100)
    negatives={
      'empty.wav':formats.wave(np.zeros((0,2)),44100),
      'nan.wav':formats.wave(np.array([[float('nan'),0]]),44100,64,True),
      'infinity.wav':formats.wave(np.array([[float('inf'),0]]),44100,64,True),
      'three-channels.wav':formats.wave(np.zeros((32,3)),44100),
      'unsupported-rate.wav':formats.wave(sample,12345),
      'ambiguous-mask.wav':formats.wave(sample,44100,16,False,True,mask=4),
      'truncated.wav':good[:-7], 'junk.bin':b'not audio\n',
      'protected.m4a':(assets/'aac-44100-2.m4a').read_bytes().replace(b'mp4a',b'enca',1),
      'rf64.wav':b'RF64'+b'\xff'*4+b'WAVE'+formats.chunk(b'ds64',struct.pack('<QQQI',len(good)+28,len(good)-44,256,0))+good[12:],
      'adif.aac':b'ADIF'+bytes(32),
    }
    for channels in (1,2):
        crcfile=bytearray(formats.adts_silence(True,channels=channels));crcfile[8]^=1
        negatives['adts-crc-mismatch-%d.aac'%channels]=bytes(crcfile)
    multiblock=bytearray(formats.adts_silence(False));multiblock[6]|=1
    negatives['adts-multiblock.aac']=bytes(multiblock)
    for name,data in negatives.items():
        path=assets/name;path.write_bytes(data);records[name]=dict(path='assets/'+name,sha256=model.digest(data),bytes=len(data),licence='CC0-1.0',generator='fixtures.py',refuse=True)
    # Mutate a valid edit count/duration, never a random decoder-error stand-in.
    data=(assets/'aac-44100-2.m4a').read_bytes()
    a,b=next((a,b) for tag,a,b,_ in formats.descendants(data) if tag==b'elst')
    bad=bytearray(data);struct.pack_into('>i',bad,a+12,-1)
    (assets/'edit-negative.m4a').write_bytes(bad)
    records['edit-negative.m4a']=dict(path='assets/edit-negative.m4a',sha256=model.digest(bad),bytes=len(bad),licence='CC0-1.0',generator='fixtures.py',refuse=True)
    # Missing declarations are positive untrimmed cases, not guessed silence trim.
    mp=(assets/'mp3-44100-2-vbr.mp3').read_bytes()
    start=10+sum((mp[6+i]&127)<<(7*(3-i)) for i in range(4)) if mp[:3]==b'ID3' else 0
    h=int.from_bytes(mp[start:start+4],'big');kbps=[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320][(h>>12)&15]
    frame_bytes=144000*kbps//44100+((h>>9)&1)
    clean=mp[start+frame_bytes:]
    # Remove the entire metadata-only frame, not merely its Xing signature.
    add('legacy.mp3',clean,44100,2,formats.mp3_interval(clean)['raw_frames'],'mpeg','mp3',lossy=True)
    bm=data
    clean=bytearray(bm.replace(b'elst',b'free',1))
    # Missing edit plus FULL packet durations is the untrimmed positive. The
    # original shortened final stts without edit is a named refusal under ADR180.
    aa,bb=next((aa,bb) for tag,aa,bb,_ in formats.descendants(clean) if tag==b'stts')
    struct.pack_into('>I',clean,bb-4,1024)
    clean=bytes(clean)
    raw=formats.bmff_interval(bm)['raw_frames']
    add('no-edit.m4a',clean,44100,2,raw,'bmff','aac_lc',lossy=True)
    negatives={}
    negatives['short-stts-alone.m4a']=bm.replace(b'elst',b'free',1)
    aa,bb=next((aa,bb) for tag,aa,bb,_ in formats.descendants(bm) if tag==b'stts')
    bad=bytearray(bm);struct.pack_into('>I',bad,bb-4,int.from_bytes(bad[bb-4:bb],'big')+1)
    negatives['short-stts-conflict.m4a']=bytes(bad)
    # Exact rational fractional endpoint: change movie timescale only.
    a,b=next((a,b) for tag,a,b,_ in formats.descendants(bm) if tag==b'mvhd')
    bad=bytearray(bm);struct.pack_into('>I',bad,a+12,44101);negatives['edit-fractional.m4a']=bytes(bad)
    a,b=next((a,b) for tag,a,b,_ in formats.descendants(bm) if tag==b'elst')
    for name,offset,value in [('edit-zero.m4a',a+8,0),('edit-outside.m4a',a+12,2147483647),('edit-multiple.m4a',a+4,2)]:
        bad=bytearray(bm);struct.pack_into('>I',bad,offset,value);negatives[name]=bytes(bad)
    # Two structurally complete, noncontiguous edits. Not a truncated elst
    # stand-in: moov follows mdat, so media chunk offsets remain unchanged.
    bad=bytearray(bm);duration,media=struct.unpack_from('>Ii',bad,a+8)
    first_duration=duration//2
    struct.pack_into('>I',bad,a+4,2);struct.pack_into('>I',bad,a+8,first_duration)
    extra=struct.pack('>Iihh',duration-first_duration,media,1,0)
    containers=[(tag,start) for tag,aa,bb,start in formats.descendants(bm) if tag in (b'moov',b'trak',b'edts',b'elst') and start<a<bb]
    assert next(start for tag,aa,bb,start in formats.descendants(bm) if tag==b'moov')>next(start for tag,aa,bb,start in formats.descendants(bm) if tag==b'mdat')
    for tag,start in containers:struct.pack_into('>I',bad,start,int.from_bytes(bad[start:start+4],'big')+len(extra))
    bad[b:b]=extra;negatives['edit-multiple.m4a']=bytes(bad)
    bad=bytearray(bm);struct.pack_into('>h',bad,a+16,2);negatives['edit-rate.m4a']=bytes(bad)
    # Explicit unsupported trim text is retained as a real ID3 TXXX tag.
    def id3(text):
        payload=b'\x03iTunSMPB\0'+text.encode()
        frame=b'TXXX'+struct.pack('>I',len(payload))+bytes(2)+payload
        n=len(frame);size=bytes((n>>s)&127 for s in (21,14,7,0))
        return b'ID3\x03\0\0'+size+frame
    at=10+sum((clean_byte&127)<<(7*(3-i)) for i,clean_byte in enumerate(mp[6:10])) if mp[:3]==b'ID3' else 0
    negatives['unsupported-trim.mp3']=id3('00000000 00000240 00000300')+mp[at:]
    negatives['conflicting-trim.mp3']=id3('00000000 00000001 00000001')+mp[at:]
    bad=bytearray((assets/'flac-44100-2-16.flac').read_bytes());bad[-3]^=1;negatives['crc.flac']=bytes(bad)
    negatives['truncated.mp3']=mp[:-17]
    # Both admitted tag-CRC writer spans, deliberately distinct at8k mono.
    tagged=(assets/'mp3-8000-1-cbr.mp3').read_bytes()
    ss,ll,pp=formats.mp3_tag_location(tagged)
    for label,value in zip(('lame','ffmpeg'),formats.mp3_tag_crc_values(tagged,ss,ll,pp)):
        variant=bytearray(tagged);struct.pack_into('>H',variant,pp+34,value)
        interval=formats.mp3_interval(variant)
        path=assets/('tag-crc-'+label+'.mp3');path.write_bytes(variant)
        records[path.name]=dict(records['mp3-8000-1-cbr.mp3'],path='assets/'+path.name,sha256=model.digest(variant),bytes=len(variant),tag_crc_span=label)
    variant=bytearray(tagged);variant[pp+35]^=1;negatives['tag-crc-invalid.mp3']=bytes(variant)
    short=(HERE/'extra-encoded/short-trim.mp3').read_bytes();ss,ll,pp=formats.mp3_tag_location(short)
    bad=bytearray(short);bad[pp+21:pp+24]=b'\xff\xff\xff';negatives['trim-outside.mp3']=bytes(bad)
    xing=mp.index(b'Xing');bad=bytearray(mp);struct.pack_into('>I',bad,xing+8,1);negatives['xing-count.mp3']=bytes(bad)
    # Generated recognized video handler is outside audio-only BMFF scope.
    negatives['video-handler.m4a']=bm.replace(b'soun',b'vide',1)

    # Rejected format headers; these are not claimed to be valid alternate music.
    negatives['wave64.w64']=bytes.fromhex('726966662e91cf11a5d628db04c10000')+bytes(24)
    # Change the actually declared AIFC compression, leaving complete PCM payload.
    comp=(assets/'NONE-44100-2-16.aif').read_bytes()
    negatives['compressed.aifc']=comp.replace(b'NONE',b'alaw',1)
    # Actual independently encoded unsupported families / multi-stream containers.
    def alternate(name,args):
        if name in seeds:
            negatives[name]=(root/seeds[name]['path']).read_bytes();return
        source=root/'alternate-source.wav';source.write_bytes(formats.wave(signal(44100,44100),44100))
        target=assets/name
        command=['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-map_metadata','-1',*args,str(target)]
        p=subprocess.run(command,capture_output=True)
        if p.returncode:raise ValueError((name,p.stderr.decode()))
        negatives[name]=target.read_bytes()
        encodings.append({'asset':name,'argv':[v.replace(str(root),'{ROOT}') for v in command],'exit':p.returncode,'stderr':p.stderr.decode()})
        source.unlink()
    for name,args in [('ogg-flac.ogg',['-c:a','flac','-f','ogg']),('layer2.mp2',['-c:a','mp2','-b:a','128k']),('alac.m4a',['-c:a','alac']),('loas.aac',['-c:a','aac','-f','latm']),('extra-audio.m4a',['-map','0:a','-map','0:a','-c:a','aac'])]:alternate(name,args)
    # MPEG bitrate index0 is explicitly free-format, not an unsupported extension.
    bad=bytearray(mp);first=at;bad[first+2]&=15;negatives['free-format.mp3']=bytes(bad)
    # ADTS profile field1 is LC;2 is SSR (unsupported).
    adts=bytearray((assets/'adts-44100-2.aac').read_bytes());adts[2]=(adts[2]&63)|128;negatives['unsupported-aac.aac']=bytes(adts)
    for name,bytes_ in negatives.items():
        if name in ('trim-outside.mp3','xing-count.mp3'):
            ss,ll,pp=formats.mp3_tag_location(bytes_);fixed=bytearray(bytes_)
            struct.pack_into('>H',fixed,pp+34,formats.mp3_tag_crc_values(fixed,ss,ll,pp)[1]);bytes_=bytes(fixed)
        (assets/name).write_bytes(bytes_)
        records[name]=dict(path='assets/'+name,sha256=model.digest(bytes_),bytes=len(bytes_),licence='CC0-1.0',generator='fixtures.py',refuse=True)
    for path in sorted(p for p in (HERE/'extra-encoded').iterdir() if p.suffix in ('.aac','.mp4','.mp1','.w64','.mp3')):
        data=path.read_bytes();name=path.name
        if name=='short-trim.mp3':
            interval=formats.mp3_interval(data)
            add(name,data,44100,1,interval['raw_frames'],'mpeg','mp3',lossy=True)
            records[name].update(interval)
        elif not name.startswith('fdk-crc-'):
            (assets/name).write_bytes(data)
            records[name]=dict(path='assets/'+name,sha256=model.digest(data),bytes=len(data),licence='CC0-1.0',generator='FDK-reference/PROVENANCE.md',refuse=True)
        else:
            channels=int(name.split('-')[-1].split('.')[0])
            # Frozen FDK output:46 raw1024-frame packets at44.1k (verified by
            # independent ADTS frame census, not an encoder input-length guess).
            at=0;frames=0
            while at<len(data):
                length=((data[at+3]&3)<<11)|(data[at+4]<<3)|(data[at+5]>>5)
                assert length>=9 and not data[at+1]&1 and not data[at+6]&3
                at+=length;frames+=1
            assert at==len(data)
            add(name,data,44100,channels,frames*1024,'adts','aac_lc',lossy=True,crc_protected=True,family='adts-crc')
            bad=bytearray(data);bad[8]^=1;badname='bad-'+name
            (assets/badname).write_bytes(bad)
            records[badname]=dict(path='assets/'+badname,sha256=model.digest(bad),bytes=len(bad),licence='CC0-1.0',generator='FDK-reference/checksum-byte-only',refuse=True)
    # Valid sparse RIFF source reaches output uint32 boundary without allocating
    # decoded output or placing a large raw asset in git. Signed zero is sparse.
    for name,count in [('riff-overflow-source.wav',178956970),('riff-largest-source.wav',178956969)]:
        size=count*2
        header=struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',size+36,b'WAVE',b'fmt ',16,1,1,7350,14700,2,16,b'data',size)
        path=assets/name
        with path.open('wb') as out:
            out.write(header);out.seek(44+size-1);out.write(b'\0')
        sha=hashlib.sha256()
        with path.open('rb') as inp:
            while block:=inp.read(1024*1024):sha.update(block)
        records[path.name]=dict(path='assets/'+path.name,sha256=sha.hexdigest(),bytes=44+size,input_rate=7350,input_channels=1,raw_frames=count,trim_head=0,trim_tail=0,effective_frames=count,trim_evidence='none',container='wave',codec='pcm',codec_profile='pcm',bits=16,licence='CC0-1.0',generator='fixtures.py',family='large-boundary')
    # A rate/channel change is a stream-level refusal even when both parts
    # separately belong to the positive matrix.
    for name,other in [('changing-rate.mp3','mp3-48000-2-vbr.mp3'),('changing-channels.mp3','mp3-44100-1-vbr.mp3')]:
        bytes_=mp+(assets/other).read_bytes()
        (assets/name).write_bytes(bytes_)
        records[name]=dict(path='assets/'+name,sha256=model.digest(bytes_),bytes=len(bytes_),licence='CC0-1.0',generator='fixtures.py',refuse=True)
    # Full decoder/version provenance; encoder argv paths are authoring metadata,
    # never part of expected Product manifest or a cross-platform waveform hash.
    version=json.loads((root/'ENCODER.json').read_text(encoding='utf-8'))['version'] if seed else subprocess.run(['ffmpeg','-version'],capture_output=True,text=True).stdout
    (root/'ENCODER.json').write_text(json.dumps({'version':version,'runs':encodings},indent=2)+'\n')
    (root/'SOURCES.json').write_bytes(model.canonical(records))
    source=root/'encoder-source.wav'
    if source.exists():source.unlink()
    return records


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory');ap.add_argument('--seed');args=ap.parse_args()
    print('Generated',len(build(args.directory,args.seed)),'CC0 source fixtures')
