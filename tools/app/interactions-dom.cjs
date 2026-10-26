// Test adapter (Verification324): the production binding (app.mjs mountApp) and renderer
// (screen.mjs mountScreen) in a fresh isolated browser document per case, wired to one actual
// production Bridge per case (host/app/tests/interaction_component.rs, served line by line by
// the compiled unit-test executable). Typed/pasted input goes through Playwright's keyboard
// into the actual handlers. No Digital Tape app, native window, IPC, child, device or OS
// clipboard is used; the facade only carries calls/events and holds them where a case says.
// Arguments: contract.json (contract.py --emit), discovery cases (windows_discovery_r1 --emit),
// unit-test executable, frontend dir, output dir, source head.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const readline = require('node:readline');
const { spawn } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const [contractPath, discoveryPath, testExe, frontend, outDir, sourceHead] = process.argv.slice(2);
const contract = JSON.parse(fs.readFileSync(contractPath, 'utf8'));
const typedCards = Object.fromEntries(JSON.parse(fs.readFileSync(discoveryPath, 'utf8')).cases.map(c => [c.id, c]));
const card = (id, stderr = '') => ({ ...typedCards[id], stderr });
const diag = (marker, lines = 0) => `${marker}\n` + 'typed diagnostic stderr line\n'.repeat(lines);
const SUCCESS = { exit: 0, frames: 88200, stderr: '' };
const failure = stderr => ({ exit: 1, stderr });
const A = 'C:\\Music\\A', B = 'C:\\Music\\B', C = 'C:\\Music\\C';

class Server {
  constructor() {
    this.child = spawn(testExe, ['bridge::interaction_component::serve', '--exact', '--nocapture', '--test-threads=1'],
      { env: { ...process.env, DT_INTERACTION_SERVE: '1' }, stdio: ['pipe', 'pipe', 'inherit'] });
    this.waiting = [];
    this.chain = Promise.resolve();
    readline.createInterface({ input: this.child.stdout }).on('line', line => {
      // The test harness prints its own status before the first reply on the same line.
      const at = line.indexOf('@@ ');
      if (at >= 0) this.waiting.shift()(JSON.parse(line.slice(at + 3)));
    });
  }
  call(op, arg = null) {
    const run = () => new Promise(resolve => {
      this.waiting.push(resolve);
      this.child.stdin.write(JSON.stringify({ op, arg }) + '\n');
    });
    const p = this.chain.then(run);
    this.chain = p.catch(() => {});
    return p;
  }
  end() { this.child.stdin.write(JSON.stringify({ op: 'end' }) + '\n'); this.child.stdin.end(); }
}

