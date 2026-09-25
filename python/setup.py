from setuptools import setup
from wheel.bdist_wheel import bdist_wheel
import os
import json
from pathlib import Path
import runpy

TARGET = json.loads((Path(__file__).parent / "deployment_target.json").read_text())
PYTHON_VERSION = runpy.run_path(str(Path(__file__).parent / "mariamem/_version.py"))["PYTHON_VERSION"]


class PlatformWheel(bdist_wheel):
    def finalize_options(self):
        super().finalize_options()
        self.root_is_pure = False
        expected = TARGET["wheel_platform"]
        if os.environ.get("MARIAMEM_WHEEL_PLATFORM", expected) != expected:
            raise ValueError("Wheel platform must match deployment_target.json")
        manifest_path = Path(__file__).parent / "mariamem/_native/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if manifest["minimum_macos"] != TARGET["minimum_macos"] or manifest["platform"] != "darwin-" + TARGET["architecture"]:
            raise ValueError("Native manifest must match deployment_target.json; run scripts/build_alpha.py")
        if manifest.get("package_version") != PYTHON_VERSION:
            raise ValueError("Native manifest version is stale; run scripts/build_alpha.py")
        self.plat_name = expected
        self.plat_name_supplied = True

    def get_tag(self):
        _, _, platform = super().get_tag()
        return "py3", "none", platform


setup(version=PYTHON_VERSION, cmdclass={"bdist_wheel": PlatformWheel})
