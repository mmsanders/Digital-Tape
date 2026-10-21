"""25 frozen tiny proof-model challenges; not actual codec/witness executions."""
U64=2**64-1
def corpus():
 rows=[]
 def add(name,op,args,expected):rows.append(dict(name=name,op=op,args=args,expected=expected))
 for name,size,ch,w,exp in [('mono-u8',3,1,1,3),('stereo-i16',12,2,2,3),('mono-i24',15,1,3,5),('stereo-f64',32,2,8,2),('partial-frame',11,2,2,None)]:add(name,'pcm_count',dict(bytes=size,channels=ch,width=w),exp)
 for name,ch,blocks,raw,planes,exp in [('mono-blocks',1,[[3],[2]],5,[5],True),('stereo-blocks',2,[[3,3],[2,2]],5,[5,5],True),('missing-raw-update',2,[[3,3],[2,2]],3,[5,5],False),('short-plane',2,[[3,3],[2,1]],5,[5,4],False),('missing-channel',2,[[3],[2]],5,[5],False)]:add(name,'append',dict(channels=ch,blocks=blocks,raw=raw,planes=planes),exp)
 for name,n,h,t,exp in [('trim-middle',10,2,3,5),('trim-all',3,1,2,None),('trim-overflow',U64,U64,1,None),('trim-one',1,0,0,1)]:add(name,'trim',dict(raw=n,head=h,tail=t),exp)
 for name,n,r,exp in [('round-zero',2,192000,0),('round-one',3,192000,1),('identity-count',3,44100,3),('wide-intermediate-valid',U64,192000,(U64*44100+96000)//192000),('output-overflow',U64,7350,None)]:add(name,'frames',dict(effective=n,rate=r),exp)
 for name,same_bytes,same_meta,exp in [('same-pass',True,True,True),('mutated-source',False,True,False),('changed-decode-state',True,False,False)]:add(name,'pass_premise',dict(same_bytes=same_bytes,same_metadata=same_meta),exp)
 add('mono-duplication','channels',dict(left=3,right=None,output_samples=6),True)
 add('stereo-zip-short','channels',dict(left=3,right=2,output_samples=4),False)
 add('32-continues-no-ranking','convergence',dict(attempts=['continue']*32,claimed_global=True,complete_rank_argument=False),False)
 assert len(rows)==25
 return rows
