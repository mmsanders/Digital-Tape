'use strict';
const LEDGER = 'https://raw.githubusercontent.com/mmsanders/Digital-Tape/agent-bus-state/state.json';
const GITHUB = 'https://github.com/mmsanders/Digital-Tape';
const stateNames = {unbound:'Not connected',ready:'Ready for validation',queued:'Queued',working:'Working',waiting:'Waiting for batch',review:'Returned for review',blocked:'Blocked',idle:'Idle',draft:'Draft',closed:'Closed','protocol-error':'Protocol error'};
let timer, busy = false, lastSuccess;
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}
function taskNode(task) {
  const node = el('div', null, 'bucket');
  const title = el('a', '#' + task.number + ' ' + task.title);
  if (Number.isSafeInteger(task.number) && task.number > 0) title.href = GITHUB + '/issues/' + task.number;
  node.append(title, el('p', (stateNames[task.state] || task.state) + ' · ' + task.role + ' → ' + task.destination, 'muted'));
  node.append(el('p', 'Invocation ' + (task.cycles || 0) + '/3 · requested ' + task.requested, 'muted'));
  if (task.claim) node.append(el('p', task.claim.resolved + ' · ' + task.claim.model, 'mono muted'));
  if (task.result) node.append(el('p', task.result, 'muted'));
  return node;
}
function card(data) {
  const node = el('article', null, 'card');
  const row = el('div', null, 'row'), identity = el('div');
  identity.append(el('div',data.seat,'seat'),el('h2',data.label));
  row.append(identity,el('span',stateNames[data.state] || data.state,'chip'));
  node.append(row);
  node.append(el('p',data.runtime.enabled ? 'Instance: ' + data.runtime.instance : 'No instance bound. No work will dispatch to this role.', 'muted'));
  for (const task of data.own) node.append(taskNode(task));
  if (data.children.length) {
    node.append(el('p','Direct children · grouped by native parent','seat'));
    for (const task of data.children) node.append(taskNode(task));
  }
  if (!data.own.length) node.append(el('p','No task in the current round.','muted'));
  return node;
}
function render(snapshot) {
  const data = BusDashboard.build(snapshot);
  const meta = document.getElementById('meta');
  meta.replaceChildren(el('span','Phase 0 signed','pill'),el('span',data.round ? 'Round #' + data.round.number + ' · ' + data.round.state : 'No active round','pill'));
  const tree = document.getElementById('tree');
  const leads = el('div',null,'leads'), workers = el('div',null,'leads');
  for (const item of data.cards.slice(1,5)) leads.append(card(item));
  for (const item of data.cards.slice(5)) workers.append(card(item));
  tree.replaceChildren(card(data.cards[0]),el('div',null,'spine'),leads,el('p','Worker mailboxes','seat'),workers);
  tree.setAttribute('aria-busy','false');
  document.getElementById('warn').replaceChildren(el('div',data.infrastructure + '. Ledger changed ' + new Date(data.updatedAt).toLocaleString() + '. This reports recorded state, not a process heartbeat.','warn'));
}
async function refresh() {
  clearTimeout(timer);
  if (busy || document.hidden) return;
  busy = true;
  const controller = new AbortController(), timeout = setTimeout(() => controller.abort(),15000);
  try {
    const response = await fetch(LEDGER,{cache:'no-cache',signal:controller.signal});
    if (!response.ok) throw new Error('Ledger request failed (HTTP ' + response.status + ')');
    render(await response.json());
    lastSuccess = new Date();
    document.getElementById('live').textContent = 'Fetched ' + lastSuccess.toLocaleTimeString();
  } catch (error) {
    document.getElementById('warn').replaceChildren(el('div',error.message + '. ' + (lastSuccess ? 'Displayed data is stale; last successful fetch ' + lastSuccess.toLocaleString() + '.' : 'State is unknown; no live activity is inferred.'),'warn'));
    document.getElementById('live').textContent = 'Unavailable';
    document.getElementById('tree').setAttribute('aria-busy','false');
  } finally {
    clearTimeout(timeout); busy = false;
    if (!document.hidden) timer = setTimeout(refresh,60000);
  }
}
document.addEventListener('visibilitychange', () => {clearTimeout(timer); if (!document.hidden) refresh();});
refresh();
