"""Test import reader correctness/error paths using the exact experimental patch."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'benchmarks'))
spec=importlib.util.spec_from_file_location('restore_read_ab',ROOT/'benchmarks/restore_read_ab.py')
ab=importlib.util.module_from_spec(spec);spec.loader.exec_module(ab)


def section(name):
    text=(ROOT/'guest/experimental.patch').read_text()
    start=text.index('+++ b/wasm/'+name+'\n')
    body=text[start:].split('\n--- ',1)[0]
    return body


@pytest.fixture
def copy_binary(tmp_path):
    if not shutil.which('cc'):pytest.skip('C compiler required')
    (tmp_path/'wasm').mkdir()
    (tmp_path/'wasm/snapshot_fs.inc').write_text((ROOT/'guest/snapshot_fs.inc').read_text())
    patch='--- a/wasm/snapshot_fs.inc\n'+section('snapshot_fs.inc')+'\n'
    subprocess.run(['patch','-p1'],cwd=tmp_path,input=patch,text=True,capture_output=True,check=True)
    lines=section('restore_experiment.inc').splitlines()[2:]
    assert all(line.startswith('+') for line in lines)
    (tmp_path/'wasm/restore_experiment.inc').write_text('\n'.join(line[1:] for line in lines)+'\n')
    prefix='''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <errno.h>
#include <sys/stat.h>
#include <unistd.h>
static struct {int enabled;} startup_timing={1};
static ssize_t test_read(int fd,void *buf,size_t n) {
 const char *fault=getenv("TEST_READ_FAULT");
 static int interrupted;
 if(fault && !strcmp(fault,"error")){errno=EIO;return -1;}
 if(fault && !strcmp(fault,"short")){
   if(!interrupted++){errno=EINTR;return -1;}
   if(n>7)n=7;
 }
 return read(fd,buf,n);
}
#define RR_NATIVE_READ test_read
#include "snapshot_fs.inc"
int main(int argc,char **argv){
 if(argc!=4)return 2;rr_guest_begin();if(rr_begin())return 3;
 int rc=snapshot_copy(argv[1],argv[2],0);rr_end();if(rc)return 4;
 if(snapshot_copy(argv[2],argv[3],0))return 5;
 fputs("{\\"ok\\":true",stdout);rr_write_stats(stdout);puts("}");return 0;
}
'''
    source=tmp_path/'wasm/main.c';source.write_text(prefix)
    target=tmp_path/'copy';subprocess.run(['cc','-std=gnu11','-O2',str(source),'-o',str(target)],check=True,capture_output=True)
    return target


@pytest.mark.parametrize('mode,fault',[('stdio',''),('direct',''),('direct','short')])
def test_restored_and_exported_contents_match(copy_binary,tmp_path,mode,fault):
    source=tmp_path/'source';(source/'nested').mkdir(parents=True)
    (source/'nested/payload').write_bytes(bytes(range(256))*256+b'tail')
    (source/'empty').write_bytes(b'')
    dest=tmp_path/'destination';export=tmp_path/'export'
    result=subprocess.run([copy_binary,source,dest,export],env={**os.environ,'MARIAMEM_EXPERIMENT_RESTORE':mode,'TEST_READ_FAULT':fault},capture_output=True,text=True,check=True)
    assert ab.inventory(source)==ab.inventory(dest)==ab.inventory(export)
    stats=json.loads(result.stdout)['restore_copy']
    assert stats['mode']==mode and stats['bytes']==stats['written_bytes']==65540
    assert stats['files']==2 and stats['chunk_bytes']==65536
    # Counters must exclude the unchanged stdio export performed after rr_end.
    assert stats['read_calls']==4 if fault!='short' else stats['read_calls']>4


def test_failures_do_not_succeed(copy_binary,tmp_path):
    source=tmp_path/'source';source.mkdir();(source/'file').write_bytes(b'payload')
    for fault in ['error']:
        result=subprocess.run([copy_binary,source,tmp_path/'error',tmp_path/'export'],env={**os.environ,'MARIAMEM_EXPERIMENT_RESTORE':'direct','TEST_READ_FAULT':fault},capture_output=True)
        assert result.returncode!=0
    occupied=tmp_path/'occupied';occupied.mkdir()
    assert subprocess.run([copy_binary,source,occupied,tmp_path/'export'],capture_output=True).returncode!=0
    (source/'link').symlink_to('file')
    assert subprocess.run([copy_binary,source,tmp_path/'linked',tmp_path/'export'],capture_output=True).returncode!=0


def test_stats_fail_closed():
    with pytest.raises(ValueError,match='reconciliation'):
        ab.validate_stats({'stage_timings':{'host':{'guest':{'restore_copy':{'mode':'stdio','chunk_bytes':65536,'bytes':0,'written_bytes':0,'files':0,'read_calls':0}}}}},'direct',{'data_bytes':0,'file_bytes':{}})
