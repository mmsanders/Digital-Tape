const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('index.html', 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes = Object.fromEntries(['board','meta','warn'].map(id => [id, {innerHTML:'',textContent:''}]));
let mode = 'ok';
let requests = [];
const ctx = vm.createContext({document:{hidden:false,getElementById:id=>nodes[id]},AbortSignal,Date,Set,Number,String,
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
  console.log('PASS pagination, PR exclusion, dual-repo routing, escaping, failure clears status, five-minute polling');
})().catch(e=>{console.error(e);process.exitCode=1;});
