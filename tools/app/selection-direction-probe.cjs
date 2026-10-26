// Browser fact for Verification324: a plain <input> (no Digital Tape code) given a selection
// with direction 'none' through setSelectionRange, read back in this browser.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.TEST_BROWSER_EXE, headless: true });
  const page = await browser.newPage();
  await page.setContent('<input id="i" value="Road Trip">');
  const rows = await page.evaluate(() => [[4, 4, 'none'], [0, 4, 'none'], [0, 4, 'forward'], [0, 4, 'backward']].map(([s, e, d]) => {
    const i = document.getElementById('i'); i.focus(); i.setSelectionRange(s, e, d);
    return { set: [s, e, d], read: [i.selectionStart, i.selectionEnd, i.selectionDirection] };
  }));
  console.log(JSON.stringify({ browser: browser.version(), platform: process.platform, rows }, null, 1));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
