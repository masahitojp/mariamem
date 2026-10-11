"""Source-only layout probe; call with extracted pristine 12.3.3 and 13.2.0 roots.

Run from the experiment checkout. Archives/hashes and recipe are in the report.
Requires GNU patch. The two input roots are read-only inputs; output must be fresh.
No guest build or production patch layout is created by this probe.
"""
import argparse,subprocess,re,shutil,json,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("source123",type=Path);p.add_argument("source132",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
old=subprocess.check_output(["git","show","5f14221463b6400e72e72a115bd1cc1a3acee88d:guest/experimental.patch"],text=True)
new=Path("guest/experimental.patch").read_text()
pattern=r"--- a/storage/innobase/log/log0log.cc\n.*?(?=--- a/storage/innobase/os/os0file.cc)"
common=re.sub(pattern,"",new,flags=re.S)
a.output.mkdir(parents=True,exist_ok=False);a.output=a.output.resolve()
(a.output/"common.patch").write_text(common)
files=re.findall(r"^\+\+\+ b/(.*)$",new,re.M)
for version,source,patch in [("123",a.source123,old),("132",a.source132,new)]:
    target=a.output/version;target.mkdir()
    for name in files:
        f=source/name
        if f.exists():
            (target/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target/name)
    variant=a.output/("redo-"+version+".patch");variant.write_text(re.search(pattern,patch,re.S).group())
    for item in [a.output/"common.patch",variant]:
        subprocess.run(["patch","--batch","--fuzz=0","-p1","-i",str(item)],cwd=target,check=True)
    (a.output/(version+"-hashes.json")).write_text(json.dumps({n:hashlib.sha256((target/n).read_bytes()).hexdigest() for n in files},indent=2)+"\n")
