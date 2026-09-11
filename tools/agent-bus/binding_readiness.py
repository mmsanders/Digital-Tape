#!/usr/bin/env python3
"""Read-only Phase 1 binding checklist. Declared evidence is not remote certification."""
import json
from pathlib import Path
from bus import validate_config, Refused

root=Path(__file__).resolve().parents[2]
folder=root/'.github/agent-bus'
config=json.loads((folder/'runtimes.json').read_text())
roster=json.loads((folder/'phase1-roster.json').read_text())
gaps=[]
try: validate_config(config)
except Refused as e: gaps.append('runtime configuration: '+str(e))
for role, target in roster['roles'].items():
    entry=config['roles'][role]
    missing=[k for k in ('instance_url','github_actor','trigger_id','adapter_revision','wake_test_evidence') if not target.get(k)]
    if not entry.get('actor') or not entry.get('instance'): missing.append('runtime actor/instance')
    if target.get('github_actor') and entry.get('actor') != target['github_actor']: missing.append('matching actor')
    if entry.get('phase1',{}).get('selected') is not True: missing.append('trial selection')
    tiers=['economy','balanced'] if target['capability']=='economy-or-balanced' else [target['capability']]
    if not any(config['providers'][entry['provider']].get(t) for t in tiers): missing.append('provider capability mapping')
    if missing: gaps.append(role+': '+', '.join(missing))
for role in roster['reserved_disabled_roles']:
    if config['roles'][role]['enabled']: gaps.append(role+': reserved role unexpectedly enabled')
print(json.dumps({'check':'documentary readiness only; no account created, no secret read, no remote proof',
                  'missing':gaps,'ready_for_binding_review':not gaps},indent=2))
raise SystemExit(1 if gaps else 0)
