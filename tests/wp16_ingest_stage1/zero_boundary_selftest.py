"""Independent ADR-178 arithmetic/admission checkpoint, not Product acceptance.

Whole-request refusal must occur even if valid neighbours or gaps make the total
positive. No WAV/meter/gain expectation or filter is changed by this amendment.
"""
from model import RATES, GAP, output_frames, admitted_output_frames


def request(sources, folders):
    return sum(admitted_output_frames(name, n, rate) for name, n, rate in sources)+GAP*(folders-1)


def refused(sources, folders, name):
    try:
        request(sources, folders)
    except ValueError as error:
        assert name in str(error) and 'too short' in str(error)
        return
    raise AssertionError('zero-output source admitted: '+name)


checks=0
for rate in RATES:
    for n in range(1,101):
        # Independent integer cross-multiplication: nearest interval, ties upward.
        count=output_frames(n,rate)
        assert 2*count*rate-rate <= 2*n*44100 < 2*count*rate+rate
        if count:
            assert admitted_output_frames('source.wav',n,rate)==count
        else:
            refused([('source.wav',n,rate)],1,'source.wav')
        checks+=1

for name,n,rate in [('zero-192k-n1.wav',1,192000),('zero-192k-n2.wav',2,192000),
                    ('zero-176k-n1.wav',1,176400),('zero-96k-n1.wav',1,96000)]:
    refused([(name,n,rate)],1,name)
    refused([(name,n,rate),('positive.wav',44100,44100)],1,name)
    refused([('positive.wav',44100,44100),(name,n,rate)],2,name)
    checks+=3

# Half-up tie and immediately positive neighbours remain admitted, including
# digital silence (admission is intentionally independent of the sample values).
for n,rate,want in [(1,88200,1),(2,96000,1),(2,176400,1),(3,192000,1)]:
    assert admitted_output_frames('silent-or-short.wav',n,rate)==want
    checks+=1

def refusal_observer(sources, observation):
    """Proposed observation gate; synthetic controls do not prove native I/O."""
    # Cross-multiplication gives zero-rounding independently of output_frames.
    zero=[name for name,n,rate in sources if 2*n*44100 < rate]
    assert zero, 'this observer applies to a zero-output input'
    assert observation['exit']==2, 'source-level exit2 refusal required'
    assert any(name in observation['stderr'] for name in zero), 'missing source name'
    assert 'too short' in observation['stderr'], 'missing plain reason'
    assert not observation['output_files'], 'output opened before refusal'
    assert not observation['staging_files'], 'staging opened before refusal'

bad=[('too-short.wav',1,192000),('positive.wav',44100,44100)]
baseline={'exit':2,'stderr':'too-short.wav: too short to produce one 44.1kHz frame',
          'output_files':[],'staging_files':[]}
refusal_observer(bad,baseline)
# Green refusal baseline, then causal faults: skip, clamp to one, rescue via
# positive total, missing source reason and stage-before-refusal. The first
# three distinct producer faults have the same visible success contract fault.
for policy in ('skip','clamp','gap-rescue','unnamed','stage-before-refusal'):
    observation=dict(baseline)
    if policy in ('skip','clamp','gap-rescue'):observation['exit']=0
    elif policy=='unnamed':observation['stderr']='too short'
    else:observation['staging_files']=['stage/audio.wav']
    try:refusal_observer(bad,observation)
    except AssertionError:checks+=1
    else:raise AssertionError('control escaped: '+policy)
print('ADR-178:',checks,'arithmetic/admission checks passed; not Product acceptance')
