// Test adapter: isolated browser DOM importing the production renderer bytes.
// No Digital Tape executable, host process, native window or OS gesture is run.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
async function main() {
  const [inputPath, outputDir, sourceHead] = process.argv.slice(2);
  const input = JSON.parse(fs.readFileSync(inputPath, 'utf8').replace(/^\uFEFF/, ''));
  const production = path.resolve(__dirname, '../../host/app/frontend/screen.mjs');
  const source = fs.readFileSync(production, 'utf8');
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.TEST_BROWSER_EXE,
    headless: true, chromiumSandbox: true
  });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    await page.setContent('<!doctype html><html><body><main id="app"></main></body></html>');
    await page.addStyleTag({content:fs.readFileSync(path.join(path.dirname(production),'style.css'),'utf8')});
    // A module in a fresh test document, never injection into the Windows app.
    await page.evaluate(async text => {
      const url = URL.createObjectURL(new Blob([text], {type:'text/javascript'}));
      window.productionScreen = await import(url);
      URL.revokeObjectURL(url);
    }, source);
    const result = await page.evaluate(async input => {
      const root = document.getElementById('app');
      const raw = {};
      const callbacks = [];
      const module = window.productionScreen;
      let component;
      function mount() {
        component?.destroy();
        component = module.mountScreen(root, {
          label: x => callbacks.push(['label', x]),
          dropPaths: x => callbacks.push(['drop', x]),
          startOver: () => callbacks.push(['reset']),
          details: () => callbacks.push(['details']) && undefined
        });
      }
      const el = id => root.querySelector('#'+id);
      function nativeProgress(node) {
        const style=getComputedStyle(node);
        const visible=!node.hidden && style.display!=='none' && style.visibility!=='hidden' && node.getClientRects().length>0;
        return {visible,position:node.position,pseudo_indeterminate:node.matches(':indeterminate'),value_attribute:node.getAttribute('value'),metadata:node.dataset.indeterminate,accent_color:style.accentColor};
      }
      function capture(id) {
        const meter = el('length');
        raw[id] = root.innerHTML;
        return {
          label: el('label').value, state: el('screen').dataset.state,
          make_disabled: el('make').disabled,
          enumerated_items: [...root.querySelectorAll('li, option, tr')].map(x=>x.textContent),
          sentence: el('message').textContent, card: el('card').textContent,
          action: el('reset').hidden ? null : el('reset').textContent,
          frames: el('length-text').hasAttribute('data-frames') ? Number(el('length-text').dataset.frames) : null,
          ratio: meter.dataset.kind === 'length' && meter.hasAttribute('value') ? meter.value : null,
          too_long: meter.dataset.tooLong === 'true',
          indeterminate: nativeProgress(meter).visible && nativeProgress(meter).position === -1,
          native_progress: nativeProgress(meter),
          details: el('details').textContent,
          details_copyable: el('details').tagName === 'PRE' && el('details').tabIndex === 0 && getComputedStyle(el('details')).userSelect === 'text' && !el('details').hidden,
          progress_bar_count: [...root.querySelectorAll('progress')].filter(x=>!x.hidden).length,
          html: root.innerHTML, raw_ref: 'dom.json#'+id
        };
      }
      mount();
      const mount_side_effects = [...callbacks];
      const views = {};
      for (const v of input.views) {
        const model = {view: v.state.toLowerCase(), checking: v.state === 'Checking',
          label:v.label, total_frames:v.frames, bar:v.ratio, too_long:v.too_long,
          message:v.sentence, card_line:v.card, details_available:!!v.details, make_enabled:false};
        component.render(model, v.details);
        let progress;
        if (v.state === 'Making') {
          progress = [];
          for (const amount of v.progress) {
            component.render({...model,bar:amount}, v.details);
            progress.push(el('length').value);
          }
        }
        if (v.details) el('show-details').click();
        views[v.id] = capture(v.id);
        if (progress) views[v.id].progress = progress;
      }
      const labels=[];
      for(const l of input.labels) {
        component.render({view:'ready',label:l.before,bar:0,total_frames:0});
        el('label').value=l.attempt;
        el('label').dispatchEvent(new Event('input',{bubbles:true}));
        labels.push({before:l.before,attempt:l.attempt,after:el('label').value});
      }
      // Only observe screen transport. Actual host admission is pending306.
      const drop_transport={};
      for(const d of input.drops) {
        callbacks.length=0;
        for(const batch of d.gestures) component.dropPaths(batch.map(x=>x.path));
        drop_transport[d.id]=callbacks.filter(x=>x[0]==='drop').map(x=>x[1]);
      }
      callbacks.length=0;
      for(const bad of input.malformed_drop_inputs) component.dropPaths(bad);
      const malformed_drop_callbacks=callbacks.filter(x=>x[0]==='drop').length;
      component.render({view:'problem',label:'old',message:'problem',details_available:true},'old details');
      callbacks.length=0;
      el('reset').click();
      const reset=capture('start-over');
      const start_over={callbacks:callbacks.filter(x=>x[0]==='reset').length,label:reset.label,
        details:reset.details,state:reset.state,frames:reset.frames,make_disabled:reset.make_disabled};
      const bad=document.createElement('progress');bad.max=1;bad.dataset.indeterminate='false';root.append(bad);
      const negative_control={actual:nativeProgress(bad),html:bad.outerHTML};
      negative_control.rejected_by_frozen_false=negative_control.actual.visible && negative_control.actual.position===-1;
      if(!negative_control.rejected_by_frozen_false) throw new Error('Native indeterminate red control was not detected');
      bad.remove();
      return {views,labels,drop_transport,malformed_drop_callbacks,mount_side_effects,start_over,raw,negative_control};
    }, input);
    const raw=result.raw;
    delete result.raw;
    fs.writeFileSync(path.join(outputDir,'dom.json'),JSON.stringify(raw,null,2)+'\n');
    const output={source_head:sourceHead,evidence_class:'production component / test DOM',
      adapter_ref:'tools/app/screen-dom.cjs',raw_refs:['dom.json'],native_ui:false,
      shipping_test_switch:false,make_enabled:false,...result,
      incomplete:['combined renderer-to-host admission/reset rows await306; no fabricated host acceptance']};
    fs.writeFileSync(path.join(outputDir,'screen-observations.json'),JSON.stringify(output,null,2)+'\n');
    fs.writeFileSync(path.join(outputDir,'runtime.json'),JSON.stringify({node:process.version,
      browser:browser.version(),platform:process.platform,arch:process.arch,
      module_sha256:crypto.createHash('sha256').update(source).digest('hex'),
      production,playwright:require(path.join(process.env.PLAYWRIGHT_MODULE || 'playwright','package.json')).version,
      browser_executable:process.env.TEST_BROWSER_EXE,errors},null,2)+'\n');
    if(errors.length) throw new Error(errors.join('\n'));
    console.log('Captured actual production DOM: '+Object.keys(output.views).length+' views; host admission pending306.');
  } finally { await browser.close(); }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
