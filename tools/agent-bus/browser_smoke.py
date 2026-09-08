#!/usr/bin/env python3
"""Exercise the actual dashboard renderer in the runner's installed Chrome."""
import functools
import http.server
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

from bus import ROOT, RUNTIME_FILE, empty_state


def main():
    chrome = shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome:
        raise SystemExit('Chrome unavailable; browser check did not run')
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp)
        shutil.copytree(ROOT / 'dashboard', site, dirs_exist_ok=True)
        app = site / 'app.js'
        app.write_text(app.read_text().replace(
            'https://raw.githubusercontent.com/mmsanders/Digital-Tape/agent-bus-state/state.json', '/state.json'))
        config = json.loads(RUNTIME_FILE.read_text())
        state = empty_state(config)
        state['current'] = 1
        state['rounds']['1'] = {'number':1,'state':'active'}
        attack = '<img src=x onerror="document.body.dataset.xss=1">'
        state['tasks']['2'] = dict(number=2,round=1,parent=1,title=attack,role='hardware',
            destination='hardware',phase='fanout',state='queued',requested='strong',cycles=1)
        (site / 'state.json').write_text(json.dumps(state))
        index = site / 'index.html'
        index.write_text(index.read_text().replace('</body>', '''<script>
          setTimeout(() => {
            document.body.dataset.overflow = document.documentElement.scrollWidth > innerWidth;
            document.body.dataset.cards = document.querySelectorAll('article.card').length;
          }, 1500);
        </script></body>'''))
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp)
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        output = ROOT / 'build/agent-bus-browser'; output.mkdir(parents=True, exist_ok=True)
        try:
            for width, height in ((1280, 1100), (390, 1600)):
                args = [chrome, '--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
                    '--no-proxy-server', '--virtual-time-budget=2500', f'--window-size={width},{height}',
                    '--dump-dom', f'--screenshot={output / (str(width)+".png")}',
                    f'http://127.0.0.1:{server.server_port}/']
                run = subprocess.run(args, capture_output=True, text=True, timeout=30, check=True)
                dom = run.stdout
                assert 'data-cards="8"' in dom, 'renderer did not finish'
                assert 'data-overflow="false"' in dom, 'horizontal overflow'
                assert 'data-xss=' not in dom.split('<body',1)[1].split('>',1)[0], 'injected markup executed'
                assert '&lt;img' in dom, 'untrusted issue title not displayed as text'
                print(f'PASS dashboard {width}px: 8 cards, no horizontal overflow, malicious title rendered safely')
        finally:
            server.shutdown(); server.server_close()


if __name__ == '__main__': main()
