const {test} = require('node:test');
const assert = require('node:assert/strict');
const {build} = require('../../dashboard/model.js');
function fixture() {
  return {version:2,updated_at:'2026-09-08T00:00:00Z',roles:{hardware:{enabled:true,actor:'hw',instance:'one'},'worker-grok':{enabled:true,actor:'grok',instance:'two'}},current:1,rounds:{'1':{number:1,state:'active'}},tasks:{'2':{number:2,round:1,role:'hardware',destination:'hardware',phase:'fanout',state:'waiting'},'3':{number:3,parent:2,round:1,role:'worker-grok',destination:'worker-grok',state:'ready',title:'<img src=x onerror=alert(1)>'}}};
}
test('workers remain attached to their hardware parent, not Software', () => {
  const view=build(fixture());
  assert.equal(view.cards.find(c=>c.id==='hardware').children[0].number,3);
  assert.equal(view.cards.find(c=>c.id==='software').children.length,0);
});
test('ready is distinct from queued and unbound is distinct from idle', () => {
  const view=build(fixture());
  assert.equal(view.cards.find(c=>c.id==='worker-grok').state,'ready');
  assert.equal(view.cards.find(c=>c.id==='pm').state,'unbound');
});
test('result ownership survives upward routing', () => {
  const f=fixture();f.tasks['3'].state='review';f.tasks['3'].destination='hardware';
  assert.equal(build(f).cards.find(c=>c.id==='worker-grok').own.length,1);
});
test('no round does not show historical tasks as current work', () => {
  const f=fixture();f.current=null;
  assert.equal(build(f).cards.find(c=>c.id==='worker-grok').own.length,0);
});
test('bad or missing snapshots fail visibly', () => {
  assert.throws(()=>build({})); const f=fixture();f.current=99;assert.throws(()=>build(f));
});
test('renderer uses text nodes rather than injecting issue/error content as markup', () => {
  const fs=require('node:fs');const source=fs.readFileSync(require('node:path').join(__dirname,'../../dashboard/app.js'),'utf8');
  assert.doesNotMatch(source,/innerHTML|insertAdjacentHTML|document\.write/);
});
