"""Independent generated-container writers and encoded interval readers.

All PCM sources are mathematical signals dedicated to CC0. FFmpeg encodes only
the lossy/container fixtures; no FFmpeg decoded bytes are universal goldens.
"""
import hashlib
import math
import struct
from pathlib import Path
import numpy as np


def pcm_bytes(x,bits,endian='little',unsigned=False):
    q=np.rint(np.asarray(x)*(2**(bits-1))).astype(np.int64)
    assert np.max(np.abs(q),initial=0)<2**(bits-1)
    if unsigned:q=q+2**(bits-1)
    return b''.join(int(v).to_bytes((bits+7)//8,endian,signed=not unsigned) for v in q.ravel())


def chunk(tag,data,endian='<'):
    return tag+struct.pack(endian+'I',len(data))+data+(b'\0' if len(data)%2 else b'')


def wave(x,rate,bits=16,floating=False,extensible=False,mask=None):
    x=np.asarray(x);channels=x.shape[1];width=bits//8
    data=x.astype('<f%d'%width).tobytes() if floating else pcm_bytes(x,bits,unsigned=bits==8)
    tag=3 if floating else 1
    fmt=struct.pack('<HHIIHH',0xfffe if extensible else tag,channels,rate,rate*channels*width,channels*width,bits)
    if extensible:
        if mask is None:mask=4 if channels==1 else 3
        fmt+=struct.pack('<HHI',22,bits,mask)+struct.pack('<IHH8s',tag,0,0x10,b'\x80\0\0\xaa\0\x38\x9b\x71')
    body=b'WAVE'+chunk(b'fmt ',fmt)+chunk(b'data',data)
    return b'RIFF'+struct.pack('<I',len(body))+body


def extended80(rate):
    exponent=int(math.floor(math.log2(rate)))
    mantissa=int(rate*2**(63-exponent))
    return struct.pack('>HQ',exponent+16383,mantissa)


def aiff(x,rate,bits=16,compression=None):
    channels=x.shape[1]
    data=pcm_bytes(x,bits,'little' if compression==b'sowt' else 'big')
    comm=struct.pack('>HIH',channels,len(x),bits)+extended80(rate)
    if compression is not None:comm+=compression+b'\0\0'
    body=(b'AIFC' if compression is not None else b'AIFF')
    if compression is not None:body+=chunk(b'FVER',struct.pack('>I',0xA2805140),'>')
    body+=chunk(b'COMM',comm,'>')+chunk(b'SSND',bytes(8)+data,'>')
    return b'FORM'+struct.pack('>I',len(body))+body


def crc(data,width,poly):
    state=0
    for b in data:
        state^=b<<(width-8)
        for _ in range(8):state=((state<<1)^poly if state&(1<<(width-1)) else state<<1)&((1<<width)-1)
    return state


def flac(x,rate,bits):
    """RFC9639 verbatim/independent-channel frames, including all8..32 bit depths."""
    channels=x.shape[1];n=len(x);assert n<=65535
    packed=(rate<<44)|((channels-1)<<41)|((bits-1)<<36)|n
    info=struct.pack('>HH',n,n)+bytes(6)+packed.to_bytes(8,'big')+hashlib.md5(pcm_bytes(x,bits)).digest()
    header=b'\xff\xf8\x70'+bytes([(channels-1)<<4])+b'\0'+struct.pack('>H',n-1)
    header+=bytes([crc(header,8,0x07)])
    values=np.rint(x*(2**(bits-1))).astype(np.int64)
    bitstream=''
    for channel in range(channels):
        bitstream+='00000010' # zero padding, VERBATIM subframe type, no wasted bits
        bitstream+=''.join(format(int(v)&((1<<bits)-1),'0%db'%bits) for v in values[:,channel])
    bitstream+='0'*((-len(bitstream))%8)
    payload=int(bitstream,2).to_bytes(len(bitstream)//8,'big') if bitstream else b''
    frame=header+payload;frame+=struct.pack('>H',crc(frame,16,0x8005))
    return b'fLaC'+b'\x80\0\0\x22'+info+frame


def boxes(data,start=0,end=None):
    end=len(data) if end is None else end
    at=start
    while at<end:
        if at+8>end:raise ValueError('truncated BMFF box')
        size,tag=struct.unpack_from('>I4s',data,at);head=8
        if size==1:size=struct.unpack_from('>Q',data,at+8)[0];head=16
        if size==0:size=end-at
        if size<head or at+size>end:raise ValueError('bad BMFF size')
        yield tag,at+head,at+size,at
        at+=size


def descendants(data,start=0,end=None):
    for tag,a,b,box_start in boxes(data,start,end):
        yield tag,a,b,box_start
        if tag in (b'moov',b'trak',b'mdia',b'minf',b'stbl',b'edts'):
            yield from descendants(data,a,b)


def bmff_interval(data):
    found=list(descendants(data));get=lambda tag:next((a,b) for t,a,b,_ in found if t==tag)
    a,b=get(b'mvhd');version=data[a];movie_scale=struct.unpack_from('>I',data,a+(20 if version else 12))[0]
    a,b=get(b'mdhd');version=data[a];rate=struct.unpack_from('>I',data,a+(20 if version else 12))[0]
    a,b=get(b'elst');version=data[a];count=struct.unpack_from('>I',data,a+4)[0]
    entries=[];pos=a+8
    for _ in range(count):
        duration,media=struct.unpack_from('>Qq' if version else '>Ii',data,pos);pos+=16 if version else 8
        integer,fraction=struct.unpack_from('>hh',data,pos);pos+=4
        entries.append((duration,media,integer,fraction))
    if len(entries)!=1 or entries[0][2:]!=(1,0):raise ValueError('unsupported edit interval')
    duration,head,*_=entries[0]
    if duration*rate%movie_scale:raise ValueError('fractional edit endpoint')
    effective=duration*rate//movie_scale
    a,b=get(b'stsz');packets=struct.unpack_from('>I',data,a+8)[0];raw=packets*1024
    a,b=get(b'stts');entries_count=struct.unpack_from('>I',data,a+4)[0]
    durations=[struct.unpack_from('>II',data,a+8+8*i) for i in range(entries_count)]
    if sum(count for count,duration in durations)!=packets:raise ValueError('stts packet census')
    if any(duration!=1024 for count,duration in durations[:-1]):raise ValueError('unsupported stts intervals')
    if durations[-1][1]<1024:
        if durations[-1][0]!=1 or sum(count*duration for count,duration in durations)!=head+effective:
            raise ValueError('shortened stts conflicts with edit')
    if head<0 or effective<=0 or head+effective>raw:raise ValueError('out of range edit')
    return dict(input_rate=rate,raw_frames=raw,trim_head=head,trim_tail=raw-head-effective,
                effective_frames=effective,trim_evidence='bmff_edit',movie_timescale=movie_scale,
                presentation_duration=duration,decoder_priming=1024)


def bmff_presentation(data):
    found=list(descendants(data))
    if any(tag==b'elst' for tag,*_ in found):return bmff_interval(data)
    a,b=next((a,b) for tag,a,b,_ in found if tag==b'stts')
    entries=struct.unpack_from('>I',data,a+4)[0]
    values=[struct.unpack_from('>II',data,a+8+8*i) for i in range(entries)]
    if any(duration!=1024 for count,duration in values):raise ValueError('shortened stts without admitted edit')
    raw=sum(count*duration for count,duration in values)
    return dict(raw_frames=raw,trim_head=0,trim_tail=0,effective_frames=raw,trim_evidence='none')


def aifc_precision(data):
    if data[:4]!=b'FORM' or data[8:12] not in (b'AIFF',b'AIFC'):raise ValueError('not AIFF/AIFC')
    at=12
    while at<len(data):
        size=int.from_bytes(data[at+4:at+8],'big');body=data[at+8:at+8+size]
        if data[at:at+4]==b'COMM':
            channels,frames,bits=struct.unpack_from('>HIH',body)
            compression=b'NONE' if data[8:12]==b'AIFF' else body[18:22]
            if compression==b'sowt' and bits!=16:raise ValueError('AIFC sowt sampleSize must be16')
            if compression not in (b'NONE',b'sowt') or bits not in (8,16,24,32):raise ValueError('unsupported AIFC precision/compression')
            return channels,frames,bits,compression
        at+=8+size+size%2
    raise ValueError('missing COMM')


def mp3_interval(data):
    at=0
    if data[:3]==b'ID3':at=10+sum((data[6+i]&127)<<(7*(3-i)) for i in range(4))
    frames=[];first=None
    while at+4<=len(data):
        h=int.from_bytes(data[at:at+4],'big')
        if h>>21!=0x7ff:break
        v=(h>>19)&3;layer=(h>>17)&3;bi=(h>>12)&15;ri=(h>>10)&3
        if v==1 or layer!=1 or bi in (0,15) or ri==3:raise ValueError('not admitted LayerIII')
        rate=[44100,48000,32000][ri]//(1 if v==3 else 2 if v==2 else 4)
        kbps=([0,32,40,48,56,64,80,96,112,128,160,192,224,256,320] if v==3 else [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160])[bi]
        count=1152 if v==3 else 576;length=(144000 if v==3 else 72000)*kbps//rate+((h>>9)&1)
        if at+length>len(data):raise ValueError('truncated MP3 frame')
        frames.append((at,length));first=first or (h,rate,count)
        at+=length
    if not frames:raise ValueError('no MP3 frames')
    h,rate,count=first;start,length=frames[0];mono=((h>>6)&3)==3;v=(h>>19)&3
    side=(17 if mono else 32) if v==3 else (9 if mono else 17)
    xing=start+4+(0 if (h>>16)&1 else 2)+side
    if data[xing:xing+4] not in (b'Xing',b'Info'):return dict(input_rate=rate,raw_frames=len(frames)*count,trim_head=0,trim_tail=0,effective_frames=len(frames)*count,trim_evidence='none')
    flags=int.from_bytes(data[xing+4:xing+8],'big');p=xing+8
    declared=None
    for mask,width in [(1,4),(2,4),(4,100),(8,4)]:
        if flags&mask:
            if mask==1:declared=int.from_bytes(data[p:p+4],'big')
            p+=width
    tag=data[p:p+36]
    if len(tag)<36:raise ValueError('missing LAME-compatible tag')
    validate_mp3_tag_crc(data,start,length,p)
    delay=(tag[21]<<4)|(tag[22]>>4);padding=((tag[22]&15)<<8)|tag[23]
    if declared!=len(frames)-1:raise ValueError('Xing frame census disagrees')
    raw=declared*count
    if delay+padding>=raw:raise ValueError('invalid MP3 interval')
    # Encoder interval is independent of decoder synthesis latency. FFmpeg's raw
    # PCM origin adds529 and removes529 from the tail; alternative decoder origins
    # must declare an equivalent mapping, never guess/remove extra presentation.
    return dict(input_rate=rate,raw_frames=raw,trim_head=delay+529,trim_tail=padding-529,
                effective_frames=raw-delay-padding,trim_evidence='xing_lame',encoder_delay=delay,
                encoder_padding=padding,decoder_priming=529,encoder_tag=tag[:9].decode('ascii','replace'),
                encoded_audio_frames=declared,samples_per_frame=count)


def crc16le(data):
    state=0
    for byte in data:
        state^=byte
        for _ in range(8):state=(state>>1)^0xA001 if state&1 else state>>1
    return state


def crc_bits(bits,initial=0xFFFF):
    state=initial
    for bit in bits:
        top=(state>>15)^int(bit);state=(state<<1)&0xFFFF
        if top:state^=0x8005
    return state


def adts_silence(crc_protected=True,frames=4,channels=1):
    # AAC-LC single-channel element with max_sfb0: no spectral payload, no PNS.
    # ISO13818-7: protect all56 header bits and192 bits of the SCE after ID;
    # append zero bits when the SCE is shorter. ID_END/alignment are excluded.
    body='0000'+format(100,'08b')+'0'+'00'+'0'+'000000'+'0'+'0'+'0'+'0'
    extra=''
    if channels==2:
        extra=format(100,'08b')+'000'
        body='0000'+'1'+'0'+'00'+'0'+'000000'+'0'+'00'+format(100,'08b')+'000'+extra
    raw=('000' if channels==1 else '001')+body+'111';raw+='0'*((-len(raw))%8)
    payload=int(raw,2).to_bytes(len(raw)//8,'big');size=(9 if crc_protected else 7)+len(payload)
    header='1'*12+'0'+'00'+('0' if crc_protected else '1')+'01'+'0100'+'0'+format(channels,'03b')+'00'+'00'+format(size,'013b')+'1'*11+'00'
    assert len(header)==56
    data=int(header,2).to_bytes(7,'big')
    if crc_protected:data+=crc_bits(header+body.ljust(192,'0')+(extra.ljust(128,'0') if extra else '')).to_bytes(2,'big')
    return (data+payload)*frames


def validate_generated_adts(data):
    # This reader is deliberately scoped to our generated minimal SCE vectors,
    # not a claim to independently parse arbitrary AAC Huffman/spectral syntax.
    at=0;count=0
    while at<len(data):
        if at+7>len(data) or data[at]!=255 or data[at+1]&0xF6!=0xF0:raise ValueError('ADTS header')
        header=data[at:at+7];size=((header[3]&3)<<11)|(header[4]<<3)|(header[5]>>5)
        if header[6]&3:raise ValueError('ADTS multiple raw data blocks')
        if at+size>len(data):raise ValueError('ADTS truncation')
        protected=not(header[1]&1);offset=9 if protected else 7
        bits=''.join(format(b,'08b') for b in data[at+offset:at+size])
        channels=((header[2]&1)<<2)|(header[3]>>6)
        if channels==1:
            if bits[:3]!='000' or bits[15:26]!='00000000000':raise ValueError('not generated SCE')
            body=bits[3:29];extra=''
        elif channels==2:
            if bits[:3]!='001' or bits[7:8]!='1':raise ValueError('not generated CPE')
            body=bits[3:43];extra=body[-11:]
        else:raise ValueError('not generated channel count')
        if protected:
            expected=int.from_bytes(data[at+7:at+9],'big')
            hb=''.join(format(b,'08b') for b in header)
            if crc_bits(hb+body.ljust(192,'0')+(extra.ljust(128,'0') if extra else ''))!=expected:raise ValueError('ADTS CRC mismatch')
        at+=size;count+=1
    return count*1024


def mp3_tag_location(data):
    start=10+sum((data[6+i]&127)<<(7*(3-i)) for i in range(4)) if data[:3]==b'ID3' else 0
    h=int.from_bytes(data[start:start+4],'big');version=(h>>19)&3
    rate=[44100,48000,32000][(h>>10)&3]//(1 if version==3 else 2 if version==2 else 4)
    rates=[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320] if version==3 else [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160]
    size=(144000 if version==3 else 72000)*rates[(h>>12)&15]//rate+((h>>9)&1)
    mono=((h>>6)&3)==3;side=(17 if mono else 32) if version==3 else (9 if mono else 17)
    xing=start+4+(0 if (h>>16)&1 else 2)+side
    if data[xing:xing+4] not in (b'Xing',b'Info'):raise ValueError('no Xing/Info')
    flags=int.from_bytes(data[xing+4:xing+8],'big');p=xing+8
    for flag,width in ((1,4),(2,4),(4,100),(8,4)):
        if flags&flag:p+=width
    return start,size,p


def mp3_tag_crc_values(data,start,size,p):
    # FFmpeg's fixed190-byte writer span zero-initializes bytes beyond a short
    # metadata frame; it calculates before writing the two tag-CRC bytes.
    frame=bytearray(data[start:start+size]);offset=p-start
    frame[offset+34:offset+36]=bytes(2)
    return crc16le(frame[:offset+34]),crc16le(bytes(frame[:190]).ljust(190,b'\0'))


def validate_mp3_tag_crc(data,start=None,size=None,p=None):
    if start is None:start,size,p=mp3_tag_location(data)
    expected=int.from_bytes(data[p+34:p+36],'big')
    values=mp3_tag_crc_values(data,start,size,p)
    if expected not in values:raise ValueError('LAME-compatible tag CRC mismatch')
    return ['lame','ffmpeg'][0 if expected==values[0] else 1]


def generated_pcm(data):
    """Independent decoder for the generated RIFF PCM/float families only."""
    if data[:4]!=b'RIFF' or data[8:12]!=b'WAVE':raise ValueError('generated WAVE required')
    at=12;fmt=None;payload=None
    while at+8<=len(data):
        tag=data[at:at+4];size=int.from_bytes(data[at+4:at+8],'little');body=data[at+8:at+8+size]
        if len(body)!=size:raise ValueError('truncated generated WAVE')
        if tag==b'fmt ':fmt=body
        if tag==b'data':payload=body
        at+=8+size+(size%2)
    code,ch,rate,_,_,bits=struct.unpack_from('<HHIIHH',fmt)
    if code==0xfffe:code=int.from_bytes(fmt[24:28],'little')
    if code==3:x=np.frombuffer(payload,dtype='<f%d'%(bits//8)).astype(float)
    elif code==1:
        width=bits//8
        x=np.array([int.from_bytes(payload[i:i+width],'little',signed=bits!=8) for i in range(0,len(payload),width)],float)
        if bits==8:x-=128
        x/=2**(bits-1)
    else:raise ValueError('unsupported generated PCM tag')
    return x.reshape(-1,ch),rate
