"""Native build targets, retaining the historical Ubuntu release identity."""
import json
import platform
import re
import subprocess

DARWIN = "darwin-arm64"
UBUNTU = "ubuntu24.04-x86_64"
LINUX_X86 = "linux-x86_64"
LINUX_ARM = "linux-aarch64"


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
    if name in (LINUX_X86, LINUX_ARM):
        arch = "x86_64" if name == LINUX_X86 else "aarch64"
        return {"platform": name, "architecture": arch, "goos": "linux",
                "goarch": "amd64" if arch == "x86_64" else "arm64",
                "minimum_glibc": "2.28", "minimum_musl": "1.2",
                "wheel_platform": f"manylinux_2_28_{arch}.musllinux_1_2_{arch}",
                "bundle_name": f"mariamem-native-{name}"}
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
    elif target["platform"] in (LINUX_X86, LINUX_ARM):
        if any(manifest.get(k) != target[k] for k in ("architecture", "minimum_glibc", "minimum_musl")):
            raise ValueError("native manifest does not match the portable Linux target")
    elif any(manifest.get(key) != target[key] for key in ("distribution", "version_id", "architecture")):
        raise ValueError("native manifest does not match the candidate platform")
    return target


def platform_fields(target):
    keys = ("platform", "minimum_macos", "distribution", "version_id")
    if target["goos"] == "linux":
        keys += ("architecture", "minimum_glibc", "minimum_musl")
    return {key: target[key] for key in keys if key in target}


def elf_dependencies(path, target=None):
    if target and target["platform"] in (LINUX_X86, LINUX_ARM):
        header = subprocess.check_output(["readelf", "-h", str(path)], text=True)
        programs = subprocess.check_output(["readelf", "-l", str(path)], text=True)
        dynamic = subprocess.check_output(["readelf", "-d", str(path)], text=True)
        versions = subprocess.check_output(["readelf", "--version-info", str(path)], text=True)
        machine = "Advanced Micro Devices X86-64" if target["goarch"] == "amd64" else "AArch64"
        if machine not in header or "ELF64" not in header or "little endian" not in header:
            raise ValueError("ELF architecture/endianness differs from Linux target")
        if re.search(r"\bINTERP\b", programs) or "(NEEDED)" in dynamic or re.search(r"\b(?:GLIBC|GLIBCXX)_", versions):
            raise ValueError("portable Linux host must have no interpreter or shared-library dependency")
        return {"format": "ELF-" + target["architecture"], "needed": [], "glibc_versions": [],
                "interpreter": None, "static": True, "wheel_platform": target["wheel_platform"],
                "runtime_acceptance_required": True}
    return legacy_elf_dependencies(path)


def legacy_elf_dependencies(path):
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
