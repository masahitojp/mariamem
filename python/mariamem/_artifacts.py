"""Private generated-Go host discovery; no WASM/runtime provisioning."""
import hashlib
import json
import os
from pathlib import Path
import platform

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
    raise ArtifactError(f"unsupported platform: detected {detected}; supported: macOS 15+ arm64 or Ubuntu 24.04 x86_64. Run on a supported platform with its matching wheel.", "unsupported_platform")


def resolve(host_binary=None, runtime=None, module=None):
    if runtime is not None or module is not None or os.environ.get("MARIAMEM_NATIVE_DIR"):
        raise ArtifactError("legacy runtime/module/MARIAMEM_NATIVE_DIR overrides are retired; use the generated-Go host-only wheel", "artifact_mismatch")
    values = {"host_binary": None, "runtime": None, "module": None}
    if host_binary is not None:
        path = Path(host_binary).expanduser().resolve()
        _available(path, True)
        values["host_binary"] = str(path)
        return values
    identity = _platform_identity()
    root = NATIVE_ROOT
    try:
        manifest = json.loads((root / "manifest.json").read_text())
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
        if identity == "darwin-arm64" and int(platform.mac_ver()[0].split(".")[0]) < manifest["minimum_macos"]:
            raise ArtifactError(f"detected macOS {platform.mac_ver()[0]}; this wheel requires macOS {manifest['minimum_macos']} or newer. Upgrade macOS or use another supported platform.", "unsupported_platform")
        if manifest.get("runtime_kind") != "generated-go":
            raise ArtifactError("this package requires a generated-Go host-only wheel; legacy runtime bundles are retired", "artifact_mismatch")
        path = root / "mariamem-host"
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        expected = manifest["sha256"]["mariamem-host"]
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
