#!/usr/bin/env python3
"""Read-only verification of archived O4 inputs and CPU observations."""
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo("Asia/Shanghai")


def rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def clock_in_window(clock, start, end):
    hour, minute, second = map(int, clock.split(":"))
    sample = end.replace(hour=hour, minute=minute, second=second)
    if sample > end:
        sample -= timedelta(days=1)
    return start <= sample < end


def cpu_samples(path, kind, pid, start, end):
    result = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts or not re.fullmatch(r"\d{2}:\d{2}:\d{2}", parts[0]):
            continue
        if not clock_in_window(parts[0], start, end):
            continue
        if kind == "pid" and len(parts) >= 10 and parts[2] == str(pid):
            result.append(float(parts[7]))  # %CPU, without pidstat -I normalization
        elif kind == "node" and len(parts) == 12 and parts[1] == "1":
            result.append(100 - float(parts[11]) - float(parts[5]))
    if len(result) != 25:
        raise ValueError(f"{path}: expected 25 displayed-second samples, got {len(result)}")
    return sum(result) / len(result)


def main():
    folders = sorted((ROOT / "runs").glob("o4-cpu-*-20ms"))
    if len(folders) != 3:
        raise ValueError("expected baseline, formal and extra directories")
    reference = None
    output = csv.writer(sys.stdout)
    output.writerow(["run", "step", "target_rps", "window_start", "window_end_exclusive",
                     "samples", "pid_cpu_pct", "cpu1_busy_pct", "ok_rps", "timeout"])
    for folder in folders:
        meta = json.loads((folder / "run.json").read_text())
        identity = (meta["commit"], meta["request_sha256"], meta["binaries_sha256"])
        if reference is None:
            reference = identity
        if identity != reference:
            raise ValueError(f"{folder}: input/build identity changed")
        if (meta["kind"] != "formal" or meta["dirty"] or meta["service_cpus"] != [1]
                or meta["generator_cpus"] != [0] or meta["variables"]["slo"] != "0.02"):
            raise ValueError(f"{folder}: experiment conditions changed")
        if hashlib.sha256((folder / "request.json").read_bytes()).hexdigest() != meta["request_sha256"]:
            raise ValueError(f"{folder}: request checksum mismatch")
        for key, expected in meta["queries_sha256"].items():
            if hashlib.sha256((folder / f"queries-{key}.txt").read_bytes()).hexdigest() != expected:
                raise ValueError(f"{folder}: query checksum mismatch")
        for row in rows(folder / "steps.csv"):
            if row["step"] == "all":
                continue
            if int(row["sent"]) != sum(int(row[k]) for k in ["ok", "http_err", "timeout", "net_err"]):
                raise ValueError(f"{folder}: request counts do not balance")
            if int(row["dropped"]):
                raise ValueError(f"{folder}: client inflight cap was reached")
            start = datetime.fromtimestamp(int(row["start_unix"]) + 5, ZONE)
            end = datetime.fromtimestamp(int(row["end_unix"]), ZONE)
            pid = cpu_samples(folder / "pidstat.log", "pid", meta["version"]["pid"], start, end)
            node = cpu_samples(folder / "mpstat.log", "node", None, start, end)
            output.writerow([folder.name, row["step"], row["target_rps"],
                             start.isoformat(), end.isoformat(), 25,
                             f"{pid:.2f}", f"{node:.2f}", row["ok_rps"], row["timeout"]])


if __name__ == "__main__":
    main()
