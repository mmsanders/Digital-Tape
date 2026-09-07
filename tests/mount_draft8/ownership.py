"""Spec-derived predicates for a future operation trace adapter; not product APIs.
Scope: ordinary bump allocation only. Do not apply this predicate to re-spool's
opportunistic second pass, promote phase 2, or destructive format/duplicate.
"""
from cases import CF

def free_next(high,live_b):
    return max([high]+[(c*CF+s+n-1)//CF+1 for c,s,n in live_b])

def ordinary_allocation(high,free,capacity,start,count):
    """Allocation is a positive contiguous bump run at the current free pointer."""
    return 0<=high<=free<=capacity and count>0 and start==free and start>=high and start+count<=capacity

def ordinary_write(high,capacity,lba,count):
    """Only for a callback ALREADY classified as an ordinary Side-B audio write.
    Metadata writes must be classified separately; checking their LBA here is wrong.
    """
    return count>0 and 2048+high*1024<=lba and lba+count<=2048+capacity*1024
