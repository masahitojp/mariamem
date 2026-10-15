import json,resource
b=bytearray(64*1024*1024)
for i in range(0,len(b),4096):b[i]=1
print(json.dumps({'getrusage_maxrss_raw':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'touched_bytes':len(b)}))
