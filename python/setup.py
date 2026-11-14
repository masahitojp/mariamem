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
        manifest_path = Path(__file__).parent / "mariamem/_native/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("platform") == "ubuntu24.04-x86_64":
            if (manifest.get("distribution") != "ubuntu"
                    or manifest.get("version_id") != "24.04"
                    or manifest.get("architecture") != "x86_64"):
                raise ValueError("Native manifest must identify Ubuntu 24.04 x86_64")
            expected = "linux_x86_64"  # No manylinux compatibility claim.
        elif manifest.get("platform") in ("linux-x86_64", "linux-aarch64"):
            arch = manifest["platform"].removeprefix("linux-")
            if (manifest.get("architecture") != arch or manifest.get("minimum_glibc") != "2.28"
                    or manifest.get("minimum_musl") != "1.2"):
                raise ValueError("Native manifest must identify portable Linux minimums")
            expected = f"manylinux_2_28_{arch}.musllinux_1_2_{arch}"
        elif manifest.get("platform") in ("windows-x86_64", "windows-arm64"):
            arm = manifest["platform"] == "windows-arm64"
            if (manifest.get("architecture") != ("arm64" if arm else "x86_64")
                    or manifest.get("minimum_windows_build") != 22000):
                raise ValueError("Native manifest must identify Windows build 22000+ and CPU")
            expected = "win_arm64" if arm else "win_amd64"
        else:
            expected = TARGET["wheel_platform"]
            if (manifest.get("minimum_macos") != TARGET["minimum_macos"]
                    or manifest.get("platform") != "darwin-" + TARGET["architecture"]):
                raise ValueError("Native manifest must match deployment_target.json; run scripts/build_alpha.py")
        if os.environ.get("MARIAMEM_WHEEL_PLATFORM", expected) != expected:
            raise ValueError("Wheel platform must match native manifest")
        if manifest.get("runtime_kind") != "generated-go":
            raise ValueError("Only generated-Go host-only wheels are supported")
        if manifest.get("package_version") != PYTHON_VERSION:
            raise ValueError("Native manifest version is stale; run scripts/build_alpha.py")
        self.plat_name = expected
        self.plat_name_supplied = True

    def get_tag(self):
        # Preserve compressed platform tags for both Linux libc families.
        return "py3", "none", self.plat_name


license_root = Path(__file__).parent
license_inventory = json.loads((license_root / "license-inventory.json").read_text())
license_names = set(license_inventory["distributed_notices"])
license_files = ["LICENSE", "NOTICE", "THIRD_PARTY_LICENSES"] + ["licenses/"+n for n in sorted(license_names)]
setup(version=PYTHON_VERSION, cmdclass={"bdist_wheel": PlatformWheel}, license_files=license_files)
