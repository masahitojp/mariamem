from pathlib import Path
import subprocess,sys
b=Path(__file__).resolve().parent
for name in ['build.py','run.py']:
 subprocess.run([sys.executable,str(b/name)],check=True)
