"""Schedule C7 tasks and take over training processes that are already running."""

import argparse
import csv
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from worker import (BASE, CONTROL, DEMOS, EPISODES, OUTPUT, TASKS, completed_training_steps,
                    state, training_steps_target, verified_inputs, write_json)

TASK_LIMIT = 3
FIRST = TASKS[0]
OUTBOX = CONTROL / "outbox"
WORKER_SCRIPT = Path(__file__).resolve().with_name("worker.py")
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
    mode = "ab" if operation == "eval" else "xb"
    with log.open(mode) as stream:
        job = subprocess.Popen([sys.executable, "-u", WORKER_SCRIPT, operation, task],
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
    allowed_episodes = {EPISODES, 100} if task == FIRST else {EPISODES}
    if (outcome["task"] != task or outcome["demos"] != DEMOS
            or outcome["steps"] != completed_training_steps(OUTPUT / task)
            or outcome["episodes"] not in allowed_episodes):
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

def schedule(adopted, external, waiting, stopped=()):
    workers = {}
    finished = set()
    failed = set()
    while True:
        for task, (trainer, monitor, start_time) in list(adopted.items()):
            run = OUTPUT / task
            if process(trainer, str(run / "staged/train_config.py")):
                continue
            del adopted[task]
            if process(monitor, "nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu"):
                os.kill(monitor, signal.SIGTERM)
            try:
                completed_training_steps(run)
            except ValueError as error:
                state(task, "failed", error=str(error))
                failed.add(task)
            else:
                write_json(run / "training_complete.json", {"train_seconds": round(time.time() - start_time, 2)})
                workers[task] = start(task, "eval")
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
        while waiting and len(adopted) + len(external) + len(workers) < TASK_LIMIT:
            task = waiting.pop(0)
            workers[task] = start(task, "full")
        active = list(adopted) + list(external) + list(workers)
        write_json(CONTROL / "queue.json",
                   {"max_active": TASK_LIMIT, "active": active, "waiting": waiting,
                    "complete": sorted(finished), "failed": sorted(failed), "stopped": list(stopped),
                    "eval_episodes_target": EPISODES, "train_steps_target": training_steps_target()})
        if not active:
            break
        time.sleep(10)
    if failed:
        raise RuntimeError(f"Formal tasks requiring recovery: {', '.join(sorted(failed))}")

def resume(snapshot, *, check_only=False):
    verified_inputs()
    data = json.loads(snapshot.read_text())
    adopted, waiting, stopped = (data[key] for key in ("adopted", "waiting", "stopped"))
    external = data.get("external", {})
    if (sorted([*adopted, *external, *waiting, *stopped]) != sorted(TASKS)
            or len(adopted) + len(external) > TASK_LIMIT):
        raise ValueError("Resume snapshot must cover each C7 task once and fit the worker limit")
    if any(phase_for(task) != "stopped" for task in stopped):
        raise ValueError("Resume snapshot includes a task without a recorded stop")
    if any((OUTPUT / task).exists() for task in waiting):
        raise ValueError("Resume snapshot includes an already started task in its waiting list")
    for task, (trainer, monitor, _) in adopted.items():
        run = OUTPUT / task
        if not process(trainer, str(run / "staged/train_config.py")):
            raise ValueError(f"Expected a running trainer for {task}")
        if (Path(f"/proc/{trainer}/fd/1").resolve() != run / "train.log"
                or Path(f"/proc/{monitor}/fd/1").resolve() != run / "train.gpu.csv"):
            raise ValueError(f"Trainer or telemetry log does not match {task}")
    for task, pid in external.items():
        if (not process(pid, f"worker.py full {task}")
                or Path(f"/proc/{pid}/fd/1").resolve() != CONTROL / f"{task}.worker.log"):
            raise ValueError(f"Worker or worker log does not match {task}")
    if check_only:
        print("C7 resume snapshot passed verification", flush=True)
        return
    print(f"Resuming C7 with {training_steps_target()} steps for new runs and {EPISODES} evaluation episodes",
          flush=True)
    schedule(adopted, external, waiting, stopped)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true", help="Only verify the cloud inputs (default)")
    mode.add_argument("--adopt", type=int, nargs=3, metavar=("CONTROLLER_PID", "TRAINER_PID", "MONITOR_PID"),
                      help="Perform the one-time handoff from the original serial run")
    mode.add_argument("--resume", type=Path, metavar="SNAPSHOT",
                      help="Resume dispatch from a snapshot of active workflows, queued tasks and stopped tasks")
    mode.add_argument("--check-resume", type=Path, metavar="SNAPSHOT",
                      help="Verify a resume snapshot without starting a scheduler")
    args = parser.parse_args()
    if args.check_resume is not None:
        resume(args.check_resume, check_only=True)
        return
    if args.adopt is None and args.resume is None:
        verified_inputs()
        print("C7 coordinator preflight passed")
        return
    if args.adopt and any(pid <= 0 for pid in args.adopt):
        parser.error("Process IDs must be positive")
    with (CONTROL / "schedule.lock").open("a") as supervisor_lock:
        fcntl.flock(supervisor_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        OUTBOX.mkdir(exist_ok=True)
        if args.adopt:
            training = adopt(*args.adopt)
        with (BASE / "runs/formal.lock").open("a") as formal_lock:
            fcntl.flock(formal_lock, fcntl.LOCK_EX)
            if args.resume:
                resume(args.resume)
            else:
                print(f"Adopted running training PID {training[0]}; at most {TASK_LIMIT} active C7 workflows", flush=True)
                external = {task: pid_for(task) for task in TASKS[1:3]}
                schedule({FIRST: training}, external, list(TASKS[3:]))

if __name__ == "__main__":
    main()
