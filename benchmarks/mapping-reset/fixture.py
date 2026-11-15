import hashlib,json,re,struct
from pathlib import Path

def make(root,temp):
    layout=json.loads((root/'internal/generatedgo/image/layout.json').read_text())
    text=(root/'internal/generatedgo/code/generated.go').read_text()
    literal=re.search(r'var wasm2goData_data_bin = \[\]byte\("((?:\\x[0-9a-f]{2})+)"\)',text).group(1)
    data=bytes.fromhex(literal.replace('\\x',''))
    memory=bytearray(layout['memory_bytes'])
    for target,a,b in [(8388608,0,9730278),(18118912,9730278,10372898),(18761536,10372898,10373403)]:memory[target:target+b-a]=data[a:b]
    struct.pack_into('<I',memory,27744624,2)
    assert hashlib.sha256(memory).hexdigest()==layout['memory_sha256'],'constructor oracle mismatch: stop'
    page=16384;ranges=[]
    with (temp/'image').open('wb') as f:
        f.truncate(2<<30)
        for off in range(0,len(memory),page):
            chunk=memory[off:off+page]
            if any(chunk):
                f.seek(off);f.write(chunk)
                if ranges and ranges[-1]['Offset']+ranges[-1]['Length']==off:ranges[-1]['Length']+=page
                else:ranges.append({'Offset':off,'Length':page})
    (temp/'ranges.json').write_text(json.dumps(ranges))
    return {'initial_sha256':layout['memory_sha256'],'ranges':ranges,'page_bytes':page,'recipe':'reconstruct Fn67 active segments and completion flag; verify complete initial-memory SHA256'}
