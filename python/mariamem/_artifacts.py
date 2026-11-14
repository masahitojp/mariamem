"""Private generated-Go host discovery; no WASM/runtime provisioning."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import sysconfig

NATIVE_ROOT = Path(__file__).parent / "_native"


class ArtifactError(RuntimeError):
    """Private discovery failure translated to the public HostError."""

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def _available(path, executable):
    if not path.is_file():
        raise ArtifactError(f"host input is unavailable: {path}; install the matching platform wheel", "native_unavailable")
    if executable and not os.access(path, os.X_OK):
        raise ArtifactError(f"host input is not executable: {path}; reinstall the matching wheel preserving executable permissions", "native_unavailable")


def _os_release():
    values = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value.strip("\"'")
    return values


def _platform_identity():
    detected = f"{platform.system()} / {platform.machine()}"
    if platform.system() == "Windows":
        process = sysconfig.get_platform()
        if process in ("win-amd64", "win-arm64"):
            build = sys.getwindowsversion().build
            if build < 22000:
                raise ArtifactError(f"Windows build {build} is unsupported; requires build 22000+", "unsupported_platform")
            return "windows-arm64" if process == "win-arm64" else "windows-x86_64"
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "darwin-arm64"
    if platform.system() == "Linux" and platform.machine() == "x86_64":
        try:
            release = _os_release()
        except OSError as exc:
            raise ArtifactError("cannot identify Ubuntu release", "unsupported_platform") from exc
        detected += f" (ID={release.get('ID')!r}, VERSION_ID={release.get('VERSION_ID')!r})"
        if release.get("ID") == "ubuntu" and release.get("VERSION_ID") == "24.04":
            return "ubuntu24.04-x86_64"
    raise ArtifactError(f"unsupported platform: detected {detected}; supported: macOS 15+ arm64, Linux x86_64/aarch64 (glibc 2.28+ or musl 1.2+), or Windows build 22000+ x86_64/arm64. Run on a supported platform with its matching wheel.", "unsupported_platform")


def _portable_linux(manifest):
    arch = {"x86_64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}.get(platform.machine())
    if platform.system() != "Linux" or arch is None or manifest.get("platform") != "linux-" + arch:
        raise ArtifactError("portable Linux wheel CPU does not match this host", "unsupported_platform")
    if (manifest.get("architecture") != arch or manifest.get("minimum_glibc") != "2.28"
            or manifest.get("minimum_musl") != "1.2"):
        raise ArtifactError("portable Linux wheel has invalid minimum conditions", "artifact_mismatch")
    libc, version = platform.libc_ver()
    if libc == "glibc":
        floor = (2, 28)
    else:
        # Alpine's musl loader is also its libc; do not use distro names as ABI evidence.
        loader = Path("/lib") / ("ld-musl-" + arch + ".so.1")
        try:
            result = subprocess.run([str(loader)], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ArtifactError("cannot identify Linux libc; requires glibc 2.28+ or musl 1.2+", "unsupported_platform") from exc
        match = re.search(r"musl libc.*?Version (\d+\.\d+(?:\.\d+)?)", result.stdout + result.stderr, re.S)
        if not match:
            raise ArtifactError("cannot identify musl version", "unsupported_platform")
        libc, version, floor = "musl", match[1], (1, 2)
    if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version) or tuple(map(int, version.split("."))) < floor:
        raise ArtifactError(f"unsupported {libc} {version}; requires glibc 2.28+ or musl 1.2+", "unsupported_platform")
    return "linux-" + arch


def resolve(host_binary=None, runtime=None, module=None):
    if runtime is not None or module is not None or os.environ.get("MARIAMEM_NATIVE_DIR"):
        raise ArtifactError("legacy runtime/module/MARIAMEM_NATIVE_DIR overrides are retired; use the generated-Go host-only wheel", "artifact_mismatch")
    values = {"host_binary": None, "runtime": None, "module": None}
    if host_binary is not None:
        path = Path(host_binary).expanduser().resolve()
        _available(path, True)
        values["host_binary"] = str(path)
        return values
    identity = None if platform.system() == "Linux" else _platform_identity()
    root = NATIVE_ROOT
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        identity = (_portable_linux(manifest) if manifest.get("platform") in ("linux-x86_64", "linux-aarch64")
                    else identity or _platform_identity())
        if manifest["version"] != 1:
            raise ValueError(f"expected host manifest format 1, got {manifest['version']!r}")
        if manifest.get("platform") != identity:
            raise ValueError(f"host wheel platform mismatch: expected {identity!r}, got {manifest.get('platform')!r}")
        if identity == "ubuntu24.04-x86_64" and (
            manifest.get("distribution") != "ubuntu"
            or manifest.get("version_id") != "24.04"
            or manifest.get("architecture") != "x86_64"
        ):
            raise ValueError("expected Ubuntu 24.04 x86_64 wheel metadata")
        if identity.startswith("windows-") and (
            manifest.get("architecture") != ("arm64" if identity == "windows-arm64" else "x86_64")
            or manifest.get("minimum_windows_build") != 22000
        ):
            raise ValueError("expected matching Windows CPU and minimum OS metadata")
        if identity == "darwin-arm64" and int(platform.mac_ver()[0].split(".")[0]) < manifest["minimum_macos"]:
            raise ArtifactError(f"detected macOS {platform.mac_ver()[0]}; this wheel requires macOS {manifest['minimum_macos']} or newer. Upgrade macOS or use another supported platform.", "unsupported_platform")
        if manifest.get("runtime_kind") != "generated-go":
            raise ArtifactError("this package requires a generated-Go host-only wheel; legacy runtime bundles are retired", "artifact_mismatch")
        host_name = "mariamem-host.exe" if identity.startswith("windows-") else "mariamem-host"
        path = root / host_name
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        expected = manifest["sha256"][host_name]
        if digest.hexdigest() != expected:
            raise ArtifactError(f"artifact hash mismatch: {path}; expected SHA256 {expected}, got {digest.hexdigest()}. Reinstall the matching wheel; do not mix artifacts.", "artifact_mismatch")
        _available(path, True)
        values["host_binary"] = str(path.resolve())
    except ArtifactError:
        raise
    except (OSError, KeyError, ValueError) as exc:
        code = "native_unavailable" if isinstance(exc, OSError) else "artifact_mismatch"
        raise ArtifactError(f"mariamem host wheel is missing or invalid: {root}. Install the platform wheel, or use host_binary for a local generated-Go host. ({exc})", code) from exc
    return values
