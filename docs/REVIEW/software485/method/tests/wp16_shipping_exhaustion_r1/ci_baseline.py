"""One exact baseline execution; normal publication CI is not Product acceptance."""
from pathlib import Path
import sys,subprocess
from runner import BASE,sha,run
matches=[p for p in Path('baseline-kit').rglob('ingest.exe') if sha(p)==BASE]
assert len(matches)==1,'exact original shipping executable unavailable'
sources=Path('baseline-sources').resolve()
subprocess.run([sys.executable,'-B','tests/wp16_ingest_stage1/asset.py','--destination',str(sources)],check=True)
run(matches[0].resolve(),BASE,sources/'assets/ordinary.wav',Path('shipping-exhaustion-results').resolve(),'baseline-red')
