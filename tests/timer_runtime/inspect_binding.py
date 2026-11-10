from pathlib import Path
import argparse,json,hashlib,re,sys,difflib
S=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser()
p.add_argument('--candidate-module',type=Path,required=True)
p.add_argument('--guest',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
args=p.parse_args(); E=args.output; E.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(S/'scripts'))
import runtime_thread_lifetime as threads
import runtime_crc32c as crc
from generate_runtime import OLD,NEW
G=args.candidate_module/'generated'
record={'baseline_guest_sha256':threads.GUEST_SHA256,'guest_sha256':json.loads((args.guest/'guest.json').read_text())['guest_sha256'],'data_sha256':hashlib.sha256((G/'data.bin').read_bytes()).hexdigest(),'functions':{},'crc':{},'proof':{}}
for path,(fn,oldsha) in threads.FUNCTIONS.items():
    text=(G/path.removeprefix('code/')).read_text().replace(OLD,NEW)
    body=threads.function(text,fn)
    got=hashlib.sha256(re.sub(r'\s+','',body).encode()).hexdigest()
    record['functions'][path]=[fn,got]
    record['proof'][fn]={'old_sha256':oldsha,'new_sha256':got,'identical_normalized_body':oldsha==got}
    if got!=oldsha:
        old=(S/'internal/generatedgo'/path).read_text()
        old=re.sub(r'(func Fn153\(m \*base.Module, l0 int32\) \{\n)\s*if base.DeferThreadAllocationFree\(m, l0\) \{\s*return\s*\}\n',r'\1',old,count=1)
        oldbody=threads.function(old,fn)
        (E/(fn+'.diff')).write_text(''.join(difflib.unified_diff(oldbody.splitlines(True),body.splitlines(True))))
text=(G/crc.PATH.removeprefix('code/')).read_text().replace(OLD,NEW)
body=threads.function(text,crc.FUNCTION)
old=(S/'tests/fixtures/pinned-crc-validator.go.txt').read_text()
table=bytes.fromhex((S/'tests/fixtures/pinned-crc-table.hex').read_text())
data=(G/'data.bin').read_bytes(); offset=data.find(table)
assert offset>=0 and data.find(table,offset+1)==-1
record['crc']={'path':crc.PATH,'function':crc.FUNCTION,'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'table_offset':offset,'table_sha256':hashlib.sha256(table).hexdigest()}
record['proof']['crc']={'old_sha256':crc.BODY_SHA256,'new_sha256':record['crc']['body_sha256'],'identical_body':body==old,'identical_table':True,'old_table_offset':crc.TABLE_OFFSET,'new_table_offset':offset}
(E/'crc.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),body.splitlines(True))))
(E/'binding-provisional.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
