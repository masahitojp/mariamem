"""Validate the four-mode samples and render a wall-clock comparison."""

from collections import Counter
import argparse
import csv
import json
from pathlib import Path
from statistics import median
from math import isclose
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator


MODES = {
    "mariamem": "mariamem",
    "native": "Native MariaDB",
    "testcontainers": "Testcontainers",
    "docker": "docker run",
}
COLORS = {
    "boot": "#5177a3",
    "fixture": "#24847f",
    "snapshot": "#8567b0",
    "other": "#d0d8df",
    "case_setup": "#748cdb",
    "reset": "#e1a04e",
    "variant": "#9cbd82",
    "write": "#287b65",
    "case_cleanup": "#aba0b5",
}


def duration(phase):
    return phase["to_ms"] - phase["from_ms"]


def suite_offset_ms(sample):
    metrics = sample["metrics"]
    if "origin_mono_ns" in sample:
        return (metrics["start_mono_ns"] - sample["origin_mono_ns"]) / 1_000_000
    return (metrics["start_ns"] - sample["origin_ns"]) / 1_000_000


def validate(sample):
    metrics = sample["metrics"]
    mode = sample["mode"]
    assert metrics["version"].startswith("12.3.4-MariaDB-")
    assert (metrics["reads"], metrics["writes"], metrics["parallel"]) == (0, 8, 8)
    assert metrics["settings"]["log_bin"] == "0"
    assert metrics["settings"]["innodb_flush_log_at_trx_commit"] == ("0" if mode == "testcontainers" else "1")
    phases = metrics["phases"]
    names = [f"late_fee/{i:02d}" for i in range(1, 9)]
    expected = [(phase, case) for phase in ("variant", "write") for case in names]
    case_phases = [p for p in phases if p.get("case")]
    if mode == "mariamem":
        expected += [(phase, case) for phase in ("case_setup", "case_cleanup") for case in names]
    else:
        expected += [("reset", case) for case in names[1:]]
        serial = sorted(case_phases, key=lambda p: p["from_ms"])
        assert all(a["to_ms"] <= b["from_ms"] for a, b in zip(serial, serial[1:]))
    assert Counter((p["name"], p["case"]) for p in case_phases) == Counter(expected)
    start = suite_offset_ms(sample)
    assert 0 <= start <= sample["through_tests_ms"]
    suite_end = start + metrics["total_ms"]
    if suite_end > sample["through_tests_ms"] + 0.5:
        raise ValueError(
            f"{mode} trial {sample['trial']}: suite ended at {suite_end:g} ms, "
            f"child exit recorded at {sample['through_tests_ms']:g} ms"
        )
    readiness, tests, shutdown = (sample[key] for key in ("ready_ms", "through_tests_ms", "with_shutdown_ms"))
    if not 0 < readiness < tests <= shutdown:
        raise ValueError(
            f"{mode} trial {sample['trial']}: invalid timing order "
            f"(SQL ready {readiness:g} ms, tests {tests:g} ms, teardown {shutdown:g} ms)"
        )


def validate_timing_boundaries(sample):
    elapsed = (sample["test_finished_mono_ns"] - sample["origin_mono_ns"]) / 1_000_000
    if not isclose(elapsed, sample["through_tests_ms"], rel_tol=0, abs_tol=0.5):
        raise ValueError("Test completion differs from the elapsed time at child exit")
    if sample["mode"] == "mariamem":
        metrics = sample["metrics"]
        ready, = (phase for phase in metrics["phases"] if phase["name"] == "ready")
        elapsed = suite_offset_ms(sample) + ready["to_ms"]
        if not isclose(elapsed, sample["ready_ms"], rel_tol=0, abs_tol=0.5):
            raise ValueError("mariamem SQL readiness differs from the ready event on the launch clock")


def time_breakdown(sample):
    phases = sample["metrics"]["phases"]
    return {
        "boot": sample["ready_ms"],
        "fixture": sum(duration(p) for p in phases if p["name"] == "fixture"),
        "snapshot": sum(duration(p) for p in phases if p["name"] == "snapshot"),
        "resets": sum(duration(p) for p in phases if p["name"] == "reset"),
        "test_process": sample["process_ms"],
        "total": sample["through_tests_ms"],
        "through_teardown": sample["with_shutdown_ms"],
    }


