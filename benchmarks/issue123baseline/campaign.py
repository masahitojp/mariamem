import pathlib,subprocess,sys
b=pathlib.Path(__file__).resolve().parent
for stage in ('build.py','run.py'):subprocess.run([sys.executable,str(b/stage)],check=True)
