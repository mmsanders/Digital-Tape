"""Additional independent logical binding states; not actual CPU/allocation measurements.
Original38 expectations are unchanged. Numbers are abstract inclusive units.
"""
def final_decision(task, phase, nxt, completion, task_limit, phase_limit):
 if task+nxt+completion>task_limit:return 'REJECT_TASK'
 if phase+nxt+completion>phase_limit:return 'REJECT_PHASE'
 return 'ALLOW'

def selftest():
 # Earlier gate90+9+1==100 allowed; final overhead1 makes it exhausted.
 assert final_decision(90,10,9,1,100,100)=='ALLOW'
 assert final_decision(91,11,9,1,100,100)=='REJECT_TASK'
 # Task slack cannot override an exhausted final phase.
 assert final_decision(20,10,9,1,100,20)=='ALLOW'
 assert final_decision(21,11,9,1,100,20)=='REJECT_PHASE'
 # Equality remains allowed; no off-by-one relaxation or arbitrary margin.
 assert final_decision(90,10,9,1,100,20)=='ALLOW'
 # Complete observed samples include temporary peak80 then lower final/post20.
 samples=[40,45,80,20,20];task_high=max(samples);phase_base=10
 phase_high=max(0,task_high-phase_base)
 assert (task_high,phase_high)==(80,70)
 assert final_decision(task_high,phase_high,25,0,100,100)=='REJECT_TASK'
 assert final_decision(task_high,phase_high,20,0,100,90)=='ALLOW'
 # Stale endpoint-only40 would allow25 and is therefore discriminated.
 assert final_decision(40,30,25,0,100,100)=='ALLOW'
 # Logical expected rejection requires zero launches through the future binding.
 return 'PASS logical expectations only; actual changed binding/source still required'

if __name__=='__main__':print(selftest())
