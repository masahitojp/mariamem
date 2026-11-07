"""Explicit UNQUALIFIED test instrumentation;no generated function-body edits."""
import hashlib
from pathlib import Path
PREIMAGE='e381f829248d859331ec560de111e3d5edabb1be11a84f57fb4458c3dec7de25'
def apply(raw):
 if hashlib.sha256(raw).hexdigest()!=PREIMAGE:raise ValueError('lifetime source preimage changed')
 s=raw.decode()
 s=s.replace('maps    map[uint32]*threadAllocation','maps    map[uint32]*threadAllocation\n nativeCompletionProbe func(uint32)')
 s=s.replace('ptr      uint32','ptr      uint32\n pthread uint32')
 s=s.replace('a := &threadAllocation{ptr: ptr,','a := &threadAllocation{pthread:uint32(td),ptr: ptr,')
 s=s.replace('defer close(a.done)','defer close(a.done)\n if p.nativeCompletionProbe!=nil {p.nativeCompletionProbe(a.pthread)}')
 if s==raw.decode() or 'pthread:uint32(td)' not in s:raise ValueError('lifetime instrumentation anchor changed')
 return s.encode()
