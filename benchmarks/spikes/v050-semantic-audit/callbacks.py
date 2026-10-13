"""Save the reviewed indirect call sites and fixed table/data corroboration.

This is a manually classified slice of the writer functions, not a points-to
analysis of all guest functions. Lifecycle callback registrations outside those
functions are recorded in the report and source anchors.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / "docs/reviews/v050-access-paths-evidence"
CLASSES = {
    "pool-thread-init": [891084],
    "pool-thread-end": [891112],
    "pool-task-execute": [891145],
    "exception-what": [825591],
    "pool-submit-task": [788550, 868516, 1022688, 1023522, 957475, 700280, 702902, 1019776],
    "empty-function-manager": [804044, 804123, 804770],
    "encryption-key-version": [893122, 854816, 855980, 811508, 811885, 812066, 828463, 996695, 673148],
    "corruption-log": [908167, 908202],
    "aio-destructor": [882944],
    "timer-destructor": [883435],
    "pool-destructor": [886593, 888112],
    "sql-field-store": [996923, 997048, 997063, 997144, 997197, 997219, 997241, 997263, 997301, 997372, 997415],
    "thdvar-table-locks-resolve": [957956],
    "charset-compare": [673506],
    "pool-set-concurrency": [696802, 696833],
    "pool-create-timer": [700336, 700436],
}
ARGUMENTS = {
    "pool-thread-init": "pool callbacks installed by srv_thread_pool_init -> thread_pool_thread_init (my_thread_init/PFS/name); no metadata pointer argument",
    "pool-thread-end": "thread_pool_thread_end (PFS/my_thread_end), followed by worker_end under pool mutex; lifetime P02",
    "pool-task-execute": "task::execute/waitable_task::execute -> registered m_func(m_arg), followed by release; P02/P04/P07/P11 cover relevant task registrations and drain",
    "exception-what": "std::system_error::what in add_thread catch; exception-owned string is printed before pending flag clear; no narrow target address passed",
    "pool-submit-task": "thread_pool_generic selected by non-Windows factory; submit_task uses pool mutex and task refcount; argument is task object, relevant callbacks mapped in P02/P04/P07/P11",
    "empty-function-manager": "std::function cleanup of local system-table scan lambdas; fixed manager words at 13347140/13347200/13347260 are zero, branch skipped for these objects; not a live fil_system metadata callback",
    "encryption-key-version": "encryption_handler getter receives numeric key id; returns version; caller may set global rotate flag. Plugin registration sql/encryption.cc. No flag pointer exported",
    "corruption-log": "constant table choices 1513/1514 -> sql_print_warning/sql_print_error; string/page number, after releasing recv mutex; no page_recv_t pointer passed",
    "aio-destructor": "thread_pool.m_aio reset in os_aio_free after read/write slot destructors wait for in-use completion; P11",
    "timer-destructor": "rollback/master timer object deletion; timer_generic::disarm cancels pending tasks then waits task references before destructor returns; P02/P11",
    "pool-destructor": "srv_thread_pool_end deletes fixed generic pool; stops AIO/timer, wakes workers, waits count/CV before free; P02",
    "sql-field-store": "INFORMATION_SCHEMA encryption row Field::store virtual calls; receiver is table Field object, numeric/text copied from crypt state; not pointer to rotate flag",
    "thdvar-table-locks-resolve": "MYSQL_THDVAR_BOOL(table_locks).resolve(thd, offset) returns per-THD option storage; does not receive ReadView pointer; owner THD in external_lock",
    "charset-compare": "fixed charset handler strnncoll for option parsing; initial table resolves to my_strnncoll_utf8mb3_general1400_as_ci; string pointers, no narrow metadata target",
    "pool-set-concurrency": "generic pool setter takes m_mtx, used around recovery batch; not a raw callback into recovery node storage",
    "pool-create-timer": "generic timer created with explicit maintenance callback/data; disarm and task reference wait precede destruction; P02/P11",
}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    inv = json.loads((OLD / "writer-inventory.json").read_text())
    graph = json.loads((OLD / "direct-call-graph.json").read_text())
    provenance = json.loads((ROOT / "internal/generatedgo/provenance.json").read_text())
    labels = {n: k for k, ns in CLASSES.items() for n in ns}
    assert len(labels) == sum(map(len, CLASSES.values()))
    rows = []
    for fn in inv:
        if not fn["indirect_calls"]:
            continue
        path = ROOT / fn["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == provenance["files_sha256"][fn["file"].removeprefix("internal/generatedgo/")]
        lines = path.read_text().splitlines()
        start = fn["line"] - 1
        end = next((n for n in range(start+1, len(lines)) if lines[n].startswith("func Fn")), len(lines))
        for n in range(start, end):
            if re.search(r"m\.T\d+\[.*\]\.\(func\(|CallIndirect", lines[n]):
                key = labels[n+1]
                rows.append({"fn": fn["fn"], "file": fn["file"], "line": n+1,
                             "statement": lines[n].strip(), "class": key,
                             "argument": ARGUMENTS[key], "context": lines[max(start,n-5):n+2]})
    assert {r["line"] for r in rows} == set(labels)
    assert len(rows) == sum(f["indirect_calls"] for f in inv)
    source = ROOT / "internal/generatedgo/code/generated.go"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == provenance["files_sha256"]["code/generated.go"]
    literal = re.search(r'var wasm2goData_data_bin = \[\]byte\("((?:\\x[0-9a-f]{2})+)"\)', source.read_text())[1]
    data = bytes.fromhex(literal.replace("\\x", ""))
    assert len(data) == 6850451
    # Fn67's two fixed passive-data destinations; do not execute guest startup.
    memory = bytearray(32*1024*1024)
    memory[8388608:14595942] = data[:6207334]
    memory[14595968:15238588] = data[6207334:6849954]
    table = {}
    for file in sorted((ROOT / "internal/generatedgo/code").glob("p*/p*.go")):
        if not file.name.endswith("_pure.go"):
            table.update({int(k): int(v) for k,v in re.findall(r"m.T0\[(\d+)\] = Fn(\d+)", file.read_text())})
    words = {str(a): struct.unpack_from("<I", memory, a)[0] for a in (13347140,13347200,13347260,14952812,10146980)}
    assert all(words[str(a)] == 0 for a in (13347140,13347200,13347260))
    selected = {str(k): {"fn": table[k], "symbol": graph[str(table[k])]["symbol"]} for k in (316,1513,1514,12493,12508,12746)}
    for name, content in (("indirect-calls.json", rows), ("callback-data.json", {"initial_words": words, "table": selected, "data_sha256": hashlib.sha256(data).hexdigest(), "limit": "Initial data plus explicit source registration; not a dynamic callback trace or proof about arbitrary plugin replacement."})):
        (out/name).write_text(json.dumps(content, indent=2)+"\n")
    print(f"PASS: {len(rows)} indirect sites in {sum(bool(f['indirect_calls']) for f in inv)} writer functions classified")


if __name__ == "__main__":
    main()
