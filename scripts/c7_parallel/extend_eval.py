"""Extend completed C7 evaluations to the configured target using the same checkpoint."""

import argparse
import csv
import fcntl
import json
import os
import re
import sys
from pathlib import Path
from tempfile import mkdtemp

from worker import CONTROL, DEMOS, OUTPUT, REPO, TASKS, evaluation_target, run_logged, verified_inputs, write_json
from summarize_eval import eval_log_episodes


def checked_run(task, run_dir, log, count):
    text = log.read_text()
    episodes, _ = eval_log_episodes(text, task, count)
    saved, = re.findall(r"^Data has been saved to (.+)$", text, re.M)
    result = (run_dir / saved.strip()).resolve(strict=True)
    if (not result.is_relative_to(run_dir / "eval_result") or result.name != "_result.txt"
            or abs(float(result.read_text().splitlines()[-1]) - sum(row["success"] for row in episodes) / count) > 1e-8
            or any(not (result.parent / f"episode{i}.mp4").stat().st_size for i in range(count))):
        raise ValueError(f"Evaluation result or videos do not match the log for {task}")
    for row in episodes:
        row["video"] = str((result.parent / f'episode{row["episode"] - 1}.mp4').relative_to(run_dir))
    return episodes, result


def combined_episodes(original, additional):
    boundary = original[-1]["scene_seed"]
    if additional[0]["scene_seed"] <= boundary:
        raise ValueError("Continuation overlaps the original scene seeds")
    return [*original, *(dict(row, episode=i) for i, row in enumerate(additional, len(original) + 1))]


def extend(task, target, *, check_only=False):
    import yaml

    run_dir = OUTPUT / task
    original = json.loads((run_dir / "completion.json").read_text())
    old_count = original["episodes"]
    if original["task"] != task or original["demos"] != DEMOS:
        raise ValueError(f"Unexpected original evaluation metadata for {task}")
    if old_count == target:
        print(f"{task}: already has {target} episodes", flush=True)
        return
    if not 0 < old_count < target:
        raise ValueError(f"Expected a completed evaluation with fewer than {target} episodes for {task}")
    runtime = CONTROL / "runtimes" / task
    staged = run_dir / "staged"
    config = staged / "sem_policy/deploy_policy.yml"
    deployed = runtime / "policy/sem_policy/deploy_policy.yml"
    checkpoint = Path(original["checkpoint"]).resolve(strict=True)
    if (Path(yaml.safe_load(config.read_text())["ckpt_path"]).resolve(strict=True) != checkpoint
            or config.read_bytes() != deployed.read_bytes()
            or (staged / "demo_clean.yml").read_bytes() != (runtime / "task_config/demo_clean.yml").read_bytes()
            or (runtime / "eval_result").resolve(strict=True) != run_dir / "eval_result"):
        raise ValueError(f"Runtime configuration or checkpoint differs from the original evaluation for {task}")
    first, first_result = checked_run(task, run_dir, run_dir / "eval.log", old_count)
    if str(first_result) != original["result"] or sum(row["success"] for row in first) != original["successes"]:
        raise ValueError(f"Original evaluation metadata does not match its log for {task}")

    count = target - old_count
    scene_seed = first[-1]["scene_seed"] + 1
    if check_only:
        print(f"{task}: verified {old_count} original episodes. Can add {count} from candidate seed {scene_seed}")
        return

    output = run_dir / f"eval_to_{target}"
    output.mkdir(exist_ok=True)
    completion = output / "completion.json"
    if completion.is_file():
        counts = json.loads(completion.read_text())
        print(f'{task}: already extended to {counts["successes"]}/{counts["episodes"]}', flush=True)
        return

    finished = sorted(output.glob("run-*/timing.json"))
    if finished:
        timing, = finished
        log = timing.with_name("eval.log")
        elapsed = json.loads(timing.read_text())["eval_seconds"]
        second, second_result = checked_run(task, run_dir, log, count)
    else:
        attempt = Path(mkdtemp(prefix="run-", dir=output))
        log = attempt / "eval.log"
        runner = REPO / "scripts/run_smoke_eval.py"
        os.environ["XDG_CACHE_HOME"] = str(runtime / "cache")
        os.environ["CUDA_VISIBLE_DEVICES"] = "0"
        os.environ["HYDRA_FULL_ERROR"] = "1"
        os.environ["PYTHONWARNINGS"] = "ignore::UserWarning"
        print(f"{task}: running {count} additional episodes starting at candidate seed {scene_seed}", flush=True)
        elapsed = run_logged(
            [sys.executable, "-u", runner, "--workspace", REPO, "--runtime", runtime, "--task", task,
             "--episodes", str(count), "--start-scene-seed", str(scene_seed), "--instruction-limit", str(old_count),
             "--expert-data-num", str(DEMOS), "--config", config], runtime, log, monitor_gpu=True)
        second, second_result = checked_run(task, run_dir, log, count)
        write_json(attempt / "timing.json", {"eval_seconds": elapsed})
    rows = combined_episodes(first, second)
    successes = sum(row["success"] for row in rows)
    table = output / "eval_episodes.csv"
    temporary = table.with_suffix(".tmp")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("episode", "scene_seed", "success", "video"))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(table)
    write_json(completion, dict(
        original, episodes=len(rows), successes=successes, success_rate_pct=100 * successes / len(rows),
        eval_seconds=round(original["eval_seconds"] + elapsed, 2), result=str(table),
        original_result=str(first_result), additional_result=str(second_result), additional_log=str(log),
        additional_episodes=count, additional_eval_seconds=elapsed, first_candidate_scene_seed=scene_seed,
        instruction_candidate_limit=old_count))
    print(f"{task}: {successes}/{len(rows)} successful, {count} additional episodes in {elapsed:.2f}s", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", nargs="+", choices=TASKS)
    parser.add_argument("--check", action="store_true", help="Verify original runs without launching evaluation")
    args = parser.parse_args()
    verified_inputs()
    target = evaluation_target()
    if args.check:
        for task in args.tasks:
            extend(task, target, check_only=True)
        return
    with (CONTROL / "extend-eval.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for task in args.tasks:
            extend(task, target)


if __name__ == "__main__":
    main()
