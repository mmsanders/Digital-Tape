#!/usr/bin/env bash
set -euo pipefail

# STAGED ONLY. Running this mutates repository labels; do not run until Michael
# explicitly authorizes Agent Bus activation.
#
# Usage:
#   tools/agent-bus/bootstrap-labels.sh owner/repo

repo="${1:?usage: bootstrap-labels.sh owner/repo}"

create() {
  local name="$1" color="$2" description="$3"
  gh label create "$name" --repo "$repo" --color "$color" --description "$description" --force
}

# Object types
create 'agent-task'              '5319E7' 'Authoritative Agent Bus task Issue'
create 'agent-root'              '5319E7' 'PM-authored lead root for one round'
create 'agent-round'             '5319E7' 'Bounded human-authorized Agent Bus round'
create 'kind:independent-review' '8250DF' 'Typed independent Verification service edge'

# Destinations
create 'to:pm'             '0E8A16' 'Return to Program Manager; never a queued mailbox'
create 'to:software'       '0E8A16' 'Software Lead mailbox'
create 'to:hardware'       '0E8A16' 'Hardware Lead mailbox'
create 'to:verification'   '0E8A16' 'Verification Lead mailbox'
create 'to:worker-chatgpt' '0E8A16' 'ChatGPT chat worker mailbox when adapter enabled'
create 'to:worker-grok'    '0E8A16' 'Grok worker mailbox when adapter enabled'

# Task lifecycle
create 'state:draft'          'D4C5F9' 'Prepared but not dispatchable'
create 'state:ready'          'FBCA04' 'Requests cheap bus validation; agents never add queued'
create 'state:queued'         '1D76DB' 'Bus-issued dispatch capability'
create 'state:working'        '1D76DB' 'Claimed by destination'
create 'state:waiting'        'C2E0C6' 'Expensive parent idle behind fan-in barrier'
create 'state:review'         '0E8A16' 'Returned one hierarchy level upward'
create 'state:blocked'        'D93F0B' 'Cannot proceed within current authority'
create 'state:protocol-error' 'B60205' 'Invalid envelope; do not execute'

# Root phases
create 'phase:fanout' 'C5DEF5' 'Lead decomposition/delegation pass'
create 'phase:fanin'  'C5DEF5' 'Lead batched integration/review pass'

# Round lifecycle
create 'round:draft'      'D4C5F9' 'Prepared round awaiting Michael'
create 'round:pending'    'D4C5F9' 'Prepared root held behind human gate'
create 'round:authorized' '0E8A16' 'Protected workflow recorded Michael approval'
create 'round:active'     '1D76DB' 'Current active round/tree'
create 'round:quiescent'  'FBCA04' 'All roots returned; PM final synthesis may run once'
create 'round:pm-review'  '8250DF' 'PM claimed final executive synthesis'
create 'round:closed'     '6E7781' 'Round summary delivered; no automatic restart'

echo "Agent Bus labels installed in $repo"
