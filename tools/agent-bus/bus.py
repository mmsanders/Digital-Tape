#!/usr/bin/env python3
"""Agent Bus controller. No model calls. Issues hold scope; CAS ledger holds receipts.

All writers use the same Actions concurrency group and GitHub Contents SHA CAS.
Labels are a recoverable projection, never a lock or authorization credential.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / '.github/agent-bus'
LEADS = {'software', 'hardware', 'verification', 'surge'}
WORKERS = {'worker-chatgpt', 'worker-claude', 'worker-grok'}
RANK = {'economy': 1, 'balanced': 2, 'strong': 3, 'frontier': 4}
ALLOWED = {r: set(RANK) - {'economy'} for r in LEADS}
ALLOWED.update({r: {'economy', 'balanced'} for r in WORKERS})
ALLOWED.update({r: {'strong', 'frontier'} for r in ('pm', 'verification')})
STATES = {'draft', 'ready', 'queued', 'working', 'waiting', 'review', 'blocked', 'protocol-error'}
RUNTIME_FILE = CONFIG / 'runtimes.json'
STATE_BRANCH = 'agent-bus-state'


class Refused(ValueError):
    pass


def need(test, why):
    if not test:
        raise Refused(why)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def fields(body):
    out = {}
    for match in re.finditer(r'(?ms)^### ([^\n]+)\n(.*?)(?=^### |\Z)', body or ''):
        name, value = match[1].strip(), match[2].strip()
        need(name not in out, 'duplicate form heading: ' + name)
        out[name] = value
    return out


def labels(issue):
    return {v if isinstance(v, str) else v['name'] for v in issue['labels']}


def one_label(issue, prefix):
    found = [v[len(prefix):] for v in labels(issue) if v.startswith(prefix)]
    need(len(found) == 1, 'expected exactly one ' + prefix + ' label')
    return found[0]


def signature(issue, parent):
    # Title/body edits, reparenting and review-kind changes invalidate approved scope.
    return digest([issue['number'], issue['title'], issue.get('body') or '', parent,
                   'kind:independent-review' in labels(issue)])


def runtime(config, role):
    entry = config['roles'].get(role, {})
    need(entry.get('enabled') is True and entry.get('actor') and entry.get('instance'),
         'runtime unbound/disabled: ' + role)
    need(entry.get('transport', {}).get('kind') in {'manual', 'pr-doorbell'}, 'unsupported transport')
    return entry


def validate_config(config):
    need(set(config['roles']) == {'pm', *LEADS, *WORKERS}, 'runtime role catalog mismatch')
    actors = set()
    for role, entry in config['roles'].items():
        if not entry.get('enabled'):
            continue
        runtime(config, role)
        actor = entry['actor'].lower()
        need(actor != config['human'].lower() and actor not in actors,
             'enabled roles require distinct non-human GitHub identities')
        actors.add(actor)
        need(entry.get('provider') in config['providers'], 'unknown provider')
        if entry['transport']['kind'] == 'pr-doorbell':
            need(type(entry['transport'].get('pr')) is int and entry['transport']['pr'] > 0,
                 'doorbell needs a designated positive PR number')


def capability(config, role, requested, risk='ordinary', resolved=None, model=None):
    entry = runtime(config, role)
    need(requested == 'auto' or requested in ALLOWED[role], 'capability outside role band')
    need(risk in {'ordinary', 'high-consequence'}, 'invalid Decision risk')
    target = requested
    if requested == 'auto':
        target = 'economy' if role in WORKERS else 'strong'
        if role not in WORKERS and risk == 'high-consequence':
            target = 'frontier'
    mapping = config['providers'][entry['provider']]
    need(mapping.get(target), f'{role}: provider cannot supply {target}; explicit reassignment required')
    if resolved is not None:
        need(resolved in ALLOWED[role] and RANK[resolved] >= RANK[target], 'silent downgrade/invalid capability')
        family = mapping.get(resolved)
        need(family and model and (model == family or model.startswith(family + '-')),
             'actual model does not attest configured capability family')
    return target


class GitHub:
    def __init__(self, repo, token):
        need(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo), 'invalid repository')
        self.repo, self.token = repo, token

    def call(self, path, method='GET', data=None):
        req = urllib.request.Request('https://api.github.com/repos/' + self.repo + '/' + path,
            data=None if data is None else json.dumps(data).encode(), method=method,
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None

    def pages(self, path):
        result = []
        for page in range(1, 1001):
            data = self.call(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            need(isinstance(data, list), 'expected paginated list')
            result.extend(data)
            if len(data) < 100:
                return result
        raise Refused('pagination bound exceeded; no truncated decisions')

    def issue(self, number):
        i = self.call(f'issues/{int(number)}')
        need('pull_request' not in i, 'PRs are not task envelopes')
        return i

    def parent(self, number):
        try:
            return self.call(f'issues/{int(number)}/parent')['number']
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def children(self, number):
        return self.pages(f'issues/{int(number)}/sub_issues')

    def rounds(self):
        return self.pages('issues?state=open&labels=agent-round')

    def ledger(self):
        file = self.call(f'contents/state.json?ref={STATE_BRANCH}')
        return json.loads(base64.b64decode(file['content'])), file['sha']

    def save(self, state, sha):
        # A stale writer receives 409; never retry blindly or merge competing claims.
        data = base64.b64encode((json.dumps(state, indent=2) + '\n').encode()).decode()
        return self.call('contents/state.json', 'PUT', dict(branch=STATE_BRANCH, sha=sha,
            message='Agent Bus receipt ' + state['updated_at'], content=data))


def empty_state(config):
    return dict(version=2, updated_at=now(), infrastructure='installed; instances unbound',
                roles=copy.deepcopy(config['roles']), current=None, rounds={}, tasks={}, receipts={})


def environment_protected(api, config):
    env = api.call('environments/michael-round-gate')
    reviewers = [x for rule in env.get('protection_rules', []) if rule.get('type') == 'required_reviewers'
                 for x in rule.get('reviewers', [])]
    need(len(reviewers) == 1 and reviewers[0].get('type') == 'User' and
         reviewers[0].get('reviewer', {}).get('login', '').lower() == config['human'].lower(),
         'michael-round-gate must require Michael alone; missing protection fails closed')
    need(env.get('can_admins_bypass') is False, 'disable administrator bypass on human gate')
    return env


def prepared(api, config, number):
    """Snapshot before human approval, then recomputed after it. No scope reread drift."""
    validate_config(config)
    runtime(config, 'pm')
    issue = api.issue(number)
    need(issue['state'] == 'open' and 'agent-round' in labels(issue), 'round is not open')
    need(one_label(issue, 'round:') == 'draft', 'round is not draft')
    need(api.parent(number) is None, 'round cannot have a parent')
    need([x['number'] for x in api.rounds()] == [number], 'exactly one open round required')
    rf = fields(issue.get('body'))
    capability(config, 'pm', rf.get('PM capability policy', ''), rf.get('Decision risk', 'ordinary'))
    roots = api.children(number)
    need(1 <= len(roots) <= 4, 'round needs 1–4 roots')
    plan = dict(number=number, title=issue['title'], scope=signature(issue, None),
                pm_capability=rf['PM capability policy'], risk=rf.get('Decision risk', 'ordinary'), roots=[])
    seen = set()
    for root in roots:
        role = one_label(root, 'to:')
        need(role in LEADS and role not in seen, 'exactly one root per lead, no worker roots')
        seen.add(role)
        need(root['state'] == 'open' and {'agent-root', 'agent-task'} <= labels(root), 'invalid root')
        need(one_label(root, 'state:') == 'draft' and api.parent(root['number']) == number,
             'root must be draft and attached to this round')
        need(not api.children(root['number']), 'prepare children only inside an authorized round')
        f = fields(root.get('body'))
        requested, risk = f.get('Capability class', ''), f.get('Decision risk', 'ordinary')
        capability(config, role, requested, risk)
        budget = int(f.get('Worker child budget', '6'))
        reviews = int(f.get('Independent-review service budget', '1'))
        need(0 <= budget <= 12 and 0 <= reviews <= 2, 'invalid approved child/review budget')
        eligibility = f.get('Independent review permission', 'none')
        need(eligibility in {'none', 'tooling-or-hardware', 'landed-independent-tests'}, 'invalid review permission')
        need(eligibility == 'none' or role in {'software', 'hardware'}, 'role cannot request lateral review')
        plan['roots'].append(dict(number=root['number'], title=root['title'], role=role,
            scope=signature(root, number), parent=number, requested=requested, risk=risk,
            budget=budget, review_budget=reviews, review_permission=eligibility))
    plan['roots'].sort(key=lambda r: r['number'])
    plan['config_hash'] = digest(config)
    return plan


class Controller:
    def __init__(self, api, config, state, actor, request, run):
        self.api, self.config, self.state = api, config, state
        self.actor, self.request, self.run = actor, request, run
        validate_config(config)
        need(re.fullmatch(r'[A-Za-z0-9_-]{8,100}', request), 'request_id must be 8–100 safe characters')

    def role(self, role):
        entry = runtime(self.config, role)
        need(entry['actor'].lower() == self.actor.lower(), 'actor is not bound to ' + role)

    def active(self):
        r = self.state['rounds'].get(str(self.state['current']))
        need(r and r['state'] == 'active', 'no authorized active round')
        need(r['plan']['config_hash'] == digest(self.config), 'runtime policy changed during round')
        self.scope_round(r)
        for task in self.state['tasks'].values():
            if task['round'] == r['number']:
                self.scope(task)
        return r

    def scope_round(self, r):
        i = self.api.issue(r['number'])
        need(i['state'] == 'open' and signature(i, self.api.parent(i['number'])) == r['plan']['scope'],
             'approved round edited/closed/reparented')
        need({x['number'] for x in self.api.rounds()} == {r['number']}, 'another open round exists')
        need({x['number'] for x in self.api.children(i['number'])} == {x['number'] for x in r['plan']['roots']},
             'approved root membership changed')
        for root in r['plan']['roots']:
            self.scope(self.state['tasks'][str(root['number'])])

    def scope(self, task):
        i = self.api.issue(task['number'])
        need(signature(i, self.api.parent(i['number'])) == task['scope'], 'task scope/parent changed')
        need(i['state'] == 'open' or task['state'] == 'closed', 'task closed outside controller')
        if task['role'] not in LEADS or task.get('service'):
            need(not self.api.children(task['number']), 'nested child work prohibited')
        return i

    def task(self, number):
        self.active()
        t = self.state['tasks'].get(str(number))
        need(t and t['round'] == self.state['current'], 'task outside current round')
        self.scope(t)
        return t

    def owned(self, task, claim):
        self.role(task['role'])
        need(task['state'] == 'working' and task.get('claim', {}).get('id') == claim and
             task['claim']['actor'] == self.actor, 'no matching active claim')

    def queue(self, task):
        need(task.get('cycles', 0) < 3, 'three-invocation fuse exhausted; human abort/replan required')
        capability(self.config, task['role'], task['requested'], task.get('risk', 'ordinary'))
        task.update(state='queued', destination=task['role'], cycles=task.get('cycles', 0) + 1,
                    queue_token=f"{self.run}-{self.request}-{task['number']}-{task.get('cycles', 0)+1}")
        task.pop('claim', None)

    def authorize(self, p, approved_digest):
        need(self.actor.lower() == self.config['human'].lower(), 'only Michael requests round authorization')
        environment_protected(self.api, self.config)
        need(not self.state['current'], 'previous round is not closed')
        plan = prepared(self.api, self.config, p['issue'])
        need(approved_digest and digest(plan) == approved_digest, 'plan changed after approval snapshot')
        key = str(p['issue'])
        need(key not in self.state['rounds'], 'round replay forbidden')
        self.state['current'] = p['issue']
        r = dict(number=p['issue'], title=plan['title'], state='active', plan=plan,
                 approved_digest=approved_digest, authorization_run=self.run, approved_at=now())
        self.state['rounds'][key] = r
        for root in plan['roots']:
            t = dict(root, round=p['issue'], phase='fanout', state='draft')
            self.state['tasks'][str(t['number'])] = t
            self.queue(t)
        return {'authorized': True, 'plan_digest': approved_digest}

    def ready(self, p):
        parent = self.task(p['parent'])
        need(parent['role'] in LEADS and not parent.get('service'), 'parent must be lead root')
        self.owned(parent, p['claim'])
        i = self.api.issue(p['issue'])
        need(i['state'] == 'open' and self.api.parent(i['number']) == parent['number'] and
             'agent-task' in labels(i) and 'agent-root' not in labels(i), 'invalid native child')
        need(not self.api.children(i['number']), 'nested child work prohibited')
        children = self.api.children(parent['number'])
        need(len(children) <= parent['budget'], 'approved child budget exceeded (closed children count)')
        service = 'kind:independent-review' in labels(i)
        role = one_label(i, 'to:')
        prior = self.state['tasks'].get(str(i['number']))
        if prior:
            self.scope(prior)
            need(prior['state'] in {'review', 'blocked'}, 'child is not eligible for rework')
            role = prior['role']
        else:
            need(one_label(i, 'state:') in {'draft', 'ready'}, 'child must begin draft/ready')
        if service:
            need(parent['role'] in {'software', 'hardware'} and role == 'verification' and
                 parent['review_permission'] != 'none', 'independent review not authorized in approved root')
            f = fields(i.get('body'))
            need(f.get('Review eligibility') == parent['review_permission'] and f.get('Coverage evidence'),
                 'missing approved eligibility/evidence for independent review')
            count = sum('kind:independent-review' in labels(c) for c in children)
            need(count <= parent['review_budget'], 'approved independent-review budget exceeded')
        else:
            need(role in WORKERS, 'normal child must target worker')
        f = fields(i.get('body'))
        t = prior or dict(number=i['number'], title=i['title'], role=role, parent=parent['number'],
            round=parent['round'], scope=signature(i, parent['number']), service=service,
            requested=f.get('Capability class', ''), risk=f.get('Decision risk', 'ordinary'), state='ready')
        self.state['tasks'][str(i['number'])] = t
        self.queue(t)
        return {'queued': t['number'], 'queue_token': t['queue_token']}

    def claim(self, p):
        t = self.task(p['issue'])
        self.role(t['role'])
        need(t['state'] == 'queued' and p['queue_token'] == t['queue_token'], 'queue already consumed/stale')
        capability(self.config, t['role'], t['requested'], t.get('risk', 'ordinary'), p['resolved'], p['model'])
        t['claim'] = dict(id=self.request, actor=self.actor, instance=self.config['roles'][t['role']]['instance'],
            resolved=p['resolved'], model=p['model'], adapter_revision=p['adapter_revision'], run=self.run)
        t['state'] = 'working'
        return {'claimed': True, 'issue': t['number'], 'claim': copy.deepcopy(t['claim']), 'scope': t['scope']}

    def finish(self, p, state):
        t = self.task(p['issue'])
        self.owned(t, p['claim'])
        children = self.api.children(t['number'])
        if state == 'waiting':
            need(t['role'] in LEADS and not t.get('service') and children, 'only roots with children may wait')
            need(all(str(c['number']) in self.state['tasks'] for c in children), 'undispatched child remains')
        elif t['role'] in LEADS and not t.get('service'):
            need(all(self.state['tasks'].get(str(c['number']), {}).get('state') == 'closed' for c in children),
                 'close/disposition all children before root return')
        if state != 'waiting':
            need(isinstance(p.get('result'), str) and p['result'].strip(), 'result/evidence required')
            t['result'] = p['result']
            t['destination'] = 'pm' if not t.get('service') and t['role'] in LEADS else self.state['tasks'][str(t['parent'])]['role']
        t['state'] = state
        return {'state': state}

    def close_child(self, p):
        t = self.task(p['issue'])
        need(t['role'] in WORKERS or t.get('service'), 'only child disposition here')
        parent = self.task(t['parent'])
        self.owned(parent, p['claim'])
        need(t['state'] in {'review', 'blocked'}, 'child has not returned')
        need(p.get('result'), 'disposition rationale required')
        t.update(state='closed', disposition=p['result'])
        return {'closed': t['number']}

    def reconcile(self):
        if not self.state['current']:
            return
        r = self.state['rounds'][str(self.state['current'])]
        if r['state'] != 'active':
            return
        self.active()
        roots = [self.state['tasks'][str(v['number'])] for v in r['plan']['roots']]
        all_closed = True
        for root in roots:
            children = self.api.children(root['number'])
            known = []
            for child in children:
                t = self.state['tasks'].get(str(child['number']))
                if not t:
                    all_closed = False
                    continue
                self.scope(t)
                known.append(t)
                all_closed = all_closed and t['state'] == 'closed'
            if root['state'] == 'waiting' and len(known) == len(children) and children and all(
                    c['state'] in {'review', 'blocked', 'closed'} for c in known):
                root['phase'] = 'fanin'
                self.queue(root)
        if all_closed and all(t['state'] in {'review', 'blocked'} and t['destination'] == 'pm' for t in roots):
            r.update(state='quiescent', queue_token=f'{self.run}-{self.request}-pm-final')

    def pm_claim(self, p):
        self.role('pm')
        r = self.state['rounds'].get(str(p['issue']))
        need(r and r['state'] == 'quiescent' and r['number'] == self.state['current'], 'no unclaimed PM barrier')
        self.scope_round(r)
        need(p['queue_token'] == r['queue_token'], 'stale PM signal')
        capability(self.config, 'pm', r['plan']['pm_capability'], r['plan']['risk'], p['resolved'], p['model'])
        r.update(state='pm-review', claim=dict(id=self.request, actor=self.actor, resolved=p['resolved'],
            model=p['model'], adapter_revision=p['adapter_revision'], run=self.run))
        return {'claimed': True, 'claim': r['claim'], 'issue': r['number']}

    def pm_close(self, p):
        self.role('pm')
        r = self.state['rounds'].get(str(p['issue']))
        need(r and r['state'] == 'pm-review' and r['claim']['id'] == p['claim'], 'no PM final claim')
        need(p.get('result'), 'executive synthesis link/text required')
        r.update(state='closed', result=p['result'])
        self.state['current'] = None
        return {'closed': r['number']}

    def abort(self, p):
        need(self.actor.lower() == self.config['human'].lower(), 'only Michael may abort')
        r = self.state['rounds'].get(str(p['issue']))
        need(r and self.state['current'] == p['issue'] and p.get('result'), 'active round/reason required')
        r.update(state='aborted', result=p['result'])
        for t in self.state['tasks'].values():
            if t['round'] == r['number'] and t['state'] != 'closed':
                t.update(state='blocked', result='Round aborted by Michael; prior evidence retained.')
        self.state['current'] = None
        return {'aborted': r['number']}

    def execute(self, command, p, approved_digest=None):
        fingerprint = digest([self.actor, command, p, approved_digest])
        old = self.state['receipts'].get(self.request)
        if old:
            need(old['fingerprint'] == fingerprint, 'request_id reused with different content/actor')
            return {'duplicate': True, 'claimed': False, 'original_run': old['run']}
        if command == 'authorize': result = self.authorize(p, approved_digest)
        elif command == 'ready': result = self.ready(p)
        elif command == 'claim': result = self.claim(p)
        elif command in {'return', 'block', 'wait'}:
            result = self.finish(p, {'return': 'review', 'block': 'blocked', 'wait': 'waiting'}[command])
        elif command == 'close-child': result = self.close_child(p)
        elif command == 'pm-claim': result = self.pm_claim(p)
        elif command == 'pm-close': result = self.pm_close(p)
        elif command == 'abort': result = self.abort(p)
        elif command == 'reconcile': result = {'reconciled': True}
        else: raise Refused('unknown command')
        self.reconcile()
        self.state['receipts'][self.request] = dict(fingerprint=fingerprint, run=self.run, result=result)
        self.state['updated_at'] = now()
        self.state['roles'] = copy.deepcopy(self.config['roles'])
        self.state['infrastructure'] = 'installed; bindings configured' if any(x.get('enabled') for x in self.config['roles'].values()) else 'installed; instances unbound'
        return result


def projection(api, state):
    """Idempotent ledger -> labels. One PATCH replaces lifecycle/destination together."""
    for t in state['tasks'].values():
        i = api.issue(t['number'])
        keep = {v for v in labels(i) if not v.startswith(('state:', 'to:', 'phase:', 'round:'))}
        extra = {'agent-task', 'to:' + t['destination'], 'round:active'}
        if t['state'] != 'closed': extra.add('state:' + t['state'])
        if t.get('phase'): extra |= {'agent-root', 'phase:' + t['phase']}
        target = sorted(keep | extra)
        issue_state = 'closed' if t['state'] == 'closed' else i['state']
        if target != sorted(labels(i)) or issue_state != i['state']:
            api.call(f"issues/{t['number']}", 'PATCH', {'labels': target, 'state': issue_state})
    for r in state['rounds'].values():
        i = api.issue(r['number'])
        keep = {v for v in labels(i) if not v.startswith('round:')}
        target = sorted(keep | {'agent-round', 'round:' + r['state']})
        patch = {'labels': target}
        if r['state'] in {'closed', 'aborted'}: patch['state'] = 'closed'
        if target != sorted(labels(i)) or patch.get('state', i['state']) != i['state']:
            api.call(f"issues/{r['number']}", 'PATCH', patch)


def doorbells(api, config, state):
    """Optional PR wakeup after a committed receipt; duplicate delivery is harmless."""
    queued = [(t['role'], t) for t in state['tasks'].values() if t['state'] == 'queued']
    queued += [('pm', r) for r in state['rounds'].values() if r['state'] == 'quiescent']
    for role, item in queued:
        transport = runtime(config, role)['transport']
        if transport['kind'] != 'pr-doorbell': continue
        pr = int(transport['pr'])
        info = api.call(f'pulls/{pr}')
        need(info['state'] == 'open', 'designated signal PR must be open')
        marker = '<!-- AGENT-BUS-SIGNAL:' + item['queue_token'] + ' -->'
        comments = api.pages(f'issues/{pr}/comments')
        if any(c['user']['login'] == 'github-actions[bot]' and marker in c['body'] for c in comments): continue
        api.call(f'issues/{pr}/comments', 'POST', {'body': marker + '\nAgent Bus mailbox changed for `' + role +
            '`: issue #' + str(item['number']) + '. Fetch the ledger and obtain an exclusive claim receipt before work. This comment alone grants no authority.'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['preflight', 'execute', 'install', 'inspect'])
    args = parser.parse_args()
    config = json.loads(RUNTIME_FILE.read_text())
    api = GitHub(os.environ['GITHUB_REPOSITORY'], os.environ['GH_TOKEN'])
    command = os.environ.get('BUS_COMMAND', 'reconcile')
    p = json.loads(os.environ.get('BUS_PAYLOAD', '{}'))
    need(isinstance(p, dict), 'payload must be an object')
    if args.mode == 'install':
        validate_config(config)
        for name in ['agent-round', 'agent-root', 'agent-task', 'kind:independent-review'] + [
                'to:' + r for r in config['roles']] + ['state:' + s for s in STATES] + [
                'round:' + s for s in ['draft', 'pending', 'active', 'quiescent', 'pm-review', 'closed', 'aborted']] + ['phase:fanout', 'phase:fanin']:
            try: api.call('labels', 'POST', {'name': name, 'color': '6e7781', 'description': 'Agent Bus v2; see docs/AGENT-BUS.md'})
            except urllib.error.HTTPError as e:
                if e.code != 422: raise
        try: api.call('git/ref/heads/' + STATE_BRANCH)
        except urllib.error.HTTPError as e:
            if e.code != 404: raise
            head = api.call('git/ref/heads/main')['object']['sha']
            api.call('git/refs', 'POST', {'ref': 'refs/heads/' + STATE_BRANCH, 'sha': head})
        try:
            state, sha = api.ledger()
            if state['current']:
                need(state['rounds'][str(state['current'])]['plan']['config_hash'] == digest(config),
                     'cannot change runtime bindings during an active round')
            state['roles'] = copy.deepcopy(config['roles'])
            state['updated_at'] = now()
            state['infrastructure'] = 'installed; bindings configured' if any(v['enabled'] for v in config['roles'].values()) else 'installed; instances unbound'
            api.save(state, sha)
        except urllib.error.HTTPError as e:
            if e.code != 404: raise
            data = base64.b64encode((json.dumps(empty_state(config), indent=2) + '\n').encode()).decode()
            api.call('contents/state.json', 'PUT', {'branch': STATE_BRANCH, 'message': 'Initialize empty Agent Bus receipt ledger', 'content': data})
        print('Installed labels and ledger; no runtime was bound or invoked.')
        return
    if args.mode == 'inspect':
        report = {'runtimes_enabled': [r for r, v in config['roles'].items() if v['enabled']]}
        for endpoint in ['pages', 'environments/michael-round-gate']:
            try: report[endpoint] = api.call(endpoint)
            except urllib.error.HTTPError as e: report[endpoint] = {'http_status': e.code}
        print(json.dumps(report, indent=2)); return
    if args.mode == 'preflight':
        if command != 'authorize': return
        need(os.environ['BUS_ACTOR'].lower() == config['human'].lower(), 'only Michael requests approval')
        environment_protected(api, config)
        plan = prepared(api, config, int(p['issue']))
        print(json.dumps(plan, indent=2))
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out: out.write('digest=' + digest(plan) + '\n')
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
            out.write('## Round approval snapshot\n\n```json\n' + json.dumps(plan, indent=2) + '\n```\n')
        return
    state, sha = api.ledger()
    c = Controller(api, config, state, os.environ['BUS_ACTOR'], os.environ['BUS_REQUEST_ID'], os.environ['GITHUB_RUN_ID'])
    result = c.execute(command, p, os.environ.get('BUS_APPROVED_DIGEST'))
    if not result.get('duplicate'): api.save(state, sha)
    # Issue projection can fail after durable commit. Reconcile repairs it, never reclaims.
    Path('bus-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    projection(api, state)
    doorbells(api, config, state)


if __name__ == '__main__':
    try: main()
    except (Refused, KeyError, ValueError, urllib.error.HTTPError) as e:
        print('AGENT BUS REFUSED: ' + str(e), file=sys.stderr)
        sys.exit(1)
