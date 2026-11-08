"""Fetch three pinned source files (including the actual const typedef) for the standalone C algorithm replay."""
from pathlib import Path
import argparse,urllib.request,hashlib
REV='83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e'
FILES={'include/my_global.h':'fc4d434c83576a251088ba695ca9b84c3219229e6e3975348e20070bc7a12a13','mysys/charset.c':'d120e40dea53badcb20c28a70189c88b483df02dd7ce7979fb6a7c234cb506f3','include/m_ctype.h':'b0c8684ffbe3b6e374b3f0bc49a162e2fc2309a2de3d20fdfb19250cca5a128b'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 for n,h in FILES.items():
  dst=a.output/n
  if dst.exists():data=dst.read_bytes()
  else:
   with urllib.request.urlopen('https://raw.githubusercontent.com/MariaDB/server/'+REV+'/'+n,timeout=90) as f:data=f.read(1000000)
  assert hashlib.sha256(data).hexdigest()==h,n
  dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
 print('pinned source files PASS')
if __name__=='__main__':main()
