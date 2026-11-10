import concurrent.futures,hashlib,json,pathlib,sys,urllib.request
here=pathlib.Path(__file__).resolve().parent;out=pathlib.Path(sys.argv[1]);out.mkdir(exist_ok=True)
rows=json.loads((here/'packages.json').read_text())['packages']
items=[('https://archive.mariadb.org/mariadb-12.3.3/repo/ubuntu/'+r['Filename'],pathlib.Path(r['Filename']).name,r['SHA256']) for r in rows]
items.append(('https://raw.githubusercontent.com/shyim/lite4mariadb/24be9371a2f6c71250a2356631ad6feab2280b02/wasm/lite4mariadb.c','lite4mariadb.c','c0a959b6755d3463de31d9d08d2a43031cc418a332768a0956ebfd5046e15526'))
def fetch(item):
 url,name,expected=item;p=out/name
 if not p.exists():p.write_bytes(urllib.request.urlopen(url,timeout=90).read())
 assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,name
 print(name,expected,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(fetch,items))
