'use strict';
const params = new URLSearchParams(location.search);
const replayMode = params.get('replay') === '34302460952';
const plumbingRun = params.get('plumbing');
const testRun = plumbingRun && /^[1-9][0-9]{0,19}$/.test(plumbingRun) ? plumbingRun : null;
const LEDGER = 'https://raw.githubusercontent.com/mmsanders/Digital-Tape/agent-bus-state/' + (testRun ? 'plumbing-' + testRun + '.json' : 'state.json');
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
  node.id = 'role-' + data.id;
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
function renderOverview(data) {
  const overview = document.getElementById('overview');
  function node(item) {
    const link = el('a',null,'flow-node');
    link.href = '#role-' + item.id;
    link.dataset.state = item.state;
    link.append(el('strong',item.label),el('span',stateNames[item.state] || item.state));
    const parents = [...new Set(item.own.filter(t=>t.parent && !t.phase).map(t=> {
      const parent = data.cards.find(c=>c.own.some(p=>p.number===t.parent));
      return parent ? parent.label : 'Parent #' + t.parent;
    }))];
    if (parents.length) link.append(el('span','Reports to ' + parents.join(', ')));
    return link;
  }
  const pm = el('div',null,'flow-pm'), leads = el('div',null,'flow-group'), workers = el('div',null,'flow-group');
  pm.append(node(data.cards[0]));
  data.cards.slice(1,5).forEach(c=>leads.append(node(c)));
  data.cards.slice(5).forEach(c=>workers.append(node(c)));
  overview.replaceChildren(pm,el('div',null,'flow-connector'),leads,el('p','Workers · parent shown when assigned','seat flow-label'),workers);
  overview.setAttribute('aria-busy','false');
}
function render(snapshot) {
  const data = BusDashboard.build(snapshot);
  renderOverview(data);
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
  if (replayMode || busy || document.hidden) return;
  busy = true;
  const controller = new AbortController(), timeout = setTimeout(() => controller.abort(),15000);
  try {
    const response = await fetch(LEDGER,{cache:'no-cache',signal:controller.signal});
    if (!response.ok) throw new Error('Ledger request failed (HTTP ' + response.status + ')');
    render(await response.json());
    lastSuccess = new Date();
    document.getElementById('live').textContent = 'Fetched ' + lastSuccess.toLocaleTimeString();
  } catch (error) {
    document.getElementById('warn').replaceChildren(el('div',error.message + '. ' + (testRun ? 'Temporary test data may not exist yet or may have been cleaned up. ' : '') + (lastSuccess ? 'Displayed data is stale; last successful fetch ' + lastSuccess.toLocaleString() + '.' : 'State is unknown; no live activity is inferred.'),'warn'));
    document.getElementById('live').textContent = 'Unavailable';
    document.getElementById('tree').setAttribute('aria-busy','false');
    document.getElementById('overview').setAttribute('aria-busy','false');
  } finally {
    clearTimeout(timeout); busy = false;
    if (!document.hidden) timer = setTimeout(refresh,60000);
  }
}
document.getElementById('view-mode').textContent = replayMode ?
  'RECORDED TEST REPLAY · 9 September 2026 · simulated agents, not live work.' : testRun ?
  'LIVE SIMULATED TEST ' + testRun + ' · production is separate.' : 'LIVE PRODUCTION · select a test above to watch simulated activity.';
document.addEventListener('visibilitychange', () => {clearTimeout(timer); if (!document.hidden) refresh();});
async function replay() {
  let playTimer;
  const button = document.getElementById('replay-play'), slider = document.getElementById('replay-step');
  function pause() { clearInterval(playTimer); playTimer=null; button.textContent='Play replay'; }
  try {
    const response = await fetch('replay-34302460952.json');
    if (!response.ok) throw Error('Replay unavailable');
    const record = await response.json();
    if (record.kind !== 'recorded-simulation' || !record.frames.length) throw Error('Invalid replay');
    record.frames.forEach(f=>BusDashboard.build(f.state));
    const frames=record.frames;
    slider.max=frames.length-1;
    document.getElementById('replay-controls').hidden=false;
    function show() {
      const index=Number(slider.value), state=frames[index].state;
      render(state);
      document.getElementById('warn').replaceChildren();
      document.getElementById('live').textContent='Recorded replay';
      document.getElementById('replay-caption').textContent='Step '+(index+1)+' of '+frames.length+' · recorded '+new Date(state.updated_at).toLocaleTimeString();
    }
    slider.addEventListener('input',()=>{pause();show();});
    button.addEventListener('click',()=>{
      if(playTimer) {pause();return;}
      if(Number(slider.value)>=frames.length-1) slider.value=0;
      show(); button.textContent='Pause replay';
      playTimer=setInterval(()=>{
        if(Number(slider.value)>=frames.length-1) {pause();return;}
        slider.value=Number(slider.value)+1;show();
      },1200);
    });
    document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
    show();
  } catch(error) { document.getElementById('view-mode').textContent='Replay unavailable: '+error.message; }
}
if (replayMode) replay(); else refresh();
