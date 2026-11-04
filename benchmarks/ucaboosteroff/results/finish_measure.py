import subprocess,sys
from pathlib import Path
w=Path(__file__).resolve().parents[1]
for phase in ['pilot','measure']:
 subprocess.run([sys.executable,str(w/'evidence/run_compare.py'),'--phase',phase],check=True)
