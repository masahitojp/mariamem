"""Observe standard runner outcomes; do not change DB setup/teardown semantics."""
import json
import os
from pathlib import Path
from unittest import TextTestResult
from django.test.runner import DiscoverRunner


def record(event, **fields):
    with Path(os.environ['W3_EVENTS']).open('a') as output:
        output.write(json.dumps(dict(event=event, **fields)) + '\n')


class Result(TextTestResult):
    def addSuccess(self, test):
        super().addSuccess(test)
        record('test_passed', name=test.id())


class Runner(DiscoverRunner):
    def get_resultclass(self):
        return Result

    def setup_databases(self, **kwargs):
        record('setup_databases_begin', keepdb=self.keepdb)
        result = super().setup_databases(**kwargs)
        record('setup_databases_end', keepdb=self.keepdb)
        return result

    def teardown_databases(self, old_config, **kwargs):
        record('teardown_databases_begin', keepdb=self.keepdb)
        super().teardown_databases(old_config, **kwargs)
        record('teardown_databases_end', keepdb=self.keepdb)

    def suite_result(self, suite, result, **kwargs):
        Path(os.environ['W3_SUMMARY']).write_text(json.dumps(dict(
            tests=result.testsRun, passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
            failures=[dict(name=t.id(), message=message) for t, message in result.failures],
            errors=[dict(name=t.id(), message=message) for t, message in result.errors],
            skipped=len(result.skipped)), indent=2) + '\n')
        return super().suite_result(suite, result, **kwargs)
