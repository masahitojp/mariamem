"""Migrate through standard Django test DB creation before Snapshot capture."""
import django
from django.test.utils import setup_databases

django.setup()
setup_databases(verbosity=1, interactive=False, keepdb=False,
                serialized_aliases={'default'})
# This process exits (all its connections close). The test DB stays in the
# disposable source until it is consumed by Snapshot; no private Django patch.
