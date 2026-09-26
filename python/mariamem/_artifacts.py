"""Private runtime discovery; applications do not need to manage WASM paths."""
import hashlib
import json
import os
from pathlib import Path
import platform


class ArtifactError(RuntimeError):
    """Private discovery failure translated to the public HostError."""

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def _available(path, executable):
    if not path.is_file():
        raise ArtifactError(f"native input is unavailable: {path}; install the matching platform wheel or re-extract a complete native bundle", "native_unavailable")
    if executable and not os.access(path, os.X_OK):
        raise ArtifactError(f"native input is not executable: {path}; re-extract the native bundle preserving executable permissions", "native_unavailable")


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
    raise ArtifactError(f"unsupported platform: detected {detected}; supported: macOS 15+ arm64 or Ubuntu 24.04 x86_64. Run on a supported platform with its matching wheel/native bundle.", "unsupported_platform")


def resolve(host_binary=None, runtime=None, module=None):
    values = {"host_binary": host_binary, "runtime": runtime, "module": module}
    if all(value is not None for value in values.values()):
        resolved = {key: Path(value).expanduser().resolve() for key, value in values.items()}
        for key, path in resolved.items():
            _available(path, key != "module")
        return {key: str(path) for key, path in resolved.items()}
    identity = _platform_identity()
    root = Path(os.environ.get("MARIAMEM_NATIVE_DIR", Path(__file__).parent / "_native"))
    names = {"host_binary": "mariamem-host", "runtime": "wasmer-headless", "module": "mariamem.wasmu"}
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest["version"] != 1:
            raise ValueError(f"expected native manifest format 1, got {manifest['version']!r}")
        if manifest.get("platform") != identity:
            raise ValueError(f"native bundle platform mismatch: expected {identity!r}, got {manifest.get('platform')!r}")
        if identity == "ubuntu24.04-x86_64" and (
            manifest.get("distribution") != "ubuntu"
            or manifest.get("version_id") != "24.04"
            or manifest.get("architecture") != "x86_64"
        ):
            raise ValueError(f"expected Ubuntu 24.04 x86_64 metadata; got distribution={manifest.get('distribution')!r}, version_id={manifest.get('version_id')!r}, architecture={manifest.get('architecture')!r}")
        if identity == "darwin-arm64" and int(platform.mac_ver()[0].split(".")[0]) < manifest["minimum_macos"]:
            raise ArtifactError(f"detected macOS {platform.mac_ver()[0]}; this bundle requires macOS {manifest['minimum_macos']} or newer. Upgrade macOS or use another supported platform.", "unsupported_platform")
        for key, name in names.items():
            if values[key] is not None:
                path = Path(values[key]).expanduser().resolve()
                _available(path, key != "module")
                values[key] = str(path)
                continue
            path = root / name
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != manifest["sha256"][name]:
                raise ArtifactError(f"artifact hash mismatch: {path}; expected SHA256 {manifest['sha256'][name]}, got {digest.hexdigest()}. Reinstall the matching wheel or re-extract the complete native bundle; do not mix artifacts.", "artifact_mismatch")
            if key != "module" and not os.access(path, os.X_OK):
                raise ArtifactError(f"artifact is not executable: {path}; re-extract the bundle preserving executable permissions", "native_unavailable")
            values[key] = str(path.resolve())
    except ArtifactError:
        raise
    except (OSError, KeyError, ValueError) as exc:
        code = "native_unavailable" if isinstance(exc, OSError) else "artifact_mismatch"
        raise ArtifactError(f"mariamem native bundle is missing or invalid: {root}. Install the platform wheel, or set MARIAMEM_NATIVE_DIR for a local build. ({exc})", code) from exc
    return values
