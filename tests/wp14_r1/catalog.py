"""Independent executable census; no Product imports."""
from pathlib import Path

MBR_FIELDS=(0,444,446,447,450,454,458,462,463,466,470,474,478,510)
EPOCHS=(0,1,315532799,315532800,315532801,946684799,946684800,0xffffffff)
MUTATIONS=('clean','invalid-standby','torn-primary','both-superblocks-bad','flipped-a-entry','degraded-b')
COMMANDS=('provision','load','verify','dump','play','scrub','record','promote','reset-b','respool')

def image_cases():
    names=sorted(p.name for p in (Path(__file__).parent.parent/'golden/ref').glob('*.wav'))
    assert len(names)==10
    return (['usage-'+str(i) for i in range(5)]+['entropy-and-UTF8-32-bytes']+
            [kind+'-roundtrip-'+name for name in names+['c60.wav'] for kind in ('bare','whole')]+
            ['recognition-'+name for name in ('crc-signature','crc-signature-corrupt')]+
            ['recognition-empty-file-'+str(x) for x in (False,True)]+
            ['layout-field-'+str(x) for x in MBR_FIELDS]+['layout-multiple-findings']+
            ['UTC-determinism-'+str(x) for x in EPOCHS]+
            ['engine-fixture-'+x for x in MUTATIONS]+['geometry-no-truncate']+
            ['capacity-'+str(a)+'-'+str(b) for a,b in ((1,1),(60,1),(1,60*44100),(1,60*44100+1))]+
            ['large-provision','large-exact-MBR-FAT-README','large-load','large-verify',
             'large-dump-A','large-dump-B','large-reset-b','large-promote','large-respool',
             'large-play','large-scrub','large-record','format-whole-refusal'])

IMAGE_CONTROLS=['drop-final-frame','append-zero-tail','wrong-last-sample',
                'FAT-sector-size','FAT-cluster-size','FAT-boot-signature','README-content',
                'UTC-create-date','UTC-mod-time','UTC-access-date','UTC-creation-fraction']

if __name__=='__main__':
    import json
    from native import requests
    print(json.dumps({'image_cases':image_cases(),'image_controls':IMAGE_CONTROLS,
                      'native':{p:[r['case'] for r in requests(p,Path('owned-backing.img'))]
                                for p in ('linux','macos','windows')}},indent=2))
