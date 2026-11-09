"""Explicit untagged-preview input identity, without weakening tagged baselines."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from guest_input_resolver import resolve_inputs, InputError


def encode(v):return (json.dumps(v,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()


class PreviewInputsTests(unittest.TestCase):
    def setUp(self):
        self.registry=json.loads((ROOT/'guest/versions/registry.json').read_text())
        self.entry=self.registry['selections']['13.2.0/native-text']
        self.descriptor=json.loads((ROOT/self.entry['descriptor']['file']).read_text())
        self.overrides={}

    def run_input(self):
        raw=encode(self.descriptor)
        self.entry['descriptor']['sha256']=sha(raw)
        self.overrides[self.entry['descriptor']['file']]=raw
        return resolve_inputs(encode(self.registry),'13.2.0','native-text',
                              lambda name:self.overrides[name] if name in self.overrides else (ROOT/name).read_bytes())

    def test_actual_preview_has_no_invented_tag(self):
        value=self.run_input()
        self.assertIsNone(value['guest_input']['tag_object_sha'])
        self.assertEqual(value['preview_source']['source_commit'],value['guest_input']['source_commit'])
        self.assertEqual(value['prepared_pin']['source_commit'],value['guest_input']['source_commit'])
        self.assertNotIn('historical_prepared_pin',value)

    def test_tag_is_still_required_for_schema_one(self):
        self.descriptor['schema']=1
        with self.assertRaisesRegex(InputError,'invalid identity'):self.run_input()

    def test_cannot_use_a_commit_as_a_preview_tag(self):
        self.descriptor['guest_input']['tag_object_sha']=self.descriptor['guest_input']['source_commit']
        with self.assertRaisesRegex(InputError,'preview source identity'):self.run_input()

    def test_missing_unknown_or_mismatched_preview_provenance(self):
        original=copy.deepcopy(self.descriptor)
        for field,value in [('kind','branch-head'),('release','13.0.2'),('source_commit','0'*40),('archive_url','https://example.invalid/source'),('archive_sha256','bad'),('upstream_ref','refs/heads/main')]:
            with self.subTest(field=field):
                self.descriptor=copy.deepcopy(original);self.descriptor['preview_source'][field]=value
                with self.assertRaises(InputError):self.run_input()
        self.descriptor=copy.deepcopy(original);del self.descriptor['preview_source']
        with self.assertRaises(InputError):self.run_input()

    def test_published_revision_must_match_even_after_rehashing(self):
        reference=self.descriptor['files'][self.descriptor['preview_source']['revision_file']]
        raw=b'#define SOURCE_REVISION "'+b'0'*40+b'"\n'
        self.overrides[reference['file']]=raw;reference['sha256']=sha(raw)
        with self.assertRaisesRegex(InputError,'published preview source revision'):self.run_input()

    def test_production_selector_still_uses_tagged_1233(self):
        registry=encode(self.registry)
        value=resolve_inputs(registry,'12.3.3','legacy-full',lambda name:(ROOT/name).read_bytes())
        self.assertEqual(value['guest_input']['version'],'12.3.3')
        self.assertIsNotNone(value['guest_input']['tag_object_sha'])
        self.assertNotIn('preview_source',value)


if __name__=='__main__':unittest.main()
