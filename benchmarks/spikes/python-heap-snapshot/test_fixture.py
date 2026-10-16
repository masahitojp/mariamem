"""Use the repository's existing session Snapshot / function Fork fixtures."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'python'))
import mariamem
import adapter
adapter.install('heap')
import pytest
pytest_plugins=['mariamem.pytest_plugin']
from workflow import connect,query,value,disconnect

@pytest.fixture(scope='session')
def mariamem_options():return {'host_binary':os.environ['SPIKE_BROKER']}

@pytest.fixture(scope='session')
def mariamem_snapshot(mariamem_server):
    c=connect(mariamem_server);query(c,'CREATE TABLE items(id INT PRIMARY KEY,v INT) ENGINE=InnoDB');query(c,'INSERT INTO items VALUES(1,10)');c.commit();disconnect(mariamem_server,c)
    with mariamem_server.snapshot() as s:yield s

@pytest.fixture(scope='session',autouse=True)
def capture_session():
    yield
    assert all(s.done and s.proc.poll()==0 for s in adapter.SESSIONS)

def test_insert(mariamem_fork):
    c=connect(mariamem_fork);assert value(c,'SELECT COUNT(*) FROM items')==1;query(c,'INSERT INTO items VALUES(2,20)');c.commit();assert value(c,'SELECT COUNT(*) FROM items')==2;disconnect(mariamem_fork,c)

def test_pristine(mariamem_fork):
    c=connect(mariamem_fork);assert value(c,'SELECT COUNT(*) FROM items')==1;assert value(c,'SELECT v FROM items')==10;disconnect(mariamem_fork,c)
