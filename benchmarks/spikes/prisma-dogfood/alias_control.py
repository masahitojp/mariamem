import hashlib,json,struct,subprocess,sys
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root/'python'),str(root/'scripts'),str(root/'tests')]
import mariamem,pymysql
from git_identity import verify_go_binary
from v06_prepared_p1_probe import prepare
from v06_prepared_p2_matrix import execute,query
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
host=root.parent/'temp/mariamem-host'
verify_go_binary(root,host,source)
with mariamem.start(host_binary=host) as owner:
    i=owner.connection_info()
    with pymysql.connect(host=i['host'],port=i['port'],user=i['user'],password=i['password'],autocommit=True) as c:
        sid,_=prepare(c,'SELECT ? AS n')
        values=[(3,False,struct.pack('<i',7))]
        actual=execute(c,sid,values,[])
        alias=execute(c,0xffffffff,values,[])
        healthy=query(c,'SELECT 1')
        assert actual['kind']=='rows' and alias['errno']==1243 and healthy==((1,),)
result={'host_source_commit':source,'control_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'sequential prepare/execute without pipelining','result':'REPRODUCED_UNSUPPORTED_LAST_STATEMENT_ALIAS','actual_statement_id':sid,'actual_id_execute':actual,'last_statement_alias_execute':alias,'healthy_after_error':True}
(root.parent/'evidence/matrix/alias-control.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
