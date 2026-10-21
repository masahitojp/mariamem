"""Bind the accepted WASIX allocation ABI to the handwritten completion owner.

This adapter adds one private Module field and a pre-allocator free handoff.
Never edit generated output. Reject changed allocation/entry/reclaimer code
before installing the handoff; this is a single-guest binding, not a generic ABI.
"""
import hashlib
import re

# Candidate-only P2 binding: canonical release inputs remain the routine guest
# until P6. See tests/fixtures/prepared-p2-binding and the implementation review.
# A fresh source build must match this single identity before development use.
GUEST_SHA256 = "a52dd707d337d5349a7c5d72bc2108dc823cfe0c625742e93bc0875a2e3b519a"
FUNCTIONS = {
    "code/p3/p3_pure.go": ("Fn153", "7287c2422d92f9cb8e1b35e90d6ff5a49f9d5578ae567ff46a261a4b11159270"),
    "code/p8/p8_pure.go": ("Fn131", "e31e88a8637fb60e5f197014ae2c4dd0afe2fcd05c6f850c13d24ff0b0810932"),
    "code/p5/p5_pure.go": ("Fn214", "e8d7ae281efd9f856fd14ae535c40473e2ccbf2af261bf67fa716bac40e3bfab"),
}


def validate_inputs(guest_sha256, candidate_files):
    required = {"generated/base/base.go", *("generated/" + p.removeprefix("code/") for p in FUNCTIONS)}
    if guest_sha256 != GUEST_SHA256 or not required <= set(candidate_files):
        raise ValueError("unreviewed guest/worker allocation binding inputs")


def function(text, name):
    starts = list(re.finditer(r"(?m)^func " + name + r"\(", text))
    if len(starts) != 1:
        raise ValueError("thread allocation binding missing/duplicate: " + name)
    tail = text[starts[0].start():]
    following = re.search(r"\nfunc Fn\d+\(", tail)
    return tail[:following.start()] if following else tail


def apply(name, text):
    if name == "code/base/base.go":
        anchor = re.compile(r"(?m)^\s*ThreadStart\s+func\(\*Module, int32, int32\)\n")
        if len(anchor.findall(text)) != 1 or re.search(r"(?m)^\s*ThreadLifetime\s+\*ThreadLifetime", text):
            raise ValueError("thread allocation Module shape changed")
        yield_body = "func (w *WasiStubs) Sched_yield(m *Module) int32 {\n\truntime.Gosched()\n\treturn _wasiESUCCESS\n}"
        if yield_body not in text or not re.search(r"_wasiESUCCESS\s+int32\s*=\s*0\b", text):
            raise ValueError("stackless reclaimer requires successful memory-free host yield")
        return anchor.sub(lambda m: m[0] + "\tThreadLifetime *ThreadLifetime\n", text, count=1)
    if name not in FUNCTIONS:
        return text
    fn, expected = FUNCTIONS[name]
    body = function(text, fn)
    if hashlib.sha256(re.sub(r"\s+", "", body).encode()).hexdigest() != expected:
        raise ValueError("accepted WASIX thread/reclaimer function changed: " + fn)
    if fn == "Fn153":
        anchor = "func Fn153(m *base.Module, l0 int32) {\n"
        return text.replace(anchor, anchor + "\tif base.DeferThreadAllocationFree(m, l0) { return }\n", 1)
    return text
