#!/usr/bin/env python3
"""Generate the unchanged product proc header for this native probe."""
import argparse
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--receipt',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(repo/'scripts'))
import routine_schema

receipt=routine_schema.prepare(args.source,root=repo)
args.receipt.parent.mkdir(parents=True,exist_ok=True)
args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
print('Product routine header prepared and pinned')
