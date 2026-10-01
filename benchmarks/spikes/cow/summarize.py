#!/usr/bin/env python3
"""Publish compact, path-free CoW evidence; raw hashes/vmmap stay in ignored results."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    content=json.loads((a.results/'characterization-resident/results.json').read_text())
    physical=json.loads((a.results/'os-only/results.json').read_text())
    proof=json.loads((a.results/'proof-measure/results.json').read_text())
    mappings=json.loads((a.results/'mapping/results.json').read_text())
    report={'schema_version':1,'source_sha':proof['source_sha'],'date':'2026-10-01',
            'environment':{'os':'macOS 27.0 (26A428)','cpu':'Apple M1','ram_bytes':17179869184,'os_page_bytes':16384,'go':'go1.26.8'},
            'content_trials':[],'physical_trials':physical['trials'],'proof':proof,'mappings':{}}
    for r in content['trials']:
        s={k:v for k,v in r.items() if k!='samples'}
        s['samples']={label:{k:v for k,v in sample.items() if k!='pages' and k not in ['linear_address','files']} for label,sample in r['samples'].items()}
        s['prepared_files']=[{k:v for k,v in f.items() if k not in ['blocks','hash','address']} for f in r['samples']['prepared']['files']]
        report['content_trials'].append(s)
    for r in report['physical_trials']:
        for label,sample in r['samples'].items():
            for k in ['pages','files']:sample.pop(k,None)
            vm=(a.results/'os-only'/f"{r['run']}-{r['workload']}"/(label+'.vmmap')).read_text()
            match=re.search(r'^Untagged\s+\S+\s+\S+\s+(\d+(?:\.\d+)?)([KMG])',vm,re.MULTILINE)
            sample['anonymous_dirty_bytes_rounded']=float(match[1])*{'K':1024,'M':1048576,'G':1073741824}[match[2]] if match else None
    aligned=[r['samples']['prepared']['pages'] for r in content['trials'] if int(r['samples']['prepared']['linear_address'],16)%16384==0]
    same=[k for k,v in aligned[0].items() if all(x.get(k)==v for x in aligned[1:])]
    zero=hashlib.sha256(bytes(16384)).hexdigest()
    report['independent_prepared_content']={'aligned_trials':len(aligned),'excluded_half_page_aligned_trials':len(content['trials'])-len(aligned),'same_content_bytes':len(same)*16384,'same_zero_content_bytes':sum(aligned[0][k]==zero for k in same)*16384,'warning':'content equality is not proof of safe cloneability; zero bytes may still require private atomic/pthread state'}
    for mode,sample in mappings.items():
        report['mappings'][mode]={k:v for k,v in sample.items() if k not in ['pages','files','linear_address']}
        summaries=[]
        for name in ['summary','regions']:
            lines=(a.results/'mapping'/mode/(name+'.vmmap')).read_text().splitlines()
            for line in lines:
                if name=='summary' and (line.startswith(('Physical footprint','Untagged','Stack ','mapped file','__TEXT ','TOTAL '))): summaries.append(line)
                if name=='regions' and (line.endswith('/proof-probe') or line.endswith('/memory.bin')):
                    summaries.append(re.sub(r'\s+/.*$', ' <image>' if line.endswith('/memory.bin') else ' <executable>',line))
        report['mappings'][mode]['vmmap_selected_lines']=summaries
    # Reduced summary remains auditable per trial, without megabytes of hash maps.
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
