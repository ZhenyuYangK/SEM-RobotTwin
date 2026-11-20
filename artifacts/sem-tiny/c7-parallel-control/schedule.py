import csv
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from worker import BASE, CONTROL, OUTPUT, TASKS, write_json, state, verified_inputs

TASK_LIMIT = 3
FIRST = TASKS[0]
OUTBOX = CONTROL / "outbox"
FIELDS = ("task", "demos", "steps", "episodes", "successes", "success_rate_pct",
          "checkpoint", "result", "train_seconds", "eval_seconds")

def process(pid, expected):
    try:
        proc = Path(f"/proc/{pid}")
        raw = (proc / "stat").read_text()
        fields = raw[raw.rfind(")") + 2:].split()
        command = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode()
        if fields[0] != "Z" and expected in command:
            return {"pid": pid, "ppid": int(fields[1]), "cmd": command}
    except FileNotFoundError:
        pass
    return None

def pid_for(task):
    return int((CONTROL / f"{task}.pid").read_text())

def phase_for(task):
    status = CONTROL / f"{task}.state.json"
    if status.is_file():
        return json.loads(status.read_text())["phase"]
    return "queued"

def start(task, operation):
    log = CONTROL / f"{task}.worker.log"
    mode = "ab" if task == FIRST else "xb"
    with log.open(mode) as stream:
        job = subprocess.Popen([sys.executable, "-u", CONTROL / "worker.py", operation, task],
                               cwd=CONTROL, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
    (CONTROL / f"{task}.pid").write_text(str(job.pid) + "\n")
    return job

def adopt(controller_pid, trainer_pid, monitor_pid):
    verified_inputs()
    controller = process(controller_pid, "scripts/run_formal_experiments.py")
    trainer = process(trainer_pid, str(OUTPUT / FIRST / "staged/train_config.py"))
    if controller is None or trainer is None or trainer["ppid"] != controller_pid:
        raise RuntimeError("Expected the original C7 controller and its running first training child")
    if (Path(f"/proc/{trainer_pid}/fd/1").resolve() != OUTPUT / FIRST / "train.log"
            or Path(f"/proc/{monitor_pid}/fd/1").resolve() != OUTPUT / FIRST / "train.gpu.csv"):
        raise RuntimeError("Original trainer or telemetry log does not match the first C7 task")
    if any(not process(pid_for(task), f"worker.py full {task}") for task in TASKS[1:3]):
        raise RuntimeError("The two additional workers must be running before handoff")
    elapsed = int(subprocess.check_output(["ps", "-p", str(trainer_pid), "-o", "etimes="]).strip())
    start_time = time.time() - elapsed
    state(FIRST, "train", adopted_pid=trainer_pid, telemetry_pid=monitor_pid)
    write_json(CONTROL / "adopted.json",
               {"trainer_pid": trainer_pid, "monitor_pid": monitor_pid, "train_started": start_time})
    os.kill(controller_pid, signal.SIGTERM)
    return trainer_pid, monitor_pid, start_time

def save_completion(task):
    complete = OUTPUT / task / "completion.json"
    outcome = json.loads(complete.read_text())
    if outcome["task"] != task or outcome["demos"] != 100 or outcome["steps"] != 100000 or outcome["episodes"] != 100:
        raise ValueError(f"Unexpected formal outcome for {task}")
    episodes, successes = outcome["episodes"], outcome["successes"]
    if not isinstance(successes, int) or not 0 <= successes <= episodes:
        raise ValueError(f"Unexpected success count for {task}")
    existing_path = OUTPUT / "results.csv"
    if existing_path.exists():
        with existing_path.open() as stream:
            rows = {row["task"]: row for row in csv.DictReader(stream)}
    else:
        rows = {}
    rows[task] = outcome
    temporary = existing_path.with_suffix(".tmp")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows[item] for item in TASKS if item in rows)
    temporary.replace(existing_path)
    public = {key: outcome[key] for key in ("task", "demos", "steps", "episodes", "successes",
                                            "success_rate_pct", "train_seconds", "eval_seconds")}
    public.update(task_config="demo_clean", policy="sem_policy", instruction_type="unseen", eval_seed=10000,
                  batch_size=2, completion_time=complete.stat().st_mtime)
    write_json(OUTBOX / f"{task}.json", public)
    print(f"{task}: verified result ready for Git push", flush=True)

def schedule(trainer, monitor, start_time):
    workers = {}
    external = {task: pid_for(task) for task in TASKS[1:3]}
    waiting = list(TASKS[3:])
    finished = set()
    failed = set()
    adopted = True
    while len(finished) + len(failed) < len(TASKS):
        if adopted and not process(trainer, str(OUTPUT / FIRST / "staged/train_config.py")):
            adopted = False
            if process(monitor, "nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu"):
                os.kill(monitor, signal.SIGTERM)
            log = (OUTPUT / FIRST / "train.log").read_text()
            if "GlobalStep[100000/100000]" in log and "FINISH TRAINING" in log:
                write_json(OUTPUT / FIRST / "training_complete.json", {"train_seconds": round(time.time() - start_time, 2)})
                workers[FIRST] = start(FIRST, "eval")
            else:
                state(FIRST, "failed", error="Adopted training exited before formal completion")
                failed.add(FIRST)
        for task, pid in list(external.items()):
            if not process(pid, f"worker.py full {task}"):
                del external[task]
                if (OUTPUT / task / "completion.json").is_file() and phase_for(task) == "complete":
                    save_completion(task)
                    finished.add(task)
                else:
                    failed.add(task)
        for task, job in list(workers.items()):
            code = job.poll()
            if code is not None:
                del workers[task]
                if code == 0 and (OUTPUT / task / "completion.json").is_file() and phase_for(task) == "complete":
                    save_completion(task)
                    finished.add(task)
                else:
                    failed.add(task)
        while waiting and len(external) + len(workers) + int(adopted) < TASK_LIMIT:
            task = waiting.pop(0)
            workers[task] = start(task, "full")
        write_json(CONTROL / "queue.json",
                   {"max_active": TASK_LIMIT, "active": ([FIRST] if adopted else []) + list(external) + list(workers),
                    "waiting": waiting, "complete": sorted(finished), "failed": sorted(failed)})
        if len(finished) + len(failed) < len(TASKS):
            time.sleep(10)
    if failed:
        raise RuntimeError(f"Formal tasks requiring recovery: {', '.join(sorted(failed))}")

def main():
    if sys.argv[1:] == ["--preflight"]:
        verified_inputs()
        print("C7 coordinator preflight passed")
        return
    args = [int(value) for value in sys.argv[1:]]
    with (CONTROL / "schedule.lock").open("a") as supervisor_lock:
        fcntl.flock(supervisor_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        OUTBOX.mkdir(exist_ok=True)
        trainer, monitor, start_time = adopt(*args)
        with (BASE / "runs/formal.lock").open("a") as formal_lock:
            fcntl.flock(formal_lock, fcntl.LOCK_EX)
            print(f"Adopted running training PID {trainer}; at most {TASK_LIMIT} active C7 workflows", flush=True)
            schedule(trainer, monitor, start_time)

if __name__ == "__main__":
    main()
