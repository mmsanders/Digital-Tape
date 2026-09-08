import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

from bus import GitHub

from bus import Controller, Refused, capability, digest, empty_state, environment_protected, fields, prepared, projection, validate_config


def form(**values):
    return '\n\n'.join('### ' + k.replace('_', ' ') + '\n\n' + str(v) for k, v in values.items())


def issue(n, ls, body, parent=None):
    return dict(number=n, title=f'Task {n}', labels=ls, body=body, state='open', parent=parent)


class Fake:
    def __init__(self):
        self.data = {
            1: issue(1, ['agent-round', 'round:draft'], form(PM_capability_policy='auto')),
            2: issue(2, ['agent-task', 'agent-root', 'to:software', 'state:draft'],
                     form(Capability_class='auto', Worker_child_budget=6, Independent_review_permission='none'), 1)}
        self.env = {'can_admins_bypass': False, 'protection_rules': [{'type': 'required_reviewers',
            'reviewers': [{'type': 'User', 'reviewer': {'login': 'mmsanders'}}]}]}

    def issue(self, n): return copy.deepcopy(self.data[n])
    def parent(self, n): return self.data[n]['parent']
    def children(self, n): return [self.issue(i) for i, v in self.data.items() if v['parent'] == n]
    def rounds(self): return [self.issue(i) for i, v in self.data.items() if 'agent-round' in v['labels'] and v['state'] == 'open']
    def call(self, path, method='GET', data=None):
        if path.startswith('environments/'): return copy.deepcopy(self.env)
        if path.startswith('issues/') and method == 'PATCH':
            self.data[int(path.split('/')[1])].update(data); return data
        raise AssertionError((path, method, data))


class BusTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).parents[2] / '.github/agent-bus/runtimes.json').read_text())
        for role, r in self.config['roles'].items():
            r.update(enabled=True, actor=role+'-bot', instance=role+'-test', provider='openai')
        self.api = Fake()
        self.state = empty_state(self.config)
        self.count = 0

    def run_command(self, cmd, actor, p, approval=None, request=None):
        self.count += 1
        # Simulates CAS transaction: exception discards changes, no side effects.
        next_state = copy.deepcopy(self.state)
        c = Controller(self.api, self.config, next_state, actor, request or f'request-{self.count:04}', str(self.count))
        result = c.execute(cmd, p, approval)
        self.state = next_state
        projection(self.api, self.state)
        return result

    def start(self):
        d = digest(prepared(self.api, self.config, 1))
        self.run_command('authorize', 'mmsanders', {'issue':1}, d)

    def claim(self, n, role, request=None):
        t = self.state['tasks'][str(n)]
        target = 'sol' if role not in {'worker-chatgpt','worker-claude','worker-grok'} else 'luna'
        result = self.run_command('claim', role+'-bot', dict(issue=n, queue_token=t['queue_token'],
            resolved='strong' if target=='sol' else 'economy', model=target, adapter_revision='test'), request=request)
        return result['claim']['id']

    def child(self, n=3, parent=2, role='worker-chatgpt'):
        self.api.data[n] = issue(n, ['agent-task', 'to:'+role, 'state:draft'], form(Capability_class='auto'), parent)

    def test_complete_round_fanout_fanin_single_pm_claim_no_restart(self):
        self.start(); lead = self.claim(2,'software')
        for n in (3,4):
            self.child(n)
            self.run_command('ready','software-bot',dict(issue=n,parent=2,claim=lead))
        self.run_command('wait','software-bot',dict(issue=2,claim=lead))
        a = self.claim(3,'worker-chatgpt')
        self.run_command('return','worker-chatgpt-bot',dict(issue=3,claim=a,result='evidence 3'))
        self.assertEqual(self.state['tasks']['2']['state'],'waiting')
        b = self.claim(4,'worker-chatgpt')
        self.run_command('block','worker-chatgpt-bot',dict(issue=4,claim=b,result='missing input'))
        self.assertEqual(self.state['tasks']['2']['state'],'queued')
        self.assertEqual(self.state['tasks']['2']['cycles'],2)
        lead = self.claim(2,'software')
        for n in (3,4): self.run_command('close-child','software-bot',dict(issue=n,claim=lead,result='disposition'))
        self.run_command('return','software-bot',dict(issue=2,claim=lead,result='root result'))
        r = self.state['rounds']['1']; self.assertEqual(r['state'],'quiescent')
        result = self.run_command('pm-claim','pm-bot',dict(issue=1,queue_token=r['queue_token'],resolved='strong',model='sol',adapter_revision='test'))
        with self.assertRaises(Refused): self.run_command('pm-claim','pm-bot',dict(issue=1,queue_token=r['queue_token'],resolved='strong',model='sol',adapter_revision='test'))
        self.run_command('pm-close','pm-bot',dict(issue=1,claim=result['claim']['id'],result='executive summary'))
        self.run_command('reconcile','mmsanders',{})
        self.assertIsNone(self.state['current'])
        self.assertEqual(self.state['rounds']['1']['state'],'closed')

    def test_no_work_with_unbound_instances(self):
        self.config['roles']['software']['enabled']=False
        with self.assertRaisesRegex(Refused,'unbound'): prepared(self.api,self.config,1)

    def test_human_gate_missing_reviewers_or_admin_bypass_fails_closed(self):
        for bad in ({'protection_rules':[]},dict(self.api.env,can_admins_bypass=True)):
            self.api.env=bad
            with self.assertRaises(Refused): environment_protected(self.api,self.config)

    def test_approval_snapshot_rejects_edit_while_waiting(self):
        d=digest(prepared(self.api,self.config,1))
        self.api.data[2]['title']+=' extra scope'
        with self.assertRaisesRegex(Refused,'changed after approval'): self.run_command('authorize','mmsanders',{'issue':1},d)

    def test_only_human_can_request_authorization(self):
        d=digest(prepared(self.api,self.config,1))
        with self.assertRaisesRegex(Refused,'only Michael'): self.run_command('authorize','software-bot',{'issue':1},d)

    def test_labels_cannot_forge_authorization(self):
        self.api.data[1]['labels']=['agent-round','round:active','round:authorized']
        self.api.data[2]['labels']=['agent-task','agent-root','state:queued','to:software']
        with self.assertRaisesRegex(Refused,'no authorized'): self.run_command('claim','software-bot',{'issue':2})

    def test_exclusive_claim_and_replay(self):
        self.start(); token=self.state['tasks']['2']['queue_token']
        p=dict(issue=2,queue_token=token,resolved='strong',model='sol',adapter_revision='test')
        first=self.run_command('claim','software-bot',p,request='same-request')
        self.assertTrue(first['claimed'])
        second=self.run_command('claim','software-bot',p,request='same-request')
        self.assertTrue(second['duplicate']); self.assertFalse(second['claimed'])
        with self.assertRaisesRegex(Refused,'consumed'): self.run_command('claim','software-bot',p)
        with self.assertRaisesRegex(Refused,'reused'): self.run_command('claim','hardware-bot',p,request='same-request')

    def test_wrong_identity_cannot_claim(self):
        self.start()
        with self.assertRaisesRegex(Refused,'not bound'): self.run_command('claim','hardware-bot',{'issue':2})

    def test_reparented_child_cannot_disappear_from_barrier(self):
        self.start(); claim=self.claim(2,'software'); self.child()
        self.run_command('ready','software-bot',dict(issue=3,parent=2,claim=claim))
        self.api.data[3]['parent']=None
        with self.assertRaisesRegex(Refused,'scope/parent'): self.run_command('reconcile','mmsanders',{})

    def test_unknown_closed_child_prevents_root_return(self):
        self.start(); claim=self.claim(2,'software'); self.child(); self.api.data[3]['state']='closed'
        with self.assertRaisesRegex(Refused,'all children'): self.run_command('return','software-bot',dict(issue=2,claim=claim,result='done'))

    def test_invalid_native_depth_and_wrong_parent_owner(self):
        self.start(); claim=self.claim(2,'software'); self.child(); self.child(4,parent=3)
        with self.assertRaisesRegex(Refused,'nested'): self.run_command('ready','software-bot',dict(issue=3,parent=2,claim=claim))
        del self.api.data[4]
        with self.assertRaisesRegex(Refused,'not bound'): self.run_command('ready','hardware-bot',dict(issue=3,parent=2,claim=claim))

    def test_low_approved_budget_is_enforced(self):
        self.api.data[2]['body']=form(Capability_class='auto',Worker_child_budget=1)
        self.start(); claim=self.claim(2,'software'); self.child(); self.child(4)
        with self.assertRaisesRegex(Refused,'budget exceeded'): self.run_command('ready','software-bot',dict(issue=3,parent=2,claim=claim))

    def test_self_service_review_requires_approved_root_permission(self):
        self.start(); claim=self.claim(2,'software'); self.child(role='verification')
        self.api.data[3]['labels'].append('kind:independent-review')
        with self.assertRaisesRegex(Refused,'not authorized'): self.run_command('ready','software-bot',dict(issue=3,parent=2,claim=claim))

    def test_review_service_returns_only_to_requesting_hardware_lead(self):
        self.api.data[2]['labels']=['agent-root','agent-task','state:draft','to:hardware']
        self.api.data[2]['body']=form(Capability_class='auto',Independent_review_permission='tooling-or-hardware')
        self.start(); lead=self.claim(2,'hardware'); self.child(role='verification')
        self.api.data[3]['labels'].append('kind:independent-review')
        self.api.data[3]['body']=form(Capability_class='auto',Review_eligibility='tooling-or-hardware',Coverage_evidence='tooling review')
        self.run_command('ready','hardware-bot',dict(issue=3,parent=2,claim=lead))
        review=self.claim(3,'verification')
        self.run_command('return','verification-bot',dict(issue=3,claim=review,result='finding'))
        self.assertEqual(self.state['tasks']['3']['destination'],'hardware')

    def test_cycle_fuse_never_closes_evidence_automatically(self):
        self.start(); lead=self.claim(2,'software'); self.child()
        self.run_command('ready','software-bot',dict(issue=3,parent=2,claim=lead))
        worker=self.claim(3,'worker-chatgpt')
        self.run_command('return','worker-chatgpt-bot',dict(issue=3,claim=worker,result='result'))
        self.state['tasks']['3']['cycles']=3
        with self.assertRaisesRegex(Refused,'fuse exhausted'): self.run_command('ready','software-bot',dict(issue=3,parent=2,claim=lead))
        self.assertEqual(self.api.data[3]['state'],'open')

    def test_pm_cannot_claim_ordinary_root_and_early_return_cannot_wake_pm(self):
        self.start()
        with self.assertRaises(Refused): self.run_command('claim','pm-bot',{'issue':2})
        with self.assertRaises(Refused): self.run_command('pm-claim','pm-bot',{'issue':1})

    def test_config_actor_separation_and_strong_opus(self):
        self.config['roles']['software']['provider']='anthropic'
        self.assertEqual(capability(self.config,'software','strong',resolved='strong',model='opus'),'strong')
        with self.assertRaisesRegex(Refused,'cannot supply frontier'): capability(self.config,'software','frontier')
        with self.assertRaisesRegex(Refused,'downgrade'): capability(self.config,'software','strong',resolved='balanced',model='sonnet')
        self.config['roles']['hardware']['actor']='software-bot'
        with self.assertRaisesRegex(Refused,'distinct'): validate_config(self.config)

    def test_payload_model_and_risk_are_not_silently_accepted(self):
        with self.assertRaises(Refused): capability(self.config,'verification','economy')
        with self.assertRaises(Refused): capability(self.config,'worker-chatgpt','frontier')
        with self.assertRaises(Refused): capability(self.config,'pm','auto','high-consequence','strong','sol')
        with self.assertRaises(Refused): fields('### Capability class\nstrong\n### Capability class\neconomy')

    def test_projection_is_repairable_and_not_queue_authority(self):
        self.start(); self.api.data[2]['labels']=['agent-task','state:working','to:pm']
        projection(self.api,self.state)
        self.assertIn('state:queued',self.api.data[2]['labels'])
        self.assertIn('to:software',self.api.data[2]['labels'])

    def test_second_round_and_edited_config_block_work(self):
        self.start(); self.api.data[10]=issue(10,['agent-round','round:draft'],'')
        with self.assertRaises(Refused): self.run_command('claim','software-bot',{'issue':2})
        del self.api.data[10];self.config['roles']['software']['instance']='changed'
        with self.assertRaisesRegex(Refused,'policy changed'): self.run_command('claim','software-bot',{'issue':2})

    def test_surge_is_bounded_lead_with_no_verification_service_authority(self):
        self.api.data[2]['labels']=['agent-root','agent-task','state:draft','to:surge']
        self.start(); lead=self.claim(2,'surge'); self.child()
        self.run_command('ready','surge-bot',dict(issue=3,parent=2,claim=lead))
        self.assertEqual(self.state['tasks']['3']['parent'],2)

    def test_human_abort_preserves_results_and_never_restarts(self):
        self.start(); self.run_command('abort','mmsanders',dict(issue=1,result='stop'))
        self.assertIsNone(self.state['current'])
        self.assertEqual(self.state['tasks']['2']['state'],'blocked')

    def test_contents_compare_and_swap_rejects_second_writer(self):
        api = GitHub('mmsanders/Digital-Tape', 'unused-test-token')
        committed = {'sha': 'initial', 'state': None}
        def server(path, method, data):
            self.assertEqual(path, 'contents/state.json')
            self.assertEqual(method, 'PUT')
            if data['sha'] != committed['sha']:
                raise urllib.error.HTTPError('test', 409, 'conflict', {}, None)
            committed.update(sha='next',state=data['content'])
            return {'content':{'sha':'next'}}
        with patch.object(api, 'call', side_effect=server):
            api.save(self.state, 'initial')
            first = committed['state']
            with self.assertRaises(urllib.error.HTTPError): api.save(self.state, 'initial')
            self.assertEqual(first, committed['state'])

    def test_pagination_includes_items_past_first_page(self):
        api = GitHub('mmsanders/Digital-Tape', 'unused-test-token')
        with patch.object(api, 'call', side_effect=[list(range(100)),[100]]):
            self.assertEqual(api.pages('issues?state=open'),list(range(101)))


if __name__ == '__main__': unittest.main()
