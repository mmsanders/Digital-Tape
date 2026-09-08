(function (root) {
  'use strict';
  const roles = [
    ['pm', 'Program Manager', 'ChatGPT Work'],
    ['software', 'Software Lead', 'Claude Code'],
    ['hardware', 'Hardware Lead', 'Claude Code'],
    ['verification', 'Verification Lead', 'ChatGPT Work · independent'],
    ['surge', 'Surge Lead', 'Bounded assignment'],
    ['worker-chatgpt', 'OpenAI worker', 'Instance to be connected'],
    ['worker-claude', 'Claude worker', 'Instance to be connected'],
    ['worker-grok', 'Grok worker', 'Instance to be connected']
  ];
  function build(snapshot) {
    if (!snapshot || snapshot.version !== 2 || !snapshot.roles || !snapshot.tasks || !snapshot.rounds ||
        !Number.isFinite(Date.parse(snapshot.updated_at))) throw new Error('Invalid ledger snapshot');
    const round = snapshot.current == null ? null : snapshot.rounds[String(snapshot.current)];
    if (snapshot.current != null && !round) throw new Error('Current round is absent from ledger');
    const tasks = Object.values(snapshot.tasks).filter(t => round && t.round === round.number);
    const order = ['protocol-error', 'blocked', 'working', 'queued', 'ready', 'waiting', 'review', 'draft'];
    const cards = roles.map(([id, label, seat]) => {
      const runtime = snapshot.roles[id] || {};
      // Role remains the executing owner after a result is routed back to a parent.
      const own = tasks.filter(t => t.role === id);
      const roots = own.filter(t => t.phase);
      const children = tasks.filter(t => roots.some(p => p.number === t.parent));
      let state = order.find(s => own.some(t => t.state === s)) || 'idle';
      if (id === 'pm' && round) state = ({active:'waiting',quiescent:'review','pm-review':'working'})[round.state] || round.state;
      if (!runtime.enabled || !runtime.actor || !runtime.instance) state = 'unbound';
      return {id,label,seat,runtime,state,own,children};
    });
    return {cards,round,updatedAt:snapshot.updated_at,infrastructure:snapshot.infrastructure};
  }
  const exported = {build,roles};
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  else root.BusDashboard = exported;
})(typeof globalThis !== 'undefined' ? globalThis : this);
