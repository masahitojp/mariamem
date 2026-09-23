"""Private runtime discovery; applications do not need to manage WASM paths."""
import hashlib
import json
import os
from pathlib import Path
import platform


def resolve(host_binary=None, runtime=None, module=None):
    values = {"host_binary": host_binary, "runtime": runtime, "module": module}
    if all(value is not None for value in values.values()):
        return {key: str(Path(value).expanduser().resolve()) for key, value in values.items()}
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("This mariamem alpha supports macOS arm64 only")
    root = Path(os.environ.get("MARIAMEM_NATIVE_DIR", Path(__file__).parent / "_native"))
    names = {"host_binary": "mariamem-host", "runtime": "wasmer-headless", "module": "mariamem.wasmu"}
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest["version"] != 1:
            raise ValueError("unsupported artifact manifest")
        if int(platform.mac_ver()[0].split(".")[0]) < manifest["minimum_macos"]:
            raise ValueError(f"this alpha requires macOS {manifest['minimum_macos']} or newer")
        for key, name in names.items():
            if values[key] is not None:
                values[key] = str(Path(values[key]).expanduser().resolve())
                continue
            path = root / name
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != manifest["sha256"][name]:
                raise ValueError(f"artifact hash mismatch: {name}")
            if key != "module" and not os.access(path, os.X_OK):
                raise ValueError(f"artifact is not executable: {name}")
            values[key] = str(path.resolve())
    except (OSError, KeyError, ValueError) as exc:
        raise RuntimeError(f"mariamem native bundle is missing or invalid: {root}. Install the platform wheel, or set MARIAMEM_NATIVE_DIR for a local build. ({exc})") from exc
    return values
