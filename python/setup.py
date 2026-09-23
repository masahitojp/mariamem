from setuptools import setup
from wheel.bdist_wheel import bdist_wheel
import os
import json
from pathlib import Path

TARGET = json.loads((Path(__file__).parent / "deployment_target.json").read_text())


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
        self.plat_name = expected
        self.plat_name_supplied = True

    def get_tag(self):
        _, _, platform = super().get_tag()
        return "py3", "none", platform


setup(cmdclass={"bdist_wheel": PlatformWheel})
