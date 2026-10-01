#!/usr/bin/env python3
"""Independent starts through unchanged host/mysqlwire packages, private module."""
import argparse
import json
from pathlib import Path
import subprocess
from measure_execution import distribution


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--runs',type=int,default=100)
    p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args();cmd=a.command
    if cmd[0]=='--':cmd=cmd[1:]
    report={'boundary':'fresh host process; per-call artifact digests; unchanged host.Start/StartVerified + MySQL wire SELECT 1; excludes public API envelope/download', 'trials':[]}
    for i in range(a.runs):
        r=subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=40)
        row=json.loads(r.stdout);row['trial']=i;row['slow']=row['wire_ready_seconds']>=.5
        report['trials'].append(row)
        a.output.write_text(json.dumps(report,indent=2)+'\n')
    for name in ['verified_seconds','wire_ready_seconds','sql_seconds']:
        report[name]=distribution([r[name] for r in report['trials']])
    report['slow_count']=sum(r['slow'] for r in report['trials'])
    report['slow_percentage']=100*report['slow_count']/a.runs
    for key in ['rss_bytes','primary_bytes','cpu_seconds']:
        for which in ['host','guest','total']:
            vals=[]
            for r in report['trials']:
                host=r['counters'][str(r['host_pid'])][key];guest=r['counters'][str(r['guest_pid'])][key]
                vals.append(host if which=='host' else guest if which=='guest' else host+guest)
            report[which+'_'+key]=distribution(vals)
    a.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
