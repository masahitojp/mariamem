"""Supported native build targets; Linux wheels deliberately make no manylinux claim."""
import json
import platform
import re
import subprocess

DARWIN = "darwin-arm64"
UBUNTU = "ubuntu24.04-x86_64"


def target_metadata(name, root=None):
    if name == DARWIN:
        floor = 15
        if root is not None:
            floor = json.loads((root / "python/deployment_target.json").read_text())["minimum_macos"]
        return {"platform": DARWIN, "minimum_macos": floor, "architecture": "arm64",
                "goos": "darwin", "goarch": "arm64", "wheel_platform": f"macosx_{floor}_0_arm64",
                "runtime_input": "wasmer", "bundle_name": "mariamem-native-darwin-arm64"}
    if name == UBUNTU:
        return {"platform": UBUNTU, "distribution": "ubuntu", "version_id": "24.04",
                "architecture": "x86_64", "goos": "linux", "goarch": "amd64",
                "wheel_platform": "linux_x86_64", "runtime_input": "wasmer-linux-x86_64",
                "bundle_name": "mariamem-native-ubuntu24.04-x86_64"}
    raise ValueError(f"unsupported native target: {name}")


def current_target(root=None):
    system, machine = platform.system(), platform.machine()
    if system == "Darwin" and machine == "arm64":
        return target_metadata(DARWIN, root)
    if system == "Linux" and machine in ("x86_64", "AMD64"):
        release = platform.freedesktop_os_release()
        if release.get("ID") == "ubuntu" and release.get("VERSION_ID") == "24.04":
            return target_metadata(UBUNTU, root)
    raise ValueError("native build requires macOS 15+ arm64 or Ubuntu 24.04 x86_64")


def manifest_target(manifest, root=None):
    target = target_metadata(manifest.get("platform"), root)
    if target["goos"] == "darwin":
        minimum = manifest.get("minimum_macos")
        if not isinstance(minimum, int) or not 0 < minimum <= target["minimum_macos"]:
            raise ValueError("native manifest does not match the candidate platform")
    elif any(manifest.get(key) != target[key] for key in ("distribution", "version_id", "architecture")):
        raise ValueError("native manifest does not match the candidate platform")
    return target


def platform_fields(target):
    keys = ("platform", "minimum_macos", "distribution", "version_id")
    if target["goos"] == "linux":
        keys += ("architecture",)
    return {key: target[key] for key in keys if key in target}


def elf_dependencies(path):
    """Record actual ELF dependencies and symbol floors, without asserting manylinux."""
    header = subprocess.check_output(["readelf", "-h", str(path)], text=True)
    if "Advanced Micro Devices X86-64" not in header:
        raise ValueError(f"{path.name} is not an x86_64 ELF binary")
    dynamic = subprocess.check_output(["readelf", "-d", str(path)], text=True)
    versions = subprocess.check_output(["readelf", "--version-info", str(path)], text=True)
    needed = sorted(set(re.findall(r"\(NEEDED\).*\[(.*?)\]", dynamic)))
    glibc = sorted(set(re.findall(r"\bGLIBC_(\d+(?:\.\d+)+)", versions)),
                   key=lambda value: tuple(map(int, value.split("."))))
    # Any non-system library would need an explicit packaging decision.
    allowed = {"libc.so.6", "libm.so.6", "libdl.so.2", "librt.so.1", "libpthread.so.0",
               "libgcc_s.so.1", "libstdc++.so.6"}
    if set(needed) - allowed:
        raise ValueError(f"unexpected shared libraries in {path.name}: {sorted(set(needed) - allowed)}")
    if glibc and tuple(map(int, glibc[-1].split("."))) > (2, 39):
        raise ValueError(f"{path.name} requires GLIBC {glibc[-1]}, above Ubuntu 24.04")
    return {"format": "ELF-x86_64", "needed": needed, "glibc_versions": glibc,
            "wheel_platform": "linux_x86_64", "manylinux_verified": False}
