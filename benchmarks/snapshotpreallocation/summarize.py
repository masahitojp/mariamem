#!/usr/bin/env python3
"""Summarize all valid fresh-process trials; no time-based filtering."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=args.raw
    campaign=json.loads((raw/'campaign.json').read_text())
    if len(campaign)!=10 or any(r['exit_code']!=0 for r in campaign):
        parser.error('expected exactly five completed before and five after trials')
    rows=[]
    for r in campaign:
        result=r['result'];name=f"{r['variant']}-{r['trial']}"
        trace=next(t for t in result['traces'] if t['operation']=='snapshot')
        events={e['name']:e['offset_ns'] for e in trace['events']}
        top=(raw/name/'alloc_space-top.txt').read_text()
        def flat(suffix):
            return int(next(l for l in top.splitlines() if l.endswith(suffix)).split()[0].removesuffix('B'))
        rows.append(dict(variant=r['variant'],trial=r['trial'],wall_seconds=r['wall_seconds'],
            snapshot_ms=result['snapshot_ms'],export_shutdown_ms=(events['export_acknowledged']-events['sessions_drained'])/1e6,
            publish_ms=(events['snapshot_published']-events['guest_stopped'])/1e6,
            total_alloc_bytes=result['total_alloc_delta'],heap_before_bytes=result['heap_before'],heap_return_bytes=result['heap_after'],
            mallocs=result['mallocs_delta'],snapshot_bytes=result['snapshot_bytes'],guest_sha256=result['guest_sha256'],
            sampled_resize_alloc_bytes=flat('base.resizeMemData'),sampled_export_alloc_bytes=flat('generatedgo.exportTransfer.func1'),
            isolation_pass=result['isolation_pass'],corruption_rejected=result['corruption_rejected'],
            inventory=result['inventory'],files_sha256=result['files_sha256'],snapshot_trace=trace,
            raw_result_sha256=sha(raw/name/'result.json'),heap_profile_sha256=sha(raw/name/'snapshot.heap'),
            log_sha256=sha(raw/(name+'.log')),profile_top_sha256=sha(raw/name/'alloc_space-top.txt')))
    summary={}
    for variant in ['before','after']:
        selected=[r for r in rows if r['variant']==variant]
        if len(selected)!=5: parser.error('expected five trials per variant')
        summary[variant]={}
        for key in ['snapshot_ms','export_shutdown_ms','publish_ms','total_alloc_bytes','heap_return_bytes','sampled_resize_alloc_bytes','sampled_export_alloc_bytes']:
            values=[r[key] for r in selected]
            summary[variant][key]={'min':min(values),'median':statistics.median(values),'max':max(values)}
    args.output.write_text(json.dumps({'scenario':'bounded Snapshot cold-copy preallocation; not canonical','trials':rows,'summary':summary,'raw_campaign_sha256':sha(raw/'campaign.json')},indent=2)+'\n')
if __name__=='__main__': main()
