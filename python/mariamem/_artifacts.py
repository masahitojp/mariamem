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
        raise ArtifactError(f"native input is unavailable: {path}", "native_unavailable")
    if executable and not os.access(path, os.X_OK):
        raise ArtifactError(f"native input is not executable: {path}", "native_unavailable")


def resolve(host_binary=None, runtime=None, module=None):
    values = {"host_binary": host_binary, "runtime": runtime, "module": module}
    if all(value is not None for value in values.values()):
        resolved = {key: Path(value).expanduser().resolve() for key, value in values.items()}
        for key, path in resolved.items():
            _available(path, key != "module")
        return {key: str(path) for key, path in resolved.items()}
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ArtifactError("This mariamem alpha supports macOS 15+ arm64 only", "unsupported_platform")
    root = Path(os.environ.get("MARIAMEM_NATIVE_DIR", Path(__file__).parent / "_native"))
    names = {"host_binary": "mariamem-host", "runtime": "wasmer-headless", "module": "mariamem.wasmu"}
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest["version"] != 1:
            raise ValueError("unsupported artifact manifest")
        if int(platform.mac_ver()[0].split(".")[0]) < manifest["minimum_macos"]:
            raise ArtifactError(f"this alpha requires macOS {manifest['minimum_macos']} or newer", "unsupported_platform")
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
                raise ArtifactError(f"artifact hash mismatch: {name}", "artifact_mismatch")
            if key != "module" and not os.access(path, os.X_OK):
                raise ArtifactError(f"artifact is not executable: {name}", "native_unavailable")
            values[key] = str(path.resolve())
    except ArtifactError:
        raise
    except (OSError, KeyError, ValueError) as exc:
        code = "native_unavailable" if isinstance(exc, OSError) else "artifact_mismatch"
        raise ArtifactError(f"mariamem native bundle is missing or invalid: {root}. Install the platform wheel, or set MARIAMEM_NATIVE_DIR for a local build. ({exc})", code) from exc
    return values
