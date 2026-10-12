"""Counterfactual operand spans on preserved prior traces; not fresh dynamic observation."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser()
p.add_argument("--output",type=Path,required=True)
a=p.parse_args()
source=ROOT/"docs/reviews/v050-shared-impact-evidence/trace-receipts.json"
prior=json.loads(source.read_text())
results={}
for name,run in prior.items():
    rows=[]
    for ex in run["selected_address_pair_examples"]:
        w=ex["writer"]["key"];o=ex["other"]["key"]
        start,end=w["ea"],w["ea"]+w["requested"]
        other_start=o["ea"]
        other_size=o["requested"] if o["kind"].startswith("subword") else o["effective"]
        overlap=max(start,other_start)<min(end,other_start+other_size)
        rows.append({
            "word":ex["word"],"writer_fn":w["fn"],"writer_ea":w["ea"],"writer_requested":w["requested"],
            "other_fn":o["fn"],"other_ea":o["ea"],"other_kind":o["kind"],"other_span":other_size,
            "prior_relation":ex["relation"],"exact_candidate_operand_overlap":overlap,
            "simultaneity_or_happens_before":"UNPROVEN",
        })
    results[name]={"selected_pair_examples":rows,"disjoint_with_exact_spans":sum(not x["exact_candidate_operand_overlap"] for x in rows),
                   "still_overlap_at_requested_bytes":sum(x["exact_candidate_operand_overlap"] for x in rows)}
a.output.write_text(json.dumps({
    "prior_receipt_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
    "interpretation":"Apply candidate machine operand widths to prior address examples only. No fresh candidate address trace, timing or whole-guest safety claim.",
    "runs":results,
},indent=2)+"\n")
print("PASS: selected prior addresses classified by exact operand spans")
