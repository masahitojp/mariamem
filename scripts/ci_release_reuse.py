#!/usr/bin/env python3
"""Authenticated immutable GitHub artifact transport for generated-Go Release CI.

Legacy native/AOT restoration and evidence interpretation are retired. Archive
allowlists and exact-source guards live in release_generated_ci.py.
"""
import json
from pathlib import PurePosixPath
import re
import shutil
import urllib.request
from common import digest

WORKFLOW = ".github/workflows/release-candidate-ready.yml"

def require(ok, message):
    if not ok: raise ValueError(message)

def safe_name(name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in name,
            "unsafe archive path: " + name)
    require(str(path) not in (".", ""), "empty archive path")
    return str(path)

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.remove_header("Authorization")
        return redirected


class GitHub:
    def __init__(self, repository, token):
        require(re.fullmatch(r"[\w.-]+/[\w.-]+", repository), "invalid GitHub repository")
        self.base = "https://api.github.com/repos/" + repository
        self.headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            self.headers["Authorization"] = "Bearer " + token
        self.opener = urllib.request.build_opener(SafeRedirect())

    def request(self, path):
        return self.opener.open(urllib.request.Request(self.base + path, headers=self.headers), timeout=120)

    def json(self, path):
        with self.request(path) as response:
            return json.load(response)

    def artifact(self, run, name, commit, destination):
        info = self.json(f"/actions/runs/{run}")
        require(info.get("path", "").split("@", 1)[0] == WORKFLOW,
                "reuse run is not the canonical Release CI workflow")
        # Retried runs may execute the newer workflow while checking out an older candidate.
        # Candidate provenance below binds the source; workflow head_sha alone cannot.
        entries = []
        page = 1
        while True:
            found = self.json(f"/actions/runs/{run}/artifacts?per_page=100&page={page}")["artifacts"]
            entries.extend(found)
            if len(found) < 100:
                break
            page += 1
        matches = [a for a in entries if a["name"] == name]
        require(len(matches) == 1, "required reusable artifact missing or ambiguous: " + name)
        artifact = matches[0]
        require(not artifact.get("expired"), "reusable artifact expired: " + name)
        expected = artifact.get("digest", "")
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", expected or ""),
                "GitHub artifact has no verifiable SHA256 digest: " + name)
        with self.request(f"/actions/artifacts/{artifact['id']}/zip") as source, destination.open("wb") as output:
            shutil.copyfileobj(source, output)
        require(digest(destination) == expected.split(":", 1)[1], "GitHub artifact ZIP hash mismatch: " + name)
        return {"run_id": run, "artifact_id": artifact["id"], "name": name, "zip_sha256": digest(destination)}
