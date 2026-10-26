"""Collect unchanged native DOM/assertion functions using guest-owned fixtures."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('native_browser_cases',Path(__file__).parent.parent/'e2e_native_control/browser_cases.py')
owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
test_01_commit_order=owner.test_01_commit_order
test_02_fail_after_commit=owner.test_02_fail_after_commit
test_03_next_case_sees_only_baseline=owner.test_03_next_case_sees_only_baseline
