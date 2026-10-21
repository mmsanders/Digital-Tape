"""Frozen abstract controls. Zero actual fixtures, no codec execution."""
def cases():
 base=dict(success=True,admitted=True,source_bound=True,spec_c=2,planes=2,host_c=2,frames=3,capacity=5,copy_lengths=[3,3],changed=False,reestablished=False)
 rows=[]
 def add(name,patch,want):rows.append(dict(name=name,input=dict(base,**patch),expected=want))
 add('stereo-capacity-not-length',{},'FINITE_PREMISES_HOLD_NOT_SOURCE_PROOF')
 add('mono',dict(spec_c=1,planes=1,host_c=1,copy_lengths=[3]),'FINITE_PREMISES_HOLD_NOT_SOURCE_PROOF')
 add('zero-frames-two-planes',dict(frames=0,copy_lengths=[0,0]),'FINITE_PREMISES_HOLD_NOT_SOURCE_PROOF')
 add('empty-plane-invalid-model',dict(planes=0,admitted=False),'UNADMITTED_MODEL_ONLY')
 add('admitted-empty-plane',dict(planes=0),'SHAPE_PREMISE_FALSE')
 add('metadata-disagreement',dict(host_c=1),'SHAPE_PREMISE_FALSE')
 add('mask-as-count',dict(spec_c=3),'SHAPE_PREMISE_FALSE')
 add('capacity-as-valid-frames',dict(frames=6),'SHAPE_PREMISE_FALSE')
 add('zip-shortened-outer',dict(copy_lengths=[3]),'COPY_PREMISE_FALSE')
 add('one-short-plane',dict(copy_lengths=[3,2]),'COPY_PREMISE_FALSE')
 add('copied-capacity',dict(copy_lengths=[5,5]),'COPY_PREMISE_FALSE')
 add('changed-unproved',dict(changed=True),'TRANSITION_UNPROVED')
 add('changed-reestablished',dict(changed=True,reestablished=True),'FINITE_PREMISES_HOLD_NOT_SOURCE_PROOF')
 add('changed-refused',dict(success=False,changed=True),'OUTSIDE_SUCCESS_DOMAIN')
 add('wrong-source',dict(source_bound=False),'UNBOUND')
 add('bool-not-count',dict(planes=True),'BAD_TYPE')
 return rows