def render(runs, output):
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "text.color": "#192d3e",
        "axes.labelcolor": "#314558",
        "xtick.color": "#314558",
        "ytick.color": "#314558",
        "axes.edgecolor": "#d7e0e8",
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    figure = plt.figure(figsize=(15, 9.6), facecolor="white")
    grid = figure.add_gridspec(5, 1, height_ratios=(1.65, 1, 1, 1, 1), hspace=0.68)
    figure.subplots_adjust(left=0.16, right=0.96, top=0.845, bottom=0.16)
    figure.text(0.08, 0.95, "Sakila · Late-fee migration", fontsize=24, weight="bold")
    measured = len(runs["mariamem"])
    count = "one measured run" if measured == 1 else f"{measured} measured runs"
    figure.text(0.08, 0.918, f"Eight cases on MariaDB 12.3.4 · Linux arm64 · {count} per mode")

    wall = figure.add_subplot(grid[0])
    wall.set_title("Startup through test completion", loc="left", weight="bold", pad=17)
    wall.text(0, 1.015, "Bars show runs closest to the median · dots show every measured run", transform=wall.transAxes,
              fontsize=9, color="#52697b", va="bottom")
    wall.set_yticks(range(len(MODES)), labels=MODES.values())
    wall.set_ylim(len(MODES) - 0.5, -0.55)
    wall.tick_params(axis="y", length=0, pad=10)

    max_wall = max(s["through_tests_ms"] for samples in runs.values() for s in samples)
    wall.set_xlim(0, max_wall * 1.12)
    wall.xaxis.set_major_locator(MaxNLocator(9))
    axes = [wall]
    for index, (mode, name) in enumerate(MODES.items()):
        samples = sorted(runs[mode], key=lambda s: s["through_tests_ms"])
        median_total = median(s["through_tests_ms"] for s in samples)
        sample = min(samples, key=lambda s: abs(s["through_tests_ms"] - median_total))
        metrics = sample["metrics"]
        suite_offset = suite_offset_ms(sample)
        stats = time_breakdown(sample)
        wall.barh(index, stats["total"], height=0.39, color=COLORS["other"])
        wall.barh(index, stats["boot"], height=0.39, color=COLORS["boot"])
        for phase in metrics["phases"]:
            if phase["name"] in ("fixture", "snapshot"):
                wall.barh(index, duration(phase), height=0.39,
                          left=suite_offset + phase["from_ms"], color=COLORS[phase["name"]])
        times = [s["through_tests_ms"] for s in samples]
        wall.hlines(index + 0.29, min(times), max(times), color="#607689", lw=1.2)
        wall.scatter(times, [index + 0.29] * len(times), color="#607689", s=10, zorder=3)
        wall.text(stats["total"] + max_wall * 0.013, index - 0.02, f'{stats["total"]:,.0f} ms',
                  va="center", weight="bold")

        ax = figure.add_subplot(grid[index + 1], sharex=wall)
        axes.append(ax)
        layout = "parallel Forks" if mode == "mariamem" else "shared DB, serial"
        ax.set_title(f"{name}  ·  {layout}", loc="left", fontsize=10, weight="bold", pad=5)
        for phase in metrics["phases"]:
            if not phase.get("case"):
                continue
            case = int(phase["case"].split("/")[1])
            ax.broken_barh(
                [(suite_offset + phase["from_ms"], duration(phase))],
                (case - 0.36, 0.72), facecolors=COLORS[phase["name"]],
            )
        ax.axvline(stats["total"], color="#607689", linestyle=":", linewidth=0.9)
        ax.tick_params(axis="y", length=0, pad=6, labelsize=9)
        ax.set_yticks([1, 4, 8], labels=["01", "04", "08"])
        ax.set_ylabel("Case", rotation=0, labelpad=20, va="center", fontsize=9)
        ax.set_ylim(8.65, 0.35)

    for ax in axes:
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#e8eef3")
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="x", labelbottom=ax is axes[-1], length=3)
    axes[-1].set_xlabel("Elapsed time from launch (ms)")
    legend = [
        ("boot", "Boot to SQL"), ("fixture", "Fixture"), ("snapshot", "Snapshot"),
        ("other", "Remaining test time"), ("case_setup", "Fork"), ("reset", "Reset"),
        ("variant", "Variant setup"), ("write", "Migration + verification"), ("case_cleanup", "Fork cleanup"),
    ]
    figure.legend(
        handles=[Patch(facecolor=COLORS[key], label=label) for key, label in legend],
        loc="lower center", bbox_to_anchor=(0.56, 0.048), ncol=5, frameon=False, fontsize=9,
    )
    figure.text(0.08, 0.018, "Testcontainers uses tmpfs and relaxed commit flushing. Native MariaDB and docker run use disk and normal flushing.",
                fontsize=9, color="#52697b")
    figure.savefig(output, dpi=180, facecolor="white")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("samples", type=Path)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    samples = [json.loads(line) for line in args.samples.read_text().splitlines()]
    trials = max(s["trial"] for s in samples) + 1
    assert trials >= 2
    assert Counter((s["mode"], s["trial"]) for s in samples) == Counter(
        (mode, trial) for mode in MODES for trial in range(trials)
    )
    # Reference samples predate the image ID and child-exit timestamp.
    image_ids = {sample.get("image_id") for sample in samples}
    has_identity = image_ids != {None} or any("test_finished_mono_ns" in sample for sample in samples)
    if has_identity and (
        len(image_ids) != 1
        or not all(re.fullmatch(r"sha256:[0-9a-f]{64}", image or "") for image in image_ids)
    ):
        raise ValueError("Samples must share one full MariaDB image ID")
    runs = {mode: [] for mode in MODES}
    for sample in samples:
        validate(sample)
        if has_identity:
            validate_timing_boundaries(sample)
        if sample["trial"]:
            runs[sample["mode"]].append(sample)
    with (args.directory / "median.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["metric", *MODES])
        for key in time_breakdown(samples[0]):
            writer.writerow([key, *(f"{median(time_breakdown(s)[key] for s in runs[mode]):.3f}" for mode in MODES)])
    render(runs, args.directory / "benchmark.png")


if __name__ == "__main__":
    main()
