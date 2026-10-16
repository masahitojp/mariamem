"""Detach the pinned MemFS implementation into its handwritten ownership source."""
import hashlib
import re

def apply(text):
    start = text.index('// MemFS is an in-memory')
    end = text.index('// wasiOpen is one entry', start)
    fragment = text[start:end]
    if hashlib.sha256(fragment.encode()).hexdigest() != '5e1dca3d5f4db1b3a80c9a14fb72218ce48316dd729f54053f277dce17759f4a':
        raise ValueError('pinned MemFS preimage changed; review storage integration')
    result = text[:start] + text[end:]
    if result.count('\t"strings"\n') != 1 or re.search(r"\bstrings\.[A-Za-z_]\w*\s*\(", result):
        raise ValueError("review MemFS-only strings import")
    return result.replace('\t"strings"\n', "", 1)


def apply_relative(text):
    changes = (
        ('p.children[leaf] = n', 'p.children[leaf] = n\n d.fs.enroll(n)'),
        ('n.data = n.data[:0]', 'if n.blocks!=nil {if e:=n.blocks.resize(0);e!=nil{return nil,e}}else{n.data=n.data[:0]}'),
        ('int64(len(n.data))', 'n.storageSize()'),
    )
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError('pinned relative MemFS fragment changed: '+old)
        text = text.replace(old, new, 1)
    return text


def apply_mapping(text):
    old = 'node.data = data'
    if text.count(old) != 1:
        raise ValueError('pinned prepared mapping fragment changed')
    return text.replace(old, 'fsys.installMappedStorage(node, data)', 1)
