#!/usr/bin/env python3
"""Cheap CLI transport; never launches a model or includes credentials in receipts."""
import argparse
import json
import subprocess
import uuid
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', default='mmsanders/Digital-Tape')
    sub = p.add_subparsers(dest='action', required=True)
    send = sub.add_parser('send')
    send.add_argument('command')
    send.add_argument('payload_file', type=Path)
    send.add_argument('--request-id', default=None)
    mailbox = sub.add_parser('mailbox')
    mailbox.add_argument('role')
    args = p.parse_args()
    if args.action == 'send':
        payload = json.loads(args.payload_file.read_text())
        request = args.request_id or str(uuid.uuid4())
        subprocess.run(['gh','workflow','run','agent-bus.yml','--repo',args.repo,'--ref','main',
            '--raw-field','command='+args.command,'--raw-field','request_id='+request,
            '--raw-field','payload='+json.dumps(payload)],check=True)
        print(json.dumps({'request_id':request,'run_title':'Agent Bus · '+args.command+' · '+request,
            'next':'Read the matching run receipt artifact. A duplicate receipt never grants a new claim.'}))
    else:
        import base64
        raw = subprocess.check_output(['gh','api',f'repos/{args.repo}/contents/state.json?ref=agent-bus-state'],text=True)
        state = json.loads(base64.b64decode(json.loads(raw)['content']))
        binding = state['roles'].get(args.role,{})
        if not binding.get('enabled'):
            print(json.dumps({'role':args.role,'enabled':False,'work':[]}));return
        if args.role == 'pm':
            work=[r for r in state['rounds'].values() if r['number']==state['current'] and r['state']=='quiescent']
        else:
            work=[t for t in state['tasks'].values() if t['round']==state['current'] and t['role']==args.role and t['state']=='queued']
        print(json.dumps({'role':args.role,'enabled':True,'work':work},indent=2))


if __name__ == '__main__': main()
