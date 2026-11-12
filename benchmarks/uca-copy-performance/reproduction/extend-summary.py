from pathlib import Path
import subprocess
E=Path(__file__).resolve().parent
p=E/'report/analyze.py';s=p.read_text()
s=s.replace("r['process_wall_ms']=float(b['process_wall_ms'])", "r['process_wall_ms']=float(b['process_wall_ms']);r['max_rss_bytes']=int(b['max_rss_bytes'])")
s=s.replace("out['shop'][arm][str(par)]=e", "e['process_peak_rss_bytes']=stats([r['max_rss_bytes'] for r in rr])\n   out['shop'][arm][str(par)]=e")
s=s.replace("out['lifecycle'][arm][kind]=entry", "out['lifecycle'][arm][kind]=entry\n  out['lifecycle'][arm]['process_peak_rss_bytes']=stats([r['max_rss_bytes'] for r in life])")
p.write_text(s)
subprocess.run(['python3',str(p)],check=True)
subprocess.run(['python3',str(p),'--check'],check=True)
