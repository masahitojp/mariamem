#!/usr/bin/env python3
"""Selected normal-CI prepared consumers; retain accepted functional failures."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--host',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    def run(args,*,check=True):
        return subprocess.run([str(x) for x in args],cwd=ROOT,check=check,timeout=300)
    consumer=a.output/'consumer'
    run(['go','build','-race','-trimpath','-buildvcs=false','-o',consumer,'./tests/prepared_consumer'])
    environment=a.output/'environment.json';actual=a.output/'consumers.json';edges=a.output/'edges.json'
    run([sys.executable,'tests/v06_prepared_connector_environment.py','--output',environment])
    r=run([sys.executable,'tests/v06_prepared_consumers.py','--host',a.host,'--consumer',consumer,'--output',actual],check=False)
    run([sys.executable,'tests/v06_prepared_consumer_edges.py','--host',a.host,'--output',edges])
    run([sys.executable,'tests/v06_prepared_p5_compare.py','--actual',actual,
         '--native','tests/fixtures/prepared-p5-native-macos314.json',
         '--actual-environment',environment,'--native-cext-environment','tests/fixtures/prepared-p5-native-macos314-environment.json',
         '--actual-edges',edges,'--native-edges','tests/fixtures/prepared-p5-native-macos314-edges.json',
         '--accepted-disposition','docs/decisions/prepared-consumer-exceptions.md',
         '--consumer-exit',r.returncode,'--output',a.output/'matching.json'])
    print('PASS: Go prepared / Python normal controls and exact accepted-exception tripwires; Python functional FAIL retained')


if __name__=='__main__':main()
