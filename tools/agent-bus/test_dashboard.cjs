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

test('approval links select only waiting main authorization runs and construct trusted URLs', () => {
  const {waitingApprovals}=require('../../dashboard/model.js');
  const run={id:123,status:'waiting',head_branch:'main',event:'workflow_dispatch',path:'.github/workflows/agent-bus.yml',display_title:'Agent Bus · authorize · test',html_url:'https://evil.invalid'};
  assert.deepEqual(waitingApprovals({workflow_runs:[run]}),[{id:123,title:run.display_title,url:'https://github.com/mmsanders/Digital-Tape/actions/runs/123'}]);
  for (const patch of [{id:-1},{status:'completed'},{head_branch:'other'},{event:'push'},{path:'other.yml'},{display_title:'Agent Bus · claim · test'}])
    assert.equal(waitingApprovals({workflow_runs:[{...run,...patch}]}).length,0);
  assert.throws(()=>waitingApprovals({}));
});
