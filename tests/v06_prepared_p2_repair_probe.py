"""Additional repair controls; original20/22/TIME oracles remain unchanged."""
import argparse
import json
from pathlib import Path
import struct

import v06_prepared_p2_matrix as matrix
from v06_prepared_p1_probe import close_ping, prepare


def parameter_states(typ,value,unsigned):
    def scenario(c,call):
        sid,_=prepare(c,'SELECT ? AS v')
        for current in [None,value]:
            reply=call(sid,[(typ,unsigned,current)])
            assert reply['kind']=='rows'
            assert call(sid,[(typ,unsigned,current)],True)==reply
        call(sid,[(3,False,struct.pack('<i',17))])
        assert call(sid,[(typ,unsigned,value)])['kind']=='rows'
        close_ping(c,sid)
    return scenario


def schema_single_execution(c,call):
    matrix.query(c,'CREATE TEMPORARY TABLE p2_repair_schema(v INT) ENGINE=InnoDB')
    matrix.query(c,'INSERT INTO p2_repair_schema VALUES(7)')
    matrix.query(c,'SET @p2_executions=0')
    sid,_=prepare(c,'SELECT @p2_executions:=@p2_executions+1 AS executions, s.* FROM p2_repair_schema AS s')
    reply=call(sid);assert reply['kind']=='rows' and len(reply['columns'])==2
    matrix.query(c,'ALTER TABLE p2_repair_schema ADD COLUMN extra INT DEFAULT 11')
    reply=call(sid);assert reply['kind']=='rows' and len(reply['columns'])==3
    assert matrix.query(c,'SELECT @p2_executions')==((2,),)
    matrix.query(c,'ALTER TABLE p2_repair_schema DROP COLUMN extra')
    reply=call(sid);assert reply['kind']=='rows' and len(reply['columns'])==2
    assert matrix.query(c,'SELECT @p2_executions')==((3,),)
    close_ping(c,sid)


def scenarios():
    values={16:b'\x01',247:b'alpha',248:b'alpha',255:b'\0\xff',
            9:struct.pack('<i',-8388608),13:struct.pack('<H',2024),
            14:struct.pack('<HBB',2024,2,29)}
    cases={f'type-{typ}-unsigned-{unsigned}':parameter_states(typ,value,unsigned)
           for typ,value in values.items() for unsigned in [False,True]}
    cases['schema-grow-shrink-single-execution']=schema_single_execution
    return cases


def main():
    p=argparse.ArgumentParser();s=p.add_mutually_exclusive_group(required=True)
    s.add_argument('--native-port',type=int);s.add_argument('--host')
    p.add_argument('--reference',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result={'result':'FAIL'}
    try:
        info=None if args.host else dict(host='127.0.0.1',port=args.native_port,user='root',database='test')
        result=matrix.exercise(info=info,host=args.host,selected=scenarios())
        result['scope']='P2 repair: raw types/null/reuse/transitions and single-execution metadata growth/shrink; not full P2-P6'
        if args.reference:
            expected=json.loads(args.reference.read_text())
            observed,wanted=matrix.comparable(result['cases']),matrix.comparable(expected['cases'])
            result['different_cases']=[name for name in sorted(set(observed)|set(wanted)) if observed.get(name)!=wanted.get(name)]
            result['native_comparison']='FAIL' if result['different_cases'] or result['failures'] else 'PASS'
            if result['native_comparison']=='FAIL':result['result']='FAIL'
        assert result['result']=='PASS',json.dumps({k:result.get(k) for k in ['failures','different_cases']})
    except Exception as error:
        result.update(result='FAIL',error=repr(error));raise
    finally:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