// Installed in the test document: the host facade the production binding receives.
function installFacade() {
  const T = window.T = { log: [], queue: [], bgQueue: [], hold: false, holdCalls: new Set(), pending: [], cb: null, cbRef: null,
    subs: 0, inflight: 0, lastView: null, mutations: 0, observer: null };
  const deliver = v => { T.log.push({ event: 'app-state', label: v.label, view: v.view, checking: v.checking, card_line: v.card_line, delivered: !!T.cb });
    T.lastView = v; if (T.cb) T.cb(v); };
  T.flush = () => { while (T.queue.length) deliver(T.queue.shift()); };
  T.flushOrder = order => { const q = T.queue.splice(0); for (const i of order) deliver(q[i]); };
  T.flushBg = () => { while (T.bgQueue.length) deliver(T.bgQueue.shift()); };
  T.push = (views, bg) => { for (const v of views) (bg ? T.bgQueue : T.queue).push(v); if (!bg && !T.hold) T.flush(); };
  T.release = name => { const i = T.pending.findIndex(p => p.name === name); const [p] = T.pending.splice(i, 1); T.log.push({ resolved: name, which: p.seq }); p.resolve(p.result); };
  T.releaseLast = name => { let i = -1; T.pending.forEach((p, j) => { if (p.name === name) i = j; }); const [p] = T.pending.splice(i, 1); T.log.push({ resolved: name, which: p.seq }); p.resolve(p.result); };
  let seq = 0;
  const call = name => async (...args) => {
    const arg = args.length ? args[0] : null;
    const n = ++seq;
    T.log.push({ call: name, arg, seq: n });
    T.inflight++;
    const r = await window.rust(name, arg);
    T.inflight--;
    T.push(r.emitted, false);
    if (T.holdCalls.has(name)) return new Promise(resolve => T.pending.push({ name, seq: n, result: r.result, resolve }));
    return r.result;
  };
  T.host = { snapshot: call('snapshot'), set_label: call('set_label'), drop_paths: call('drop_paths'), start_over: call('start_over'), raw_details: call('raw_details'),
    async subscribe(cb) { T.subs++; T.cb = cb; T.cbRef = cb; T.log.push({ subscribe: true }); return () => { T.subs--; T.cb = null; T.log.push({ unsubscribe: true }); }; } };
  const vis = n => !!n && !n.hidden && getComputedStyle(n).display !== 'none' && n.getClientRects().length > 0;
  const nodePath = (root, node) => { const p = []; while (node && node !== root) { p.unshift([...node.parentNode.childNodes].indexOf(node)); node = node.parentNode; } return p; };
  T.obs = () => {
    const root = document.getElementById('app'), q = id => root.querySelector('#' + id);
    const make = q('make'), ae = document.activeElement;
    const o = { forbidden_nodes: [...root.querySelectorAll('ul,ol,li,table,tr,td,option,select,img,a,iframe,script,object,embed,svg')].map(n => n.localName),
      make_enabled: !!(T.lastView && T.lastView.make_enabled) || (make ? !make.disabled : false),
      focus: ae && ae !== document.body ? (ae.id || ae.localName) : 'body' };
    const screen = q('screen');
    if (!screen) return { ...o, dom_nodes: root.childNodes.length };
    const label = q('label'), details = q('details'), frames = q('length-text').dataset.frames;
    Object.assign(o, { state: screen.dataset.state, card_line: q('card').textContent, message: q('message').textContent,
      frames: frames === undefined ? null : Number(frames), label_value: label.value, utf8_bytes: new TextEncoder().encode(label.value).length,
      label_selection: [label.selectionStart, label.selectionEnd, label.selectionDirection], show_details_visible: vis(q('show-details')),
      reset_visible: vis(q('reset')), details_visible: vis(details), details_text: details.textContent,
      details_scroll: { element: details.scrollTop, page: document.scrollingElement.scrollTop } });
    const s = getSelection();
    if (s.rangeCount && details.contains(s.anchorNode) && details.contains(s.focusNode)) {
      o.dom_selection = [nodePath(details, s.anchorNode), s.anchorOffset, nodePath(details, s.focusNode), s.focusOffset];
      o.selection_text = s.toString();
    } else { o.dom_selection = null; o.selection_text = ''; }
    return o;
  };
  // Select `text` inside the details panel through the DOM Selection API.
  T.selectDetails = text => {
    const details = document.getElementById('details');
    const walker = document.createTreeWalker(details, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const i = n.data.indexOf(text);
      if (i >= 0) { const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + text.length); getSelection().removeAllRanges(); getSelection().addRange(r); return true; }
    }
    return false;
  };
}

