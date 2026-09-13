const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('index.html', 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes = Object.fromEntries(['board','meta','warn','roadmap'].map(id => [id, {innerHTML:'',textContent:''}]));
let mode = 'ok';
let requests = [];
const ctx = vm.createContext({document:{hidden:false,getElementById:id=>nodes[id]},AbortSignal,Date,Set,Number,String,Math,
  setInterval:(_,ms)=>assert.equal(ms,300000),
  fetch:async url=>{
    requests.push(url);
    if(mode==='fail') return {ok:false,status:403,json:async()=>({message:'<img src=x onerror=alert(1)>'})};
    const page=Number(new URL(url).searchParams.get('page'));
    const verify=url.includes('digital-tape-verification');
    const items=verify ? [{number:4,title:'Verify',labels:[{name:'verification-lead'}]}] : page===1
      ? Array.from({length:100},(_,i)=>({number:i,pull_request:{},labels:[{name:'pm'}]}))
      : [{number:55,title:'<PM> & watch',labels:[{name:'pm'}]}];
    return {ok:true,json:async()=>items};
  }});
vm.runInContext(source,ctx);

// The roadmap bar is a claim about how far Phase 1 has come, so it is worth the same
// scepticism as a gate: it must be computed from the stage table, must not round a
// package up, and must not survive a stage whose rung is unstated.
const rungs = vm.runInContext('PHASE1.stages.map(s => s.rung)', ctx);
const top = vm.runInContext('RUNGS.length', ctx);
const expected = Math.round(rungs.reduce((a,b)=>a+b,0) / (rungs.length * top) * 100);
const roadmap = () => nodes.roadmap.innerHTML;
assert.equal((roadmap().match(/class="seg[ "]/g)||[]).length, rungs.length);
assert.match(roadmap(), new RegExp('>' + expected + '%<'));
assert.match(roadmap(), new RegExp('aria-valuenow="' + expected + '"'));
// Segment fills, in order, are exactly the stage rungs -- no stage borrows another's.
assert.equal([...roadmap().matchAll(/width:(\d+)%/g)].map(m => m[1]).join(),
  Array.from(rungs).map(rung => Math.round(rung / top * 100)).join());
// A package is only green once it is independently accepted, and none is yet.
assert.equal(rungs.some(r => r === top), false);
assert.equal(roadmap().includes('class="seg done"'), false);
assert.match(roadmap(), /<b>0<\/b> accepted/);

// The denominator has to be the real Phase 1 package set, or the bar is measuring a
// list this file invented. Package IDs only -- status is PM's to write, not ours to read.
const phase1 = fs.readFileSync('../../docs/PACKAGES/README.md', 'utf8')
  .split(/^## /m).find(section => section.startsWith('Phase 1'));
const packages = [...phase1.matchAll(/^\| (WP-\d+) \|/gm)].map(m => m[1]);
assert.equal(Array.from(vm.runInContext('PHASE1.stages.map(s => s.id)', ctx)).sort().join(), packages.sort().join());

// Negative control: the bar is derived, not a hardcoded picture of today.
const original = JSON.stringify(rungs);
vm.runInContext('PHASE1.stages.forEach(s => { s.rung = RUNGS.length; }); renderRoadmap();', ctx);
assert.match(roadmap(), />100%</);
assert.equal((roadmap().match(/class="seg done"/g)||[]).length, rungs.length);
assert.match(roadmap(), new RegExp('<b>' + rungs.length + '</b> accepted'));
vm.runInContext('PHASE1.stages.forEach(s => { s.rung = 0; }); renderRoadmap();', ctx);
assert.match(roadmap(), />0%</);
assert.equal(roadmap().includes('width:0%'), true);

// Negative control: a stage with no stated rung is unknown progress, not zero progress
// and not the last good number. It must stop the render loudly.
vm.runInContext('PHASE1.stages[0].rung = null;', ctx);
assert.throws(() => vm.runInContext('renderRoadmap()', ctx), /WP-06 has no valid rung/);
vm.runInContext('PHASE1.stages[0].rung = 5;', ctx);
assert.throws(() => vm.runInContext('renderRoadmap()', ctx), /no valid rung/);

// Stage prose is escaped on the same path as issue titles.
const name0 = vm.runInContext('PHASE1.stages[0].name', ctx);
vm.runInContext('PHASE1.stages[0].rung = 1; PHASE1.stages[0].name = "<img src=x> & co"; renderRoadmap();', ctx);
assert.match(roadmap(), /&lt;img src=x&gt; &amp; co/);
assert(!roadmap().includes('<img'));

vm.runInContext('PHASE1.stages[0].name = ' + JSON.stringify(name0) + ';', ctx);
vm.runInContext('PHASE1.stages.forEach((s, i) => { s.rung = ' + original + '[i]; }); renderRoadmap();', ctx);
const settled = roadmap();
assert.match(settled, new RegExp('>' + expected + '%<'));

(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(nodes.board.innerHTML,/&lt;PM&gt; &amp; watch/);
  assert.match(nodes.board.innerHTML,/digital-tape-verification\/issues\/4/);
  assert.equal((nodes.board.innerHTML.match(/class="chip yellow"/g)||[]).length,2);
  assert.equal((nodes.board.innerHTML.match(/class="chip green"/g)||[]).length,4);
  assert(requests.some(url=>url.includes('page=2')));
  mode='fail'; await vm.runInContext('render()',ctx);
  assert.match(nodes.board.textContent,/unknown/);
  assert.match(nodes.warn.innerHTML,/&lt;img/);
  assert(!nodes.warn.innerHTML.includes('<img'));
  // The roadmap reads main, not GitHub, so a failed queue refresh must not blank it.
  assert.equal(roadmap(), settled);
  console.log('PASS pagination, PR exclusion, dual-repo routing, escaping, failure clears status, five-minute polling');
  console.log('PASS roadmap computed from stage table, unaccepted stays amber, unknown rung fails loudly, survives queue failure');
})().catch(e=>{console.error(e);process.exitCode=1;});
