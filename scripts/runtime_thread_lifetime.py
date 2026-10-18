"""Bind the accepted WASIX allocation ABI to the handwritten completion owner.

This adapter adds one private Module field and a pre-allocator free handoff.
Never edit generated output. Reject changed allocation/entry/reclaimer code
before installing the handoff. Each supported byte identity has an explicit
reviewed binding; this is not a generic ABI recognizer.
"""
import hashlib
import re

GUEST_SHA256 = "7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09"
FUNCTIONS = {
    "code/p3/p3_pure.go": ("Fn153", "b1d381957fd1d352e7ab741f3e7330c5ac77e1b6f20ddd465c497f51f7389d5b"),
    "code/p8/p8_pure.go": ("Fn131", "e31e88a8637fb60e5f197014ae2c4dd0afe2fcd05c6f850c13d24ff0b0810932"),
    "code/p5/p5_pure.go": ("Fn216", "7d0e1dee8ae23b77990a1c0ce7b2f56988a67f80003d6962a25dc2159b3de7eb"),
}


# Experiment-only additional byte identity. Keep canonical defaults and their
# mutation oracles intact. No wildcard, address normalization or runtime fallback.
PREPARED_SPIKE_GUEST = "e8f1b15e69194c860101496ed02ec684e34ad042bb3f6048630805ba656208ac"
PREPARED_SPIKE_FUNCTIONS = {
    "code/p3/p3_pure.go": ("Fn153", "7700544cce65958d2073cb961140bed4c7b3b0b33f658b28ac0851370a12b43f"),
    "code/p8/p8_pure.go": FUNCTIONS["code/p8/p8_pure.go"],
    "code/p5/p5_pure.go": ("Fn216", "16f465fc8b73be894545ec6bc525658bd2a7d27257dba87fe4c3802fb7e00362"),
}
# This continuation has byte-identical allocation/entry/free functions and
# data image to the prepared spike. Bind its whole guest identity explicitly;
# keep checking every body, not a wildcard or normalized-address recognizer.
MULTI_SPIKE_GUEST = "1fabf31ced768f12bd60ba2f0c4c79110fbbe883c440bfa4c9ee63d834b6c179"
OPTION_SPIKE_GUEST = "55c5d4910459c87b5e1e00eb999506acc661ea0eaa3a794662db647bd124c953"
REVIEWED_BINDINGS = {GUEST_SHA256: FUNCTIONS, PREPARED_SPIKE_GUEST: PREPARED_SPIKE_FUNCTIONS,
                     MULTI_SPIKE_GUEST: PREPARED_SPIKE_FUNCTIONS,
                     OPTION_SPIKE_GUEST: PREPARED_SPIKE_FUNCTIONS}


def validate_inputs(guest_sha256, candidate_files):
    required = {"generated/base/base.go", *("generated/" + p.removeprefix("code/") for p in FUNCTIONS)}
    if guest_sha256 not in REVIEWED_BINDINGS or not required <= set(candidate_files):
        raise ValueError("unreviewed guest/worker allocation binding inputs")


def function(text, name):
    starts = list(re.finditer(r"(?m)^func " + name + r"\(", text))
    if len(starts) != 1:
        raise ValueError("thread allocation binding missing/duplicate: " + name)
    tail = text[starts[0].start():]
    following = re.search(r"\nfunc Fn\d+\(", tail)
    return tail[:following.start()] if following else tail


def apply(name, text, *, guest_sha256=GUEST_SHA256):
    if guest_sha256 not in REVIEWED_BINDINGS:
        raise ValueError("unreviewed guest/worker allocation binding inputs")
    functions = REVIEWED_BINDINGS[guest_sha256]
    if name == "code/base/base.go":
        anchor = re.compile(r"(?m)^\s*ThreadStart\s+func\(\*Module, int32, int32\)\n")
        if len(anchor.findall(text)) != 1 or re.search(r"(?m)^\s*ThreadLifetime\s+\*ThreadLifetime", text):
            raise ValueError("thread allocation Module shape changed")
        yield_body = "func (w *WasiStubs) Sched_yield(m *Module) int32 {\n\truntime.Gosched()\n\treturn _wasiESUCCESS\n}"
        if yield_body not in text or not re.search(r"_wasiESUCCESS\s+int32\s*=\s*0\b", text):
            raise ValueError("stackless reclaimer requires successful memory-free host yield")
        return anchor.sub(lambda m: m[0] + "\tThreadLifetime *ThreadLifetime\n", text, count=1)
    if name not in functions:
        return text
    fn, expected = functions[name]
    body = function(text, fn)
    if hashlib.sha256(re.sub(r"\s+", "", body).encode()).hexdigest() != expected:
        raise ValueError("accepted WASIX thread/reclaimer function changed: " + fn)
    if fn == "Fn153":
        anchor = "func Fn153(m *base.Module, l0 int32) {\n"
        return text.replace(anchor, anchor + "\tif base.DeferThreadAllocationFree(m, l0) { return }\n", 1)
    return text