async function runCase(browser, server, c, script) {
  const raw = { steps: [], rpc: [], captures: {} };
  const context = await browser.newContext({ viewport: { width: 800, height: 600 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.route('http://dt.test/**', route => {
    const name = new URL(route.request().url()).pathname.slice(1);
    if (name === '' || name === 'index.html')
      return route.fulfill({ contentType: 'text/html', body: '<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="style.css"></head><body><main id="app"></main></body></html>' });
    const types = { 'app.mjs': 'text/javascript', 'screen.mjs': 'text/javascript', 'style.css': 'text/css' };
    if (!types[name]) return route.fulfill({ status: 404, body: '' });
    return route.fulfill({ contentType: types[name], body: fs.readFileSync(path.join(frontend, name)) });
  });
  const rpc = async (op, arg = null) => { const r = await server.call(op, arg); raw.rpc.push({ op, arg, result: r.result, emitted: r.emitted }); return r; };
  await page.exposeFunction('rust', (op, arg) => rpc(op, arg));
  await page.goto('http://dt.test/index.html');
  await page.evaluate(installFacade);
  await rpc('new');
  const evaluate = (fn, arg) => page.evaluate(fn, arg);
  const idle = async () => { for (let i = 0; i < 2000; i++) { if (await evaluate(() => T.inflight === 0)) return; await new Promise(r => setTimeout(r, 2)); } throw new Error('host call never completed'); };
  const tick = () => evaluate(() => new Promise(r => setTimeout(r, 0)));
  const ctx = {
    page, rpc, evaluate, idle, tick,
    async mount({ holdSnapshot = false } = {}) {
      if (holdSnapshot) await evaluate(() => T.holdCalls.add('snapshot'));
      await evaluate(async () => { const { mountApp } = await import('/app.mjs'); T.mounted = mountApp(document.getElementById('app'), T.host).then(app => { T.app = app; }); });
      if (!holdSnapshot) { await evaluate(() => T.mounted); await ctx.settle(); }
    },
    // Settle: every host call answered, queued events delivered, held Promises resolved.
    async settle() {
      await idle();
      await evaluate(() => { T.flush(); for (const p of T.pending.splice(0)) { T.log.push({ resolved: p.name, which: p.seq }); p.resolve(p.result); } });
      await tick(); await idle(); await evaluate(() => T.flush()); await tick();
    },
    async bg(op, arg, { hold = false } = {}) { const r = await rpc(op, arg); await evaluate(([v, h]) => T.push(v, h), [r.emitted, hold]); await tick(); return r.result; },
    async type(text) { await page.focus('#label'); await page.keyboard.type(text); await idle(); },
    async paste(text) { await page.focus('#label'); await page.keyboard.insertText(text); await idle(); },
    async select(s, e, dir) { await evaluate(([s, e, dir]) => { const l = document.getElementById('label'); l.focus(); l.setSelectionRange(s, e, dir); }, [s, e, dir]); },
    async drop(paths) { await evaluate(p => T.app.dropPaths(p), paths); await idle(); await tick(); },
    async openDetails() { await page.click('#show-details'); await ctx.settle(); },
    async readDetails(text, { scroll = false } = {}) {
      await evaluate(([text, scroll]) => {
        const d = document.getElementById('details');
        d.focus({ preventScroll: true });
        if (!T.selectDetails(text)) throw new Error('selection text not in details: ' + text);
        if (scroll) document.scrollingElement.scrollTop = d.offsetTop + 120;
      }, [text, scroll]);
    },
    obs: () => evaluate(() => T.obs()),
    facts: async () => (await rpc('facts')).result,
  };
  const steps = script(ctx);
  if (steps.setup) await steps.setup();
  let before = steps.captureBeforeAt === undefined ? await ctx.obs() : null;
  if (steps.length !== c.steps.length) throw new Error(`script/frozen step count differ: ${c.id}`);
  for (let i = 0; i < steps.length; i++) {
    const mark = { step: c.steps[i], rpc_from: raw.rpc.length, log_from: await evaluate(() => T.log.length) };
    await steps[i]();
    raw.steps.push({ ...mark, rpc_to: raw.rpc.length, log_to: await evaluate(() => T.log.length), dom: await ctx.obs() });
    if (steps.captureBeforeAt === i) before = await ctx.obs();
  }
  let after = await ctx.obs();
  if (steps.finish) after = { ...after, ...(await steps.finish(before, after)) };
  raw.calls = await evaluate(() => T.log);
  raw.page_errors = errors;
  raw.captures = { before, after };
  await context.close();
  return { before, after, raw };
}

// Trace helpers over the actual coordinator trace (bridge.rs note()).
const count = (trace, from, event) => trace.slice(from).filter(e => e === event).length;

const S = {};
// ---- editing ----
S['E-ascii-caret'] = x => Object.assign([
  () => x.bg('cards', card('zero'), { hold: true }),
  async () => { await x.evaluate(() => T.flushBg()); await x.settle(); }], {
  async setup() { await x.mount(); await x.bg('cards', card('zero')); await x.type('Road Trip'); await x.settle(); await x.select(4, 4, 'none'); } });
S['E-ascii-backward-selection'] = x => Object.assign([
  () => x.bg('cards', card('one64'), { hold: true }),
  async () => { await x.evaluate(() => T.flushBg()); await x.settle(); }], {
  async setup() { await x.mount(); await x.bg('cards', card('zero')); await x.type('Road Trip'); await x.settle(); await x.select(0, 4, 'backward'); } });
const delayedCompletion = (prev, last, sel, outcome) => x => Object.assign([
  async () => { await x.evaluate(() => T.flushBg()); await x.settle(); }], {
  async setup() {
    await x.mount(); await x.drop([A]); await x.type(prev); await x.settle();
    await x.bg('check', outcome, { hold: true }); // emitted while the host still had the previous label
    await x.type(last); await x.settle(); await x.select(...sel);
  } });
S['E-two-byte-selection'] = delayedCompletion('é'.repeat(15), 'é', [2, 10, 'forward'], SUCCESS);
S['E-astral-caret'] = delayedCompletion('😀'.repeat(7), '😀', [6, 6, 'none'], failure('INGEST-DIAG'));
S['E-paste-exact-limit'] = x => Object.assign([
  async () => { await x.paste('x'.repeat(32)); await x.settle(); await x.select(32, 32, 'none'); },
  async () => { await x.evaluate(() => T.flushBg()); await x.bg('check', SUCCESS); await x.settle(); }], {
  captureBeforeAt: 0,
  async setup() { await x.mount(); await x.drop([A]); await x.bg('cards', card('zero')); await x.bg('cards', card('zero'), { hold: true }); } });
const rejected = (value, sel, attempt, background) => x => Object.assign([
  async () => { await x.paste(attempt); await x.tick(); },
  async () => { await background(x); await x.settle(); }], {
  async setup() { await x.mount(); await x.drop([A]); await x.bg('cards', card('zero')); await x.type(value); await x.settle(); await x.select(...sel); },
  async finish() { return { invalid_label_callbacks: (await x.evaluate(() => T.log)).filter(e => e.call === 'set_label' && (e.arg.includes('\0') || new TextEncoder().encode(e.arg).length > 32)).length }; } });
S['E-reject-ascii-excess'] = rejected('x'.repeat(32), [8, 16, 'forward'], 'x'.repeat(9), x => x.bg('cards', card('zero')));
S['E-reject-multibyte-excess'] = rejected('é'.repeat(16), [0, 8, 'backward'], 'é'.repeat(9), x => x.bg('check', SUCCESS));
S['E-reject-nul'] = rejected('Music', [2, 2, 'none'], '\0', x => x.bg('cards', card('one64')));
S['E-delete-to-empty'] = x => Object.assign([
  async () => { await x.page.keyboard.press('Backspace'); await x.idle(); await x.select(0, 0, 'none'); },
  async () => { await x.evaluate(() => T.flushOrder([1, 0])); await x.settle(); }], {
  captureBeforeAt: 0,
  async setup() { await x.mount(); await x.evaluate(() => { T.hold = true; }); await x.type('A'); } });
S['E-two-edits-reversed-acks'] = x => Object.assign([
  async () => { await x.paste('Old'); await x.page.keyboard.press('Control+A'); await x.paste('Latest 😀'); await x.select(9, 9, 'none'); },
  async () => { await x.evaluate(() => { T.flushOrder([1, 0]); T.releaseLast('set_label'); T.release('set_label'); }); await x.settle(); }], {
  captureBeforeAt: 0,
  async setup() { await x.mount(); await x.evaluate(() => { T.hold = true; T.holdCalls.add('set_label'); }); } });
S['E-late-initial-snapshot'] = x => Object.assign([
  () => x.mount({ holdSnapshot: true }),
  async () => { await x.evaluate(() => { T.hold = true; }); await x.type('New label'); await x.select(3, 7, 'forward'); },
  async () => { await x.evaluate(async () => { T.release('snapshot'); await T.mounted; T.hold = false; T.flush(); }); await x.settle(); }], {
  captureBeforeAt: 1,
  async setup() { await x.rpc('set_label', 'Old label'); } });
S['E-paste-replaces-astral-selection'] = x => Object.assign([
  async () => { await x.select(14, 16, 'forward'); await x.paste('abcd'); await x.settle(); await x.select(14, 18, 'backward'); },
  async () => { await x.bg('cards', card('zero-unprobed')); await x.drop([A]); await x.settle(); }], {
  captureBeforeAt: 0,
  async setup() { await x.mount(); await x.bg('cards', card('zero')); await x.type('😀'.repeat(8)); await x.settle(); } });

// ---- details ----
const LONG = 'INGEST-DIAG\n<plain>& text\n' + 'retained raw diagnostic line\n'.repeat(40);
S['D-ingest-poll'] = x => Object.assign([
  async () => { for (let i = 0; i < 3; i++) { await x.bg('cards', card('zero')); await x.settle(); } }], {
  async setup() { await x.mount(); await x.bg('cards', card('zero')); await x.drop([A]); await x.bg('check', failure(LONG)); await x.settle();
    await x.openDetails(); await x.readDetails('DIAG', { scroll: true }); } });
S['D-cards-check-snapshot'] = x => Object.assign([
  async () => { await x.bg('check', SUCCESS); await x.settle(); }], {
  async setup() { await x.mount(); await x.drop([A]); await x.bg('cards', card('enum-unavailable', diag('CARDS-DIAG current diagnostic', 40))); await x.settle();
    await x.openDetails(); await x.readDetails('current diagnostic', { scroll: true }); } });
S['D-combined-unchanged'] = x => Object.assign([
  async () => { for (let i = 0; i < 2; i++) { await x.bg('cards', card('enum-unavailable', diag('CARDS-DIAG'))); await x.settle(); } }], {
  async setup() { await x.mount(); await x.drop([A]); await x.bg('check', failure('INGEST-DIAG')); await x.bg('cards', card('enum-unavailable', diag('CARDS-DIAG'))); await x.settle();
    await x.openDetails(); await x.readDetails('INGEST-DIAG'); } });
S['D-copy-plain-selection'] = x => Object.assign([
  async () => { x.copied = await x.evaluate(() => getSelection().toString()); },
  async () => { await x.bg('cards', card('zero')); await x.settle(); },
  async () => { x.copiedAfter = await x.evaluate(() => getSelection().toString()); }], {
  async setup() { await x.mount(); await x.bg('cards', card('zero')); await x.drop([A]); await x.bg('check', failure('raw\r\n<img>& text\nlast line')); await x.settle();
    await x.openDetails(); await x.readDetails('<img>& text'); },
  async finish() { return { selection_tostring: [x.copied, x.copiedAfter] }; } });
const openIfNeeded = async x => { if (!(await x.obs()).details_visible && (await x.obs()).show_details_visible) await x.openDetails(); await x.settle(); };
S['D-changed-diagnostic'] = x => Object.assign([
  () => x.bg('cards', card('enum-unavailable', diag('CARDS-NEW'))),
  () => openIfNeeded(x)], {
  async setup() { await x.mount(); await x.bg('cards', card('enum-unavailable', diag('CARDS-OLD'))); await x.openDetails(); } });
S['D-cards-success-keeps-ingest'] = x => Object.assign([
  () => x.bg('cards', card('one64')),
  () => openIfNeeded(x)], {
  async setup() { await x.mount(); await x.drop([A]); await x.bg('check', failure('INGEST-CURRENT')); await x.bg('cards', card('enum-unavailable', diag('CARDS-FAILED'))); await x.settle(); await x.openDetails(); } });
// Problem offers Start over only (APP-1), so a fresh music check follows Start over and a new drop.
S['D-ingest-success-keeps-cards'] = x => Object.assign([
  async () => { await x.page.click('#reset'); await x.settle(); await x.drop([A]); await x.bg('check', SUCCESS); await x.settle(); },
  () => openIfNeeded(x)], {
  async setup() { await x.mount(); await x.drop([A]); await x.bg('check', failure('INGEST-FAILED')); await x.bg('cards', card('enum-unavailable', diag('CARDS-CURRENT'))); await x.settle(); await x.openDetails(); } });
S['D-reset-closes-music-details'] = x => Object.assign([
  () => x.page.click('#reset'),
  () => x.settle()], {
  async setup() { await x.mount(); await x.bg('cards', card('zero')); await x.type('Road Trip'); await x.drop([A]); await x.bg('check', failure('INGEST-OLD')); await x.settle(); await x.openDetails(); } });
S['D-late-details-response'] = x => Object.assign([
  () => x.bg('cards', card('enum-unavailable', diag('CARDS-NEW'))),
  async () => { await x.evaluate(() => T.holdCalls.delete('raw_details')); if ((await x.obs()).show_details_visible) await x.page.click('#show-details'); await x.idle(); await x.tick(); },
  async () => { await x.evaluate(() => T.release('raw_details')); await x.tick(); }], {
  async setup() { await x.mount(); await x.bg('cards', card('enum-unavailable', diag('CARDS-OLD'))); await x.evaluate(() => T.holdCalls.add('raw_details')); await x.page.click('#show-details'); await x.idle(); } });
S['D-dismiss-by-clear'] = x => Object.assign([
  () => x.bg('cards', card('one64')),
  async () => { await x.idle(); await x.evaluate(() => T.flush()); await x.tick(); },
  async () => { await x.evaluate(() => { for (const p of T.pending.splice(0)) p.resolve(p.result); }); await x.tick(); }], {
  async setup() { await x.mount(); await x.drop([A]); await x.bg('check', SUCCESS); await x.bg('cards', card('enum-unavailable', diag('CARDS-FAILED'))); await x.settle(); await x.openDetails();
    await x.evaluate(() => T.holdCalls.add('raw_details')); await x.page.click('#show-details'); await x.idle(); } });

// ---- composed ordering/lifetime ----
const typedLabel = async x => { await x.type('Road Trip'); await x.settle(); await x.select(4, 4, 'none'); };
const ready = async x => { await x.drop([A]); await x.bg('check', SUCCESS); await x.settle(); };
S['O-drop-check-card-ready'] = x => Object.assign([
  () => x.drop([A]),
  async () => { await x.bg('cards', card('zero')); await x.bg('cards', card('one64')); },
  async () => { await x.bg('check', SUCCESS); await x.settle(); }], {
  async setup() { await x.mount(); await typedLabel(x); },
  async finish(before, after) { const f = await x.facts(); return { accepted_folders: f.folders, check_requests: f.check_requests,
    label_unchanged: after.label_value === before.label_value && JSON.stringify(after.label_selection) === JSON.stringify(before.label_selection) }; } });
S['O-card-then-check-failure'] = x => Object.assign([
  () => x.drop([A]),
  () => x.bg('cards', card('one64')),
  async () => { await x.bg('check', failure('INGEST-DIAG')); await x.settle(); },
  () => openIfNeeded(x)], { async setup() { await x.mount(); await typedLabel(x); } });
S['O-check-failure-then-card'] = x => Object.assign([
  async () => { await x.bg('check', failure('INGEST-DIAG')); await x.settle(); },
  () => x.bg('cards', card('one64')),
  () => openIfNeeded(x)], { async setup() { await x.mount(); await typedLabel(x); await x.drop([A]); } });
S['O-check-success-card-failure'] = x => Object.assign([
  async () => { await x.bg('check', SUCCESS); await x.settle(); },
  () => x.bg('cards', card('enum-unavailable', diag('CARDS-DIAG'))),
  () => openIfNeeded(x)], { async setup() { await x.mount(); await typedLabel(x); await x.drop([A]); } });
// The window hides Start over while Checking; the coordinator's own start_over path is driven.
S['O-reset-while-checking'] = x => Object.assign([
  async () => { await x.drop([A]); await x.rpc('check_begin'); },
  async () => { x.mark = (await x.facts()).trace.length; await x.bg('start_over'); await x.settle(); },
  async () => { await x.bg('check_release', SUCCESS); await x.bg('check_duplicate', { index: 0, outcome: SUCCESS }); await x.settle(); }], {
  async setup() { await x.mount(); await typedLabel(x); },
  async finish() { const f = await x.facts(); const t = f.trace;
    const oldCleanup = t.indexOf('remove-owned-job', x.mark);
    return { accepted_folders: f.folders, late_publications: count(t, x.mark, 'completion-delivered'),
      replacement_before_old_cleanup: t.slice(x.mark, oldCleanup < 0 ? t.length : oldCleanup).filter(e => e === 'worker-enter').length, trace: t }; } });
S['O-reset-due-poll'] = x => Object.assign([
  () => x.rpc('poll_pause', card('one64')),
  async () => { await x.page.click('#reset'); await x.settle(); x.mark = (await x.facts()).trace.length; },
  async () => { await x.rpc('poll_resume'); await x.bg('snapshot'); await x.settle(); }], {
  async setup() { await x.mount(); await typedLabel(x); await ready(x); },
  async finish() { const f = await x.facts(); return { poll_workers: count(f.trace, x.mark, 'cards:worker-start'), max_concurrent: f.max_concurrent,
    foreign_cleanup: f.foreign_intact ? [] : ['jobs/foreign'], trace: f.trace }; } });
S['O-reset-inflight-poll'] = x => Object.assign([
  () => x.rpc('cards_block'),
  async () => { await x.page.click('#reset'); await x.settle(); },
  async () => { await x.bg('cards_release', card('zero')); await x.settle(); x.mark = (await x.facts()).trace.length; },
  async () => { await x.bg('cards_duplicate', card('zero')); await x.settle(); }], {
  async setup() { await x.mount(); await typedLabel(x); await ready(x); },
  async finish() { const f = await x.facts(); return { duplicate_publications: count(f.trace, x.mark, 'cards:published'), max_concurrent: f.max_concurrent, trace: f.trace }; } });
S['O-shutdown-due-poll'] = x => Object.assign([
  () => x.rpc('poll_pause', card('one64')),
  async () => { await x.bg('shutdown'); await x.settle(); x.mark = (await x.facts()).trace.length; },
  async () => { await x.rpc('poll_resume'); await x.settle(); }], {
  async setup() { await x.mount(); await typedLabel(x); },
  async finish() { const f = await x.facts(); return { poll_workers_after_stop: count(f.trace, x.mark, 'cards:worker-start'),
    late_publications: count(f.trace, x.mark, 'cards:published'), active_cards: f.cards_active, foreign_cleanup: f.foreign_intact ? [] : ['jobs/foreign'], trace: f.trace }; } });
S['O-shutdown-inflight'] = x => Object.assign([
  () => x.rpc('cards_block'),
  async () => { x.mark = (await x.facts()).trace.length; await x.bg('shutdown'); await x.settle(); },
  async () => { await x.bg('cards_duplicate', card('one64')); await x.settle(); }], {
  async setup() { await x.mount(); await typedLabel(x); await ready(x); },
  async finish() { const f = await x.facts(); const t = f.trace, stop = t.indexOf('stop-polls', x.mark);
    const terminal = t.indexOf('cards:child-terminal', x.mark), cleanup = t.indexOf('cards:remove-owned-job', x.mark);
    return { late_publications: count(t, x.mark, 'cards:published'), cleanup_before_terminal: cleanup >= 0 && (terminal < 0 || cleanup < terminal) ? 1 : 0,
      new_workers_after_stop: count(t, stop, 'cards:worker-start') + count(t, stop, 'worker-enter'), foreign_cleanup: f.foreign_intact ? [] : ['jobs/foreign'], trace: t }; } });
S['O-supersede-and-destroy'] = x => Object.assign([
  async () => { await x.drop([A]); await x.rpc('check_begin'); await x.drop([B, C]); },
  async () => { await x.bg('check_release', SUCCESS); await x.bg('check', SUCCESS); await x.settle(); },
  async () => { x.mark = (await x.facts()).trace.length; await x.bg('check_duplicate', { index: 0, outcome: SUCCESS }); await x.settle(); },
  async () => { await x.evaluate(() => T.holdCalls.add('raw_details')); await x.page.click('#show-details'); await x.idle();
    await x.evaluate(() => { const root = document.getElementById('app'); T.app.destroy();
      T.observer = new MutationObserver(m => { T.mutations += m.length; }); T.observer.observe(root, { subtree: true, childList: true, characterData: true, attributes: true }); }); },
  async () => { const r = await x.rpc('snapshot'); await x.evaluate(v => { T.push([v], false); if (T.cbRef) T.cbRef(v); for (const p of T.pending.splice(0)) p.resolve(p.result); }, r.result); await x.tick(); await x.tick(); }], {
  async setup() { await x.mount(); await x.bg('cards', card('enum-unavailable', diag('CARDS-DIAG'))); await typedLabel(x); },
  async finish() { const f = await x.facts(); const t = f.trace; const second = t.indexOf('worker-enter', t.indexOf('worker-enter') + 1); const cleanup = t.indexOf('remove-owned-job');
    const page = await x.evaluate(() => ({ mutations_after_destroy: T.mutations, remaining_subscriptions: T.subs, last_view: T.lastView }));
    return { accepted_folders: f.folders, check_requests: f.check_requests, replacement_before_old_cleanup: second >= 0 && second < cleanup ? 1 : 0,
      late_publications: count(t, x.mark, 'completion-delivered'), ...page, trace: t }; } });

async function main() {
  fs.mkdirSync(outDir, { recursive: true });
  const server = new Server();
  const browser = await chromium.launch({ executablePath: process.env.TEST_BROWSER_EXE, headless: true, chromiumSandbox: true });
  const cases = {}, raw = {};
  const version = browser.version();
  try {
    for (const c of contract.cases) {
      if (process.env.DT_ONLY && !c.id.startsWith(process.env.DT_ONLY)) continue;
      console.error('case', c.id);
      const r = await runCase(browser, server, c, S[c.id]);
      raw[c.id] = r.raw;
      cases[c.id] = { before: r.before, after: r.after, event_order: c.steps, steps_ref: `interactions.raw.json#${c.id}.steps`,
        raw_ref: `interactions.raw.json#${c.id}`, actual_production_calls_ref: `interactions.raw.json#${c.id}.calls`, producer_expected_trace_used: false };
    }
  } finally { await browser.close(); server.end(); }
  // The renderer/binding actually served, by content (the Bridge's blobs are in source-blobs.txt).
  const blobs = ['app.mjs', 'screen.mjs', 'style.css'].map(f => {
    const b = fs.readFileSync(path.join(frontend, f));
    return { path: path.join(frontend, f).replaceAll('\\', '/'), sha256: crypto.createHash('sha256').update(b).digest('hex'),
      git_blob: crypto.createHash('sha1').update(`blob ${b.length}\0`).update(b).digest('hex') }; });
  const result = { source_head: sourceHead, evidence_class: 'production renderer/binding/coordinator controlled interaction',
    adapter_refs: ['tools/app/interactions-dom.cjs', 'host/app/tests/interaction_component.rs'], raw_refs: ['interactions.raw.json'],
    source_blobs: blobs, commands: [process.argv.slice(1).join(' ')], actual_emission_refs: ['interactions.raw.json#<case>.rpc[].emitted'],
    entry_points: ['mountApp', 'mountScreen', 'Bridge'], native_ui: false, real_child_runs: 0, live_metadata_runs: 0,
    shipping_fake_route: false, reference_ui_model: false, browser: version, cases };
  fs.writeFileSync(path.join(outDir, 'interactions.raw.json'), JSON.stringify(raw, null, 1) + '\n');
  fs.writeFileSync(path.join(outDir, 'interactions.json'), JSON.stringify(result, null, 1) + '\n');
}
main().catch(e => { console.error(e); process.exit(1); });
