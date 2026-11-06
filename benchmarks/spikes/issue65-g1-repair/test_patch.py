"""Source seam guards, complementing the real guest/native runtime observations."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[3]
PATCH=(ROOT/'guest/experimental.patch').read_text()
def sections(name):
    return '\n'.join(re.findall(r'(?ms)^--- [^\n]+\n\+\+\+ b/'+re.escape(name)+r'\n(.*?)(?=^--- |\Z)',PATCH))
class RepairGuards(unittest.TestCase):
    def test_rejection_before_dispatch_and_alias_invalidation(self):
        p=sections('sql/sql_parse.cc')
        self.assertLess(p.index('thd->clear_last_stmt();'),p.index('packet_length == 0'))
        self.assertIn('command == COM_SET_OPTION && packet_length != 2',p)
        self.assertIn('packet_length > 1048576',p)
    def test_native_parser_retains_d2_and_checks_consumption(self):
        p=sections('sql/sql_prepare.cc')
        self.assertIn('get_wire_param_length(pos, len, true)',p)
        self.assertIn('if (consume_overdeclared_string)',p)
        self.assertEqual(2,p.count('stmt->thd->mariamem_native_wire && read_pos != data_end'))
        self.assertIn('uint4korr(packet + 5) != 1',p)
        self.assertIn('packet_end != packet && packet[0] > 1',p)
    def test_restore_all_descriptors_after_native_decode_failure(self):
        p=sections('sql/sql_prepare.cc');a=p.index('param_array[i]->mariamem_save_conversion');b=p.index('res= (setup_conversion_functions',a);c=p.index('if (res && saved)',b);d=p.index('param_array[i]->mariamem_restore_conversion',c)
        self.assertLess(a,b);self.assertLess(b,c);self.assertLess(c,d)
        h=sections('sql/item.h')
        for field in ('handler','value_handler','is_unsigned','simple','empty_string_is_null'):
            self.assertIn(field,h)
    def test_unchanged_observation_fixture(self):
        import hashlib
        p=ROOT/'benchmarks/spikes/issue65-prepared-input/g1_test.go.txt'
        self.assertEqual('804f48fa64a4467a879c3fcd65eb14b6a2b8dda53cf4bade570e163eabc0fd77',hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':unittest.main()
