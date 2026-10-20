import json, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/"scripts"))
from git_identity import require_commit
records=[]
for name, repo, sha in [("mariadb","MariaDB/server","83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e"),("lite4mariadb","shyim/lite4mariadb","24be9371a2f6c71250a2356631ad6feab2280b02"),("converter","goccy/wasm2go","730057c146463f663e8774587bc96fb2bea91af8")]:
 root=Path("../temp/git-inputs")/name;root.mkdir(parents=True,exist_ok=True)
 subprocess.run(["git","init","-q",str(root)],check=True)
 subprocess.run(["git","-C",str(root),"fetch","--depth=1","--filter=blob:none","https://github.com/"+repo+".git",sha],check=True)
 record=require_commit(root,sha)
 records.append(dict(name=name,repository=repo,**record.__dict__))
 Path("../evidence/git-input-identities.json").write_text(json.dumps(records,indent=2)+"\n")
