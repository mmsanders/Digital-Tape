#!/usr/bin/env python3
"""Real GitHub plumbing; role actors are simulated, never production credentials."""
import base64
import copy
import json
import os
from pathlib import Path
import sys
import urllib.error
from bus import (GitHub, Controller, Refused, RUNTIME_FILE, empty_state, environment_protected,
                 prepared, digest, projection, need, LEADS, WORKERS)
from test_bus import form

api = GitHub(os.environ['GITHUB_REPOSITORY'], os.environ['GH_TOKEN'])
run = os.environ['GITHUB_RUN_ID']
config = json.loads(RUNTIME_FILE.read_text())
out = Path('build/plumbing'); out.mkdir(parents=True, exist_ok=True)


def guard():
    env = environment_protected(api, config)
    need(all(not x['enabled'] for x in config['roles'].values()), 'production roles must remain disabled')
    state, _ = api.ledger()
    need(state['current'] is None and not api.rounds(), 'another round exists; test refused')
    return env


if sys.argv[1] == 'preflight':
    guard()
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
        f.write('## Plumbing test approval\n\nApprove only this fixed test at commit `' + os.environ['GITHUB_SHA'] + '`.'
                '\n\nCreates one test round, four lead roots and three worker issues; exercises all eight simulated roles, '
                'real native parents, Contents SHA conflicts, exclusive claims, fan-in, blocked-worker disposition and PM close. '
                'Closes test issues and deletes the temporary ledger file. No model calls, production bindings, product work, '
                'purchases or independent acceptance. GitHub role identities and adapter wakeups are simulated, not certified.\n')
    print('Preflight passed; no test issues or bindings created. Await Michael in protected environment.')
    sys.exit(0)

if sys.argv[1] == 'cleanup':
    # Recovery after a failed exercise step; restricted to this run's manifest and path.
    manifest = out / 'issues.json'
    for n in json.loads(manifest.read_text()) if manifest.exists() else []:
        item = api.issue(n)
        need(item['title'].startswith('[PLUMBING '+run+'] '), 'cleanup scope mismatch')
        api.call(f'issues/{n}', 'PATCH', {'state':'closed'})
    path = 'contents/plumbing-' + run + '.json'
    try: file = api.call(path+'?ref=agent-bus-state')
    except urllib.error.HTTPError as e:
        if e.code != 404: raise
    else: api.call(path,'DELETE',dict(branch='agent-bus-state',sha=file['sha'],message='Clean plumbing test '+run))
    print('Recovery cleanup complete for this run.')
    sys.exit(0)

guard()
for role, entry in config['roles'].items():
    entry.update(enabled=True, actor='simulated-'+role, instance='plumbing-'+run+'-'+role, provider='openai')
# Model strings are simulated attestations. No actual provider is invoked (including Grok).
state = empty_state(config)
created = []
trace = []
path = 'contents/plumbing-' + run + '.json'
sha = None
counter = 0


def record(text):
    print(text, flush=True)
    trace.append(text)
    (out / 'trace.json').write_text(json.dumps(trace, indent=2))


def create(title, labels, body, parent=None):
    item = api.call('issues', 'POST', dict(title='[PLUMBING '+run+'] '+title,
        labels=labels, body='SIMULATED AGENT TEST — no product acceptance.\n\n'+body))
    created.append(item['number'])
    (out / 'issues.json').write_text(json.dumps(created))
    if parent:
        api.call(f'issues/{parent}/sub_issues', 'POST', {'sub_issue_id':item['id']})
        need(api.parent(item['number']) == parent, 'native parent did not persist')
    return item['number']


def save(value):
    global sha
    args = dict(branch='agent-bus-state', message='Isolated plumbing test '+run,
                content=base64.b64encode(json.dumps(value).encode()).decode())
    if sha: args['sha'] = sha
    result = api.call(path, 'PUT', args)
    sha = result['content']['sha']


def command(cmd, role, payload, approved=None, request=None):
    global state, counter
    counter += 1
    staged = copy.deepcopy(state)
    actor = config['human'] if role == 'human' else config['roles'][role]['actor']
    c = Controller(api, config, staged, actor, request or f'plumbing-{run}-{counter}', run)
    result = c.execute(cmd, payload, approved)
    save(staged)
    state = staged
    projection(api, state)
    (out / f'{counter:03}-{cmd}.json').write_text(json.dumps(state, indent=2))
    record(f'PASS {cmd} as simulated {role}: {json.dumps(result)}')
    return result


def refused(cmd, role, payload, request=None):
    old = digest(state)
    try: command(cmd, role, payload, request=request)
    except Refused as e:
        need(digest(state) == old, 'refused command changed state')
        record('PASS rejected '+cmd+': '+str(e))
    else: raise AssertionError('unsafe command accepted: '+cmd)


