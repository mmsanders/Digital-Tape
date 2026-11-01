"""Full same-profile three-platform candidate campaign; no Product execution."""
import argparse,json
from pathlib import Path
import audit,review,relations

def check(packets,sources,receipts):
    assert len(packets)==len(receipts)==3,'all three native platform packets required'
    reports=[];outputs=[]
    for packet,receipt in zip(packets,receipts):
        report,out=review.check(packet,sources,json.loads(Path(receipt).read_text(encoding='utf-8')))
        reports.append(report);outputs.append(out)
    assert {r['platform'] for r in reports}=={'windows11','macos','linux'}
    assert all(len({r[key] for r in reports})==1 for key in ('candidate_sha','profile','tool_version','config_sha256'))
    assert all(set(out)==set(outputs[0]) for out in outputs),'cross-platform success census differs'
    for id_ in outputs[0]:
        for out in outputs[1:]:relations.pair(outputs[0][id_],out[id_],'cross-os')
    return {'status':'FULL SAME-PROFILE CAMPAIGN CHECKED; Verification exact-head disposition required','reports':reports}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',action='append',required=True);p.add_argument('--verification-receipts',action='append',required=True);p.add_argument('--sources',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    report=check(a.packet,a.sources,a.verification_receipts);a.out.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
