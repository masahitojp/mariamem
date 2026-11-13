from pathlib import Path
import json
e=Path(__file__).resolve().parent
(e/"build-handoff.json").write_text(json.dumps({"result":"BUILD_READY","next":"Run measure.py separately after build guards exit; per-process disk checks and timeouts remain."})+"\n")
print("BUILD READY: separate measurement avoids disk-scanner CPU interference",flush=True)
