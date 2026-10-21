"""Abstract premise discriminator, never a production decoder/proof checker."""
def classify(x):
 if not x['success']:return 'OUTSIDE_SUCCESS_DOMAIN'
 if not x['admitted']:return 'UNADMITTED_MODEL_ONLY'
 if x['source_bound'] is not True:return 'UNBOUND'
 c=x['spec_c'];p=x['planes'];h=x['host_c'];f=x['frames'];cap=x['capacity']
 if any(type(n) is not int for n in (c,p,h,f,cap)):return 'BAD_TYPE'
 if c not in (1,2) or h!=c or p!=c or not 0<=f<=cap:return 'SHAPE_PREMISE_FALSE'
 if len(x['copy_lengths'])!=c or any(type(n) is not int or n!=f for n in x['copy_lengths']):return 'COPY_PREMISE_FALSE'
 if x['changed'] and not x['reestablished']:return 'TRANSITION_UNPROVED'
 return 'FINITE_PREMISES_HOLD_NOT_SOURCE_PROOF'
