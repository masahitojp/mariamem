"""Policy for optional local xdist; this module acquires no database owner."""
import importlib.metadata

import pytest

KEY = 'mariamem_django_local'


def _versions():
    for package, expected in [('pytest-xdist', '3.8.0'), ('execnet', '2.1.2')]:
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        if actual != expected:
            raise pytest.UsageError(f'Prepared Django local workers require {package}=={expected}')


def validate(config):
    """Validate the controller before spawning, or its explicit worker handoff."""
    if hasattr(config, 'workerinput'):
        if config.workerinput.get(KEY) != 1:
            raise pytest.UsageError('Prepared Django requires local workers created by its own controller')
        _versions()
        return
    count = config.getoption('numprocesses', None)
    gateways = config.getoption('tx', [])
    if not count and not gateways:
        return
    if type(count) is not int or count < 1:
        raise pytest.UsageError('Prepared Django workers require an explicit positive -n N; manual --tx is unsupported')
    if config.getoption('dist', 'no') not in ('load', 'loadscope'):
        raise pytest.UsageError('Prepared Django workers support --dist=load or loadscope')
    if gateways != ['popen'] * count:
        raise pytest.UsageError('Use explicit -n N with its unmodified local popen workers')
    _versions()


def local_specs(specs):
    # Validate actual execnet gateways too; do not trust only CLI normalization.
    if any(not spec.popen or spec.ssh or spec.socket for spec in specs):
        raise pytest.UsageError('Prepared Django supports only local popen workers')
