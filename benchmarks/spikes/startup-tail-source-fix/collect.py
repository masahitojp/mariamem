#!/usr/bin/env python3
"""Retain compact identities from disposable guest and native receipts."""

import json
from pathlib import Path

WORK = Path(__file__).resolve().parents[4]
TEMP = WORK / "temp"
DEST = Path(__file__).resolve().parents[2] / "v050-startup-tail-source-fix-evidence"

guests = []
for name in ("dev-guest", "dev-guest-rebound"):
    record = json.loads((TEMP / name / "guest.json").read_text())
    guests.append({
        "name": name,
        "source_commit": record["source_identity"]["commit"],
        "guest_sha256": record["guest_sha256"],
        "linked_sha256": record["repetitions"][0]["linked_sha256"],
        "experimental_patch": record["prepared_source"]["experimental_patch"],
        "toolchain_pins_sha256": record["toolchain"]["pins_sha256"],
        "contract": record["contract"],
        "result": record["result"],
    })

natives = []
for name in ("dev-native-rebound", "dev-native-independent"):
    record = json.loads((TEMP / name / "development.json").read_text())
    natives.append({
        "name": name,
        "source_commit": record["source_identity"]["commit"],
        "guest_sha256": record["guest_sha256"],
        "binary_sha256": record["binary_sha256"],
        "smoke": record["smoke"],
        "raw_translation": record["raw_translation"],
        "generated_inventory": record["generated_inventory"],
        "contract": record["contract"],
        "result": record["result"],
    })

different = sorted(key for key in natives[0]["generated_inventory"]
                   if natives[0]["generated_inventory"][key] != natives[1]["generated_inventory"][key])
assert different == ["provenance.json"], different
assert guests[0]["guest_sha256"] == guests[1]["guest_sha256"]
assert natives[0]["binary_sha256"] == natives[1]["binary_sha256"]
assert natives[0]["raw_translation"] == natives[1]["raw_translation"]
assert natives[0]["smoke"] == natives[1]["smoke"] == "PASS"

for name in ("dev-native-rebound", "dev-native-independent"):
    inputs = json.loads((TEMP / name / "installation-inputs.json").read_text())
    inputs.pop("translation_directory")
    natives[["dev-native-rebound", "dev-native-independent"].index(name)]["normalized_installation_inputs"] = inputs
assert natives[0]["normalized_installation_inputs"] == natives[1]["normalized_installation_inputs"]

summary = {"guests": guests, "natives": natives, "generated_inventory_different_files": different,
           "provenance_difference": "installation-inputs.json translation_directory is an absolute output path"}
(DEST / "identities.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print("identity checks PASS")
