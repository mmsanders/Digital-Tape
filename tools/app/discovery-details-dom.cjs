// Test adapter (V318-02): actual backend discovery views through a production renderer
// in an isolated browser document. No Digital Tape executable, host process, native window
// or OS gesture is run. Arguments: correction1.json, renderer (screen.mjs), output file.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
async function main() {
  const [inputPath, rendererPath, outputPath] = process.argv.slice(2);
  const input = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
  const source = fs.readFileSync(rendererPath);
  const browser = await chromium.launch({ executablePath: process.env.TEST_BROWSER_EXE, headless: true, chromiumSandbox: true });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    await page.setContent('<!doctype html><html><body><main id="app"></main></body></html>');
    await page.addStyleTag({ content: fs.readFileSync(path.join(path.dirname(rendererPath), 'style.css'), 'utf8') });
    await page.evaluate(async text => {
      const url = URL.createObjectURL(new Blob([text], { type: 'text/javascript' }));
      window.productionScreen = await import(url);
      URL.revokeObjectURL(url);
    }, source.toString('utf8'));
    const rows = await page.evaluate(async views => {
      const root = document.getElementById('app');
      const visible = node => { const s = getComputedStyle(node); return !node.hidden && s.display !== 'none' && s.visibility !== 'hidden' && node.getClientRects().length > 0; };
      const out = {};
      for (const [id, { view, details }] of Object.entries(views)) {
        const calls = [];
        const screen = window.productionScreen.mountScreen(root, { details: () => { calls.push('details'); return details; } });
        screen.render(view);
        const el = x => root.querySelector('#' + x);
        const row = { state: el('screen').dataset.state, card: el('card').textContent, make_disabled: el('make').disabled,
          enumerated_items: [...root.querySelectorAll('li, option, tr')].length, show_details_visible: visible(el('show-details')) };
        if (row.show_details_visible) {
          el('show-details').click();
          await new Promise(r => setTimeout(r, 0));
        }
        row.details_visible = visible(el('details'));
        row.details_text = row.details_visible ? el('details').textContent : '';
        row.details_calls = calls.length;
        out[id] = row;
        screen.destroy();
      }
      return out;
    }, input.details_views);
    const result = { source_head: input.source_head, renderer: path.relative(process.cwd(), rendererPath).replaceAll('\\', '/'),
      renderer_sha256: crypto.createHash('sha256').update(source).digest('hex'), browser: browser.version(), native_ui: false, page_errors: errors, rows };
    fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
  } finally { await browser.close(); }
}
main().catch(e => { console.error(e); process.exit(1); });
