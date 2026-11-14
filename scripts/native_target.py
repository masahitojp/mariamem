"""Supported native build targets; Linux wheels deliberately make no manylinux claim."""
import json
from pathlib import Path
import platform
import re
import subprocess
import struct
import sysconfig

DARWIN = "darwin-arm64"
UBUNTU = "ubuntu24.04-x86_64"
WINDOWS_X86 = "windows-x86_64"
WINDOWS_ARM = "windows-arm64"


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
    if name in (WINDOWS_X86, WINDOWS_ARM):
        arm = name == WINDOWS_ARM
        return {"platform": name, "minimum_windows_build": 22000,
                "architecture": "arm64" if arm else "x86_64", "goos": "windows",
                "goarch": "arm64" if arm else "amd64", "host_name": "mariamem-host.exe",
                "wheel_platform": "win_arm64" if arm else "win_amd64",
                "bundle_name": "mariamem-native-" + name}
    raise ValueError(f"unsupported native target: {name}")


def current_target(root=None):
    system, machine = platform.system(), platform.machine()
    if system == "Windows":
        process = sysconfig.get_platform()
        if process in ("win-amd64", "win-arm64"):
            return target_metadata(WINDOWS_ARM if process == "win-arm64" else WINDOWS_X86, root)
    if system == "Darwin" and machine == "arm64":
        return target_metadata(DARWIN, root)
    if system == "Linux" and machine in ("x86_64", "AMD64"):
        release = platform.freedesktop_os_release()
        if release.get("ID") == "ubuntu" and release.get("VERSION_ID") == "24.04":
            return target_metadata(UBUNTU, root)
    raise ValueError("native build requires macOS 15+ arm64, Ubuntu 24.04 x86_64, or Windows x86_64/arm64")


def manifest_target(manifest, root=None):
    target = target_metadata(manifest.get("platform"), root)
    if target["goos"] == "darwin":
        minimum = manifest.get("minimum_macos")
        if not isinstance(minimum, int) or not 0 < minimum <= target["minimum_macos"]:
            raise ValueError("native manifest does not match the candidate platform")
    elif target["goos"] == "windows":
        if any(manifest.get(k) != target[k] for k in ("architecture", "minimum_windows_build")):
            raise ValueError("native manifest does not match the Windows target")
    elif any(manifest.get(key) != target[key] for key in ("distribution", "version_id", "architecture")):
        raise ValueError("native manifest does not match the candidate platform")
    return target


def platform_fields(target):
    keys = ("platform", "minimum_macos", "distribution", "version_id")
    if target["goos"] == "linux":
        keys += ("architecture",)
    if target["goos"] == "windows":
        keys += ("architecture", "minimum_windows_build")
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


def pe_dependencies(path, target):
    """Verify the Go host's actual PE machine and 64-bit optional header."""
    with Path(path).open('rb') as stream:
        dos = stream.read(64)
        if len(dos) != 64 or dos[:2] != b'MZ':
            raise ValueError('Windows host is not a PE executable')
        offset = struct.unpack_from('<I', dos, 60)[0]
        stream.seek(offset)
        header = stream.read(26)
    expected = 0xAA64 if target['goarch'] == 'arm64' else 0x8664
    if (len(header) != 26 or header[:4] != b'PE\0\0'
            or struct.unpack_from('<H', header, 4)[0] != expected
            or struct.unpack_from('<H', header, 24)[0] != 0x20B):
        raise ValueError('Windows host PE architecture differs from target')
    return {'format': 'PE32+', 'architecture': target['architecture']}
