"""Bounded lossless compact JSON evidence, with exact decoded-byte checksum."""
import base64,hashlib,json,zlib
MAX_RAW=150*1024*1024
MAX_PACKED=12*1024*1024

def pack(value):
 raw=json.dumps(value,separators=(',',':'),ensure_ascii=True).encode();assert len(raw)<=MAX_RAW
 blob=zlib.compress(raw,9);assert len(blob)<=MAX_PACKED
 return {'schema':1,'encoding':'zlib-base64-json','raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),'data':base64.b64encode(blob).decode()}

def unpack(value):
 assert set(value)=={'schema','encoding','raw_bytes','raw_sha256','data'}
 assert value['schema']==1 and value['encoding']=='zlib-base64-json'
 assert type(value['raw_bytes']) is int and 0<value['raw_bytes']<=MAX_RAW
 assert len(value['data'])<=MAX_PACKED*4//3+4
 blob=base64.b64decode(value['data'],validate=True);assert len(blob)<=MAX_PACKED
 decoder=zlib.decompressobj();raw=decoder.decompress(blob,value['raw_bytes']+1)
 assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
 assert len(raw)==value['raw_bytes'] and hashlib.sha256(raw).hexdigest()==value['raw_sha256']
 return json.loads(raw)

def read(path):
 return unpack(json.loads(path.read_text()))