def claim(n, role, request=None):
    worker = role in WORKERS
    p = dict(issue=n, queue_token=state['tasks'][str(n)]['queue_token'],
             resolved='economy' if worker else 'strong', model='luna' if worker else 'sol',
             adapter_revision='SIMULATED-plumbing-v1')
    return command('claim', role, p, request=request)['claim']['id'], p


try:
    round_n = create('Test round', ['agent-round','round:draft'], form(PM_capability_policy='auto'))
    roots = {role:create(role, ['agent-task','agent-root','to:'+role,'state:draft'],
             form(Capability_class='auto',Worker_child_budget=3,Independent_review_permission='none'),round_n)
             for role in sorted(LEADS)}
    refused('claim', 'software', {'issue':roots['software']})
    plan = prepared(api, config, round_n)
    command('authorize','human',{'issue':round_n},digest(plan))
    # Real GitHub compare-and-swap rejection against an outdated file SHA.
    stale = sha
    save(dict(state, plumbing_cas_probe=True))
    try:
        api.call(path,'PUT',dict(branch='agent-bus-state',sha=stale,message='Expected stale write rejection',
                 content=base64.b64encode(b'{"stale":true}').decode()))
    except urllib.error.HTTPError as e:
        need(e.code == 409, 'unexpected CAS response '+str(e.code)); record('PASS real GitHub stale SHA rejected with 409')
    else: raise AssertionError('stale SHA accepted')
    save(state)
    sw = roots['software']
    refused('claim','hardware',{'issue':sw})
    lead, claim_payload = claim(sw,'software',request='duplicate-'+run)
    replay = command('claim','software',claim_payload,request='duplicate-'+run)
    need(replay.get('claimed') is False and replay.get('duplicate'), 'duplicate granted another claim')
    refused('claim','software',claim_payload)
    children = {}
    for role in sorted(WORKERS):
        n=create(role,['agent-task','to:'+role,'state:draft'],form(Capability_class='auto'),sw)
        children[role]=n
        command('ready','software',dict(issue=n,parent=sw,claim=lead))
    command('wait','software',dict(issue=sw,claim=lead))
    for index,(role,n) in enumerate(children.items()):
        token,_=claim(n,role)
        command('block' if index == 1 else 'return',role,dict(issue=n,claim=token,result='Simulated worker evidence'))
        need(state['tasks'][str(sw)]['state'] == ('queued' if index == 2 else 'waiting'), 'fanin fired at wrong time')
    lead,_=claim(sw,'software')
    need(state['tasks'][str(sw)]['cycles'] == 2, 'unexpected lead invocations')
    for n in children.values(): command('close-child','software',dict(issue=n,claim=lead,result='Test-only disposition'))
    command('return','software',dict(issue=sw,claim=lead,result='Test batch reviewed'))
    for role,n in roots.items():
        if role == 'software': continue
        token,_=claim(n,role)
        command('return',role,dict(issue=n,claim=token,result='Simulated root result; no independent acceptance'))
    r=state['rounds'][str(round_n)]
    need(r['state']=='quiescent', 'PM barrier failed')
    payload=dict(issue=round_n,queue_token=r['queue_token'],resolved='strong',model='sol',adapter_revision='SIMULATED-plumbing-v1')
    final=command('pm-claim','pm',payload)
    refused('pm-claim','pm',payload)
    command('pm-close','pm',dict(issue=round_n,claim=final['claim']['id'],result='Plumbing test complete; no product acceptance'))
    command('reconcile','human',{})
    need(state['current'] is None, 'unexpected restart')
    need(all(api.issue(n)['state']=='closed' for n in created), 'test envelopes not closed')
    record('PASS all eight simulated roles completed; no model calls; no automatic restart')
finally:
    failures=[]
    for n in created:
        try: api.call(f'issues/{n}','PATCH',{'state':'closed'})
        except Exception as e: failures.append(f'issue {n}: {e}')
    if sha:
        try: api.call(path,'DELETE',dict(branch='agent-bus-state',sha=sha,message='Remove temporary plumbing ledger '+run))
        except Exception as e: failures.append('temporary ledger: '+str(e))
    (out/'cleanup.json').write_text(json.dumps({'issues':created,'failures':failures},indent=2))
    need(not failures, 'cleanup incomplete: '+str(failures))
    production,_=api.ledger()
    need(production['current'] is None and all(not r['enabled'] for r in production['roles'].values()), 'production isolation violated')
    record('PASS cleanup: test issues closed, temporary ledger deleted, production remains unbound')
