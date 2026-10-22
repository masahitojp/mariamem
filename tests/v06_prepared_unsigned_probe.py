"""Additional common-type unsigned/NULL transitions; existing oracles unchanged."""
import struct

from v06_prepared_p1_probe import close_ping,prepare
from v06_prepared_p2_repair_probe import main


def numeric(c,call):
    sid,_=prepare(c,'SELECT ? AS v')
    values=[(8,True,None),(8,True,struct.pack('<Q',2**64-1)),
            (8,False,None),(8,False,struct.pack('<q',-2**63)),
            (8,True,None),(8,True,struct.pack('<Q',2**64-1))]
    for value in values:
        reply=call(sid,[value]);assert reply['kind']=='rows'
        assert call(sid,[value],True)==reply
    close_ping(c,sid)


def text(c,call):
    sid,_=prepare(c,'SELECT ? AS v')
    for unsigned in [True,False,True]:
        for value in [None,b'alpha']:
            reply=call(sid,[(253,unsigned,value)]);assert reply['kind']=='rows'
            assert call(sid,[(253,unsigned,value)],True)==reply
    close_ping(c,sid)


def scenarios():
    return {'numeric-unsigned-null-transitions':numeric,'text-unsigned-null-transitions':text}


if __name__=='__main__':main(scenarios(),scope='unsigned/NULL common-type transitions; not full P2-P6')
