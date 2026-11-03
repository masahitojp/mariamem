"""Daily local-worker admission policy: no optional Django or C driver needed."""
from types import SimpleNamespace

import pytest
from mariamem.django import _xdist, pytest_plugin


def config(**options):
    return SimpleNamespace(getoption=lambda name, default=None: options.get(name, default))


@pytest.fixture(autouse=True)
def versions(monkeypatch):
    monkeypatch.setattr(_xdist.importlib.metadata, 'version',
                        lambda name: {'pytest-xdist':'3.8.0','execnet':'2.1.2'}[name])


def test_serial_needs_no_optional_worker_package(monkeypatch):
    monkeypatch.setattr(_xdist, '_versions', lambda: pytest.fail('unwanted dependency'))
    _xdist.validate(config())
    _xdist.validate(config(numprocesses=0))


@pytest.mark.parametrize('count', [2, 4])
@pytest.mark.parametrize('scheduler', ['load', 'loadscope'])
def test_explicit_local_workers(count, scheduler):
    _xdist.validate(config(numprocesses=count, dist=scheduler, tx=['popen']*count))


@pytest.mark.parametrize('options', [dict(numprocesses=-1),dict(numprocesses=True),
    dict(numprocesses='auto'),dict(tx=['ssh=remote']),
    dict(numprocesses=2,dist='each',tx=['popen']*2),
    dict(numprocesses=2,dist='load',tx=['popen','ssh=remote'])])
def test_unsupported_modes_are_refused(options):
    with pytest.raises(pytest.UsageError):
        _xdist.validate(config(**options))


def test_worker_requires_explicit_controller_handoff():
    worker=config();worker.workerinput={'workerid':'gw0'}
    with pytest.raises(pytest.UsageError,match='own controller'):
        _xdist.validate(worker)
    worker.workerinput[_xdist.KEY]=1
    _xdist.validate(worker)


def test_unknown_worker_versions_refused(monkeypatch):
    monkeypatch.setattr(_xdist.importlib.metadata,'version',lambda name:'future')
    with pytest.raises(pytest.UsageError,match='require'):
        _xdist.validate(config(numprocesses=2,dist='load',tx=['popen']*2))


def test_actual_gateway_checked_and_handoff_is_data_only():
    local=SimpleNamespace(popen=True,ssh=None,socket=None)
    node=SimpleNamespace(gateway=SimpleNamespace(spec=local),workerinput={})
    pytest_plugin.pytest_configure_node(node)
    assert node.workerinput=={_xdist.KEY:1}
    for spec in [SimpleNamespace(popen=False,ssh='remote',socket=None),
                 SimpleNamespace(popen=False,ssh=None,socket='remote')]:
        with pytest.raises(pytest.UsageError,match='local popen'):
            _xdist.local_specs([spec])


@pytest.mark.parametrize('count',['auto','logical'])
def test_symbolic_worker_count_refused_before_xdist_normalizes(count):
    wrapper=pytest_plugin.pytest_cmdline_main(config(numprocesses=count))
    with pytest.raises(pytest.UsageError,match='explicit'):
        next(wrapper)


@pytest.mark.parametrize('options',[dict(tx=['popen']),dict(looponfail=True)])
def test_manual_or_loop_launcher_refused_before_normalization(options):
    with pytest.raises(pytest.UsageError,match='explicit'):
        next(pytest_plugin.pytest_cmdline_main(config(**options)))
