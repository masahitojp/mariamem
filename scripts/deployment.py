"""Validate native binaries against the declared wheel deployment target."""
import re
import subprocess


def minimum_macos(load_commands):
    versions = []
    for block in re.split(r"Load command \d+", load_commands):
        if re.search(r"cmd LC_BUILD_VERSION\b", block):
            field = "minos"
        elif re.search(r"cmd LC_VERSION_MIN_MACOSX\b", block):
            field = "version"
        else:
            continue
        versions.extend(re.findall(r"^\s*" + field + r"\s+(\d+(?:\.\d+){1,2})\s*$", block, re.M))
    if not versions:
        raise ValueError("Mach-O deployment target not found")
    return max(tuple((list(map(int, v.split('.'))) + [0, 0])[:3]) for v in versions)


def check_binary(path, target):
    output = subprocess.check_output(["otool", "-arch", "arm64", "-l", str(path)], text=True)
    minimum = minimum_macos(output)
    if minimum > (target, 0, 0):
        raise ValueError(f"{path.name} requires macOS {minimum}; candidate target is {target}.0")
    return ".".join(map(str, minimum))
