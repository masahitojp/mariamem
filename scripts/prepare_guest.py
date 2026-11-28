#!/usr/bin/env python3
"""Prepare a fresh MariaDB source tree from the public input lock and overlays."""
import json
import re
import shutil
import subprocess
from common import ROOT, LOCK, digest, extract, fetch
from guest_init_hooks import instrument
from guest_experiment import patch_files
from guest_input import descriptor, apply_series
from prepared_auth_keys import write_header
from routine_schema import prepare as prepare_routine_schema
from guest_auth_hooks import prepare as prepare_auth_source

from pathlib import Path


def prepare(root, lock, build, fetch_input, *, selected=None, features=None):
    root, build = Path(root), Path(build)
    source = build / "source"
    if source.exists():
        raise SystemExit("build/source already exists; move it aside before preparing a fresh tree")
    work = build / "unpack"
    work.mkdir(parents=True, exist_ok=False)
    guest_input = descriptor(root, lock) if selected is None else selected
    features = ["uca", "lexer", "startup-concurrency"] if features is None else features
    uca_prepared = None
    lexer_prepared = None
    startup_concurrency = None
    for name in (guest_input["source_input"], "lite4mariadb", "libmariadb", "wolfssl"):
        extract(fetch_input(name), work / name)
    recipe = next((work / "lite4mariadb").iterdir())
    main = next((work / guest_input["source_input"]).iterdir())
    for name, expected in guest_input["recipe_files_sha256"].items():
        if digest(recipe / name) != expected:
            raise ValueError("guest recipe file identity mismatch: " + name)
        target = main / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(recipe / name, target)
    shutil.move(str(main), source)
    for name, relative in (("libmariadb", "libmariadb"), ("wolfssl", "extra/wolfssl/wolfssl")):
        target = source / relative
        if target.exists():
            target.rmdir()  # Only replace upstream's empty submodule placeholders.
        shutil.move(str(next((work / name).iterdir())), target)
    for name, expected in lock["pristine_files"].items():
        if digest(source / name) != expected:
            raise ValueError(f"unexpected upstream file: {name}")
    if 'uca' in features:
        from uca_prepared import prepare as prepare_uca
        uca_prepared = prepare_uca(root, source)
    if 'lexer' in features:
        from lexer_prepared import prepare as prepare_lexer
        lexer_prepared = prepare_lexer(root, source)
    portability_series = apply_series(root, source, guest_input)
    source_overlay = []
    observation_overlay = []
    if 'source_overlay' in guest_input:
        source_overlay = apply_series(root, source, {'patches': [guest_input['source_overlay']]})
    else:
        subprocess.run(["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-i", str(root / "guest/source.patch")], cwd=source, check=True)
    if 'startup-concurrency' in features:
        from startup_concurrency import validate
        startup_concurrency = validate(source)
    if 'observation_overlay' in guest_input:
        observation_overlay = apply_series(root, source, {'patches': [guest_input['observation_overlay']]})
    # A disposable experiment patch is separate from the canonical product patch.
    experimental = root / "guest/experimental.patch"
    experimental_files = (list(guest_input.get('native_overlay', {}).get('after_sha256', {}))
                          if selected is not None else patch_files(root))
    time_patch = None
    prepared_patch = None
    canonical_prepared = None
    if (root / "guest/prepared_source_patch.json").exists():
        pin = json.loads((root / "guest/prepared_source_patch.json").read_text())
        if pin.get('patch_file') in [p['file'] for p in guest_input['patches']]:
            from prepared_source_patch import inputs as prepared_inputs, check_profile_source
            canonical_prepared = prepared_inputs(root)
            check_profile_source(source, root)
    native_wire_series = []
    if 'native_wire_patch' in guest_input:
        native_wire_series = apply_series(root, source, {'patches': [guest_input['native_wire_patch']]})
    if experimental.exists():
        if canonical_prepared is not None:
            # Future experiments remain isolated and release provenance rejects them.
            if 'native_overlay' in guest_input:
                apply_series(root, source, {'patches': [guest_input['native_overlay']]})
            else:
                subprocess.run(["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-i", str(experimental)], cwd=source, check=True)
        elif (root / "guest/prepared_source_patch.json").exists():
            from prepared_source_patch import apply as apply_prepared_patch
            prepared_patch = apply_prepared_patch(source, root)
        elif (root / "guest/prepared_time_patch.json").exists():
            from prepared_time_patch import apply as apply_time_patch
            time_patch = apply_time_patch(source, root)
        else:
            subprocess.run(["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-i", str(experimental)], cwd=source, check=True)
    elif (root / "guest/prepared_source_patch.json").exists() and canonical_prepared is None:
        raise ValueError("experimental prepared source patch is missing")
    elif (root / "guest/prepared_time_patch.json").exists():
        raise ValueError("experimental TIME patch is missing")
    native_glue = None
    native_manifest = root / "guest/native/manifest.json"
    canonical_native_glue = 'native_glue_manifest' in guest_input
    if native_manifest.exists():
        if not canonical_native_glue and not experimental.exists():
            raise ValueError("guest/native/manifest.json requires canonical native_glue_manifest or guest/experimental.patch")
        glue_spec = json.loads(native_manifest.read_text())
        pending_glue = []
        for dest, ref in glue_spec.get("files", {}).items():
            src_file = (root / ref["file"]).resolve(strict=True)
            if not src_file.is_relative_to(root.resolve()):
                raise ValueError("native glue source outside root: " + dest)
            if digest(src_file) != ref["sha256"]:
                raise ValueError("native glue identity mismatch: " + dest)
            target = source
            for part in dest.split("/"):
                target = target / part
                if target.is_symlink():
                    raise ValueError("native glue destination symlink: " + dest)
            if target.exists() or not target.parent.is_dir():
                raise ValueError("native glue destination conflict: " + dest)
            pending_glue.append((target, src_file))
        for target, src_file in pending_glue:
            shutil.copyfile(src_file, target)
            target.chmod(0o644)
        native_glue = glue_spec.get("files", {})
        if not canonical_native_glue:
            experimental_files = [*experimental_files, *native_glue.keys()]
    core = re.sub(r"\bg_mysql\b", "multi_mysql", (root / "guest/wire_core.inc").read_text())
    (source / "wasm/wire_api.inc").write_text(
        "#include <pthread.h>\nstatic _Thread_local MYSQL *multi_mysql;\n" + core + '\n#include "prepared_api.inc"\n#include "resident.inc"\n')
    for name in ("resident.inc", "snapshot_fs.inc", "startup_timing.inc", "init_diagnostics.inc", "prepared_auth_keys.inc", "routine_bootstrap.inc", "prepared_api.inc"):
        shutil.copy2(root / "guest" / name, source / "wasm" / name)
    shutil.copy2(root / "guest/init_diagnostics.h", source / "include/mariamem_init_diagnostics.h")
    diagnostic_files = instrument(source)
    auth_files = prepare_auth_source(source)
    auth_header = write_header(source, fixture=root / "guest/test-auth-keypair.json")
    routine_schema = prepare_routine_schema(source, root=root)
    cmake = source / 'wasm/CMakeLists.txt'
    text = cmake.read_text()
    anchor = '  TARGET_LINK_OPTIONS(lite4mariadb-wasix PRIVATE\n'
    if text.count(anchor) != 1:
        raise ValueError('guest linker diagnostic anchor changed')
    wrappers = ('open', 'open64', 'close', 'read', 'write', 'pread', 'pread64', 'pwrite', 'pwrite64',
                'ftruncate', 'ftruncate64', 'malloc', 'calloc', 'realloc', 'free', 'posix_memalign',
                'mmap', 'mmap64', 'munmap', 'pthread_create')
    cmake.write_text(text.replace(anchor, anchor + ''.join(f'    "SHELL:-Wl,--wrap={name}"\n' for name in wrappers)))
    vendor = source / "mariamem-dependencies"
    vendor.mkdir()
    for name, cmake in (("pcre2", "cmake/pcre.cmake"), ("libfmt", "cmake/libfmt.cmake")):
        entry = next(p for p in lock["inputs"] if p["name"] == name)
        shutil.copy2(fetch_input(name), vendor / entry["file"])
        path = source / cmake
        text = path.read_text()
        if text.count(entry["url"]) != 1:
            raise ValueError(f"unexpected dependency URL in {cmake}")
        path.write_text(text.replace(entry["url"], "${CMAKE_SOURCE_DIR}/mariamem-dependencies/" + entry["file"]))
    generated_files = []
    if uca_prepared:
        generated_files += ['strings/ctype-uca.c', 'include/m_ctype.h', uca_prepared['header']]
    if lexer_prepared:
        generated_files += [lexer_prepared['header'], 'mysys/charset.c']
    # UCA private-copy input is installed by the canonical patch for12.3.3.
    # Frozen profiles without this header retain their original preparation.
    if (source / 'strings/mariamem_uca_copy_prepared.h').exists():
        generated_files.append('strings/mariamem_uca_copy_prepared.h')
    history_wait_files = ()
    from check_history_wait_source import BOUNDARY, FILES, source as check_history_wait
    if (root/'guest/source.patch').is_file() and BOUNDARY in (root/'guest/source.patch').read_bytes():
        check_history_wait(root)
        history_wait_files = FILES
    native_wire_files = [name for patch in native_wire_series for name in patch["after_sha256"]]
    native_glue_files = list(native_glue.keys()) if (native_glue and canonical_native_glue) else []
    manifest = {"guest_input": guest_input, "portability_series": portability_series, "routine_schema": routine_schema,
                "inputs_lock_sha256": digest(root / "release/inputs.lock.json"),
                "overlays": {p.name: digest(p) for p in sorted((root / "guest").iterdir()) if p.is_file()},
                "modified_files": {name: digest(source / name) for name in
                                   (*lock["pristine_files"], *(name for patch in portability_series for name in patch["after_sha256"]), *native_wire_files, *native_glue_files, "wasm/wire_api.inc", "wasm/resident.inc",
                                    "wasm/snapshot_fs.inc", "wasm/startup_timing.inc", "wasm/init_diagnostics.inc",
                                    "wasm/prepared_auth_keys.inc", "wasm/routine_bootstrap.inc", "wasm/prepared_api.inc", routine_schema["header"], auth_header, *auth_files,
                                    "include/mariamem_init_diagnostics.h", *generated_files, *diagnostic_files,
                                    "storage/innobase/dict/dict0dict.cc",
                                    "cmake/pcre.cmake", "cmake/libfmt.cmake", *history_wait_files, *experimental_files)}}
    if native_wire_series:
        manifest["native_wire_patch"] = native_wire_series[0]
    if selected is None or 'lexer' in features:
        manifest.update(startup_concurrency=startup_concurrency, lexer_prepared=lexer_prepared,
                        uca_prepared=uca_prepared)
    if source_overlay:
        manifest.update(source_overlay=source_overlay, observation_overlay=observation_overlay,
                        uca_prepared=uca_prepared, prepared_profile=canonical_prepared)
    if experimental.exists():
        manifest["experimental_patch"] = {"file": "guest/experimental.patch", "sha256": digest(experimental)}
    if native_glue:
        manifest["native_glue"] = native_glue
    if time_patch:
        manifest["experimental_time_patch"] = time_patch
    if prepared_patch:
        manifest["experimental_prepared_patch"] = prepared_patch
    if canonical_prepared is not None:
        manifest["prepared_api_source"] = canonical_prepared
    if selected is not None:
        manifest['schema'] = 'selected-source-preparation-v1'
        manifest['release_eligible'] = False
    (build / "prepared-source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copy2(root / "release/inputs.lock.json", build / "preparation-inputs.lock.json")
    print("Prepared build/source from pinned archives; all guest dependencies are local.")
    return manifest


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine')
    parser.add_argument('--profile')
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--archive-cache', type=Path)
    args = parser.parse_args()
    if any((args.engine, args.profile, args.work_dir, args.archive_cache)):
        if not all((args.engine, args.profile, args.work_dir)):
            parser.error('--engine, --profile and --work-dir are required together')
        from guest_preparation_context import prepare_selected
        prepare_selected(ROOT, args.engine, args.profile, args.work_dir, archive_cache=args.archive_cache)
    else:
        prepare(ROOT, LOCK, ROOT / 'build', fetch)


if __name__ == '__main__':
    main()
