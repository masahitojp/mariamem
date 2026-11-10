"""Acquire pinned MariaDB source for the timer/charset consumer census."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile


REPO = Path(__file__).resolve().parents[2]
WORKSPACE = REPO.parent
TEMP = WORKSPACE / "temp"
EVIDENCE = WORKSPACE / "evidence"
sys.path.insert(0, str(REPO / "scripts"))
from git_identity import require_commit


def main():
    plan = json.loads(Path(__file__).with_name("plan.json").read_text())
    require_commit(REPO, plan["source_commit"])
    inputs = json.loads((REPO / "release/inputs.lock.json").read_text())["inputs"]
    item = next(entry for entry in inputs if entry["name"] == "mariadb")
    assert item["revision"] == plan["mariadb_source_commit"]
    commit = json.loads(subprocess.check_output(
        ["gh", "api", "repos/MariaDB/server/git/commits/" + item["revision"]], text=True
    ))
    assert commit["sha"] == item["revision"]
    TEMP.mkdir(exist_ok=True)
    EVIDENCE.mkdir(exist_ok=True)
    archive_path = TEMP / "source.tar.gz"
    subprocess.run(["curl", "-fLsS", item["url"], "-o", str(archive_path)],
                   check=True, timeout=300)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    assert digest == item["sha256"]
    destination = TEMP / "upstream"
    destination.mkdir()
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        for member in members:
            assert not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
            if member.issym() or member.islnk():
                assert not Path(member.linkname).is_absolute()
                assert ".." not in Path(member.linkname).parts
        archive.extractall(destination)
    root = next(destination.iterdir())
    assert root.name == "server-" + item["revision"]
    result = dict(source_commit=item["revision"], archive_sha256=digest, url=item["url"],
                  files=sum(member.isfile() for member in members),
                  extracted_bytes=sum(member.size for member in members if member.isfile()),
                  verified_commit=commit["sha"])
    (EVIDENCE / "acquisition.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Verified full pinned source:", root.name, flush=True)


if __name__ == "__main__":
    main()
