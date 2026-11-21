#!/usr/bin/env python3
"""Publish completed C7 evaluations and final checkpoints from cloud storage to GitHub."""

import argparse
import csv
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = Path("artifacts/sem-tiny")
FORMAL = Path("c7-formal")
SUMMARY_FIELDS = (
    "task", "training_steps", "episodes", "successes", "success_rate_pct",
    "method", "segment_episode_counts", "episode_results", "videos",
)
SSH_OPTIONS = (
    "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
    "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3",
)
GIT_ENV = {
    **os.environ, "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0",
    "GIT_SSH_COMMAND": shlex.join(("ssh", *SSH_OPTIONS)),
}


def file_info(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def file_inside(root, path):
    path = path.resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file() or not path.stat().st_size:
        raise ValueError(f"Invalid artifact for {root.name}: {path.name}")
    return path


def source_plan(root, task, target, demos, weights_only):
    from run_formal_experiments import completed_training_steps

    run = (root / task).resolve()
    if run.parent != root:
        raise ValueError(f"Unexpected run path for {task}")
    markers = (run / f"eval_to_{target}/completion.json", run / "completion.json")
    for marker in markers:
        if marker.is_file():
            outcome = json.loads(marker.read_text())
            if outcome["episodes"] == target:
                break
    else:
        marker = outcome = None
    if not (outcome or (weights_only and (run / "training_complete.json").is_file())):
        return None

    steps = completed_training_steps(run)
    if outcome:
        weight = file_inside(run, Path(outcome["checkpoint"]))
        if (outcome["task"], outcome["steps"], outcome["demos"]) != (task, steps, demos):
            raise ValueError(f"Completion record disagrees with the training evidence for {task}")
    else:
        candidates = (run / "train/checkpoints").glob("checkpoint_*/model.safetensors")
        weight = max(candidates, key=lambda path: int(path.parent.name.split("_")[-1]), default=None)
        if weight is None:
            raise ValueError(f"Final checkpoint is missing for {task}")
        weight = file_inside(run, weight)
    if not re.fullmatch(r"train/checkpoints/checkpoint_\d+/model\.safetensors", str(weight.relative_to(run))):
        raise ValueError(f"Unexpected checkpoint location for {task}")
    model_files = [
        weight, weight.with_name("model.config.json"), run / "train/robotwin2_0_processor.json",
        *(run / "staged" / name for name in ("demo_clean.yml", "train_config.py", "train_kwargs.json")),
        *(run / "staged/sem_policy" / name for name in ("deploy_policy.yml", "eval.sh", "eval_config.py")
          if (run / "staged/sem_policy" / name).is_file()),
    ]
    model_info = {
        str(file_inside(run, file).relative_to(run)): file_info(file) for file in model_files
    }
    weight_path = str(weight.relative_to(run))
    if outcome and outcome.get("checkpoint_sha256", model_info[weight_path]["sha256"]) != model_info[weight_path]["sha256"]:
        raise ValueError(f"Evaluation checkpoint SHA-256 mismatch for {task}")
    result = None
    if outcome and not weights_only:
        result = evaluation_plan(run, marker, outcome, target)
    return dict(task=task, weight=weight_path, models=model_info, evaluation=result,
                steps=steps, train_seconds=json.loads((run / "training_complete.json").read_text())["train_seconds"])


def evaluation_plan(run, marker, outcome, target):
    continued = marker.parent != run
    table = file_inside(run, marker.with_name("eval_episodes.csv"))
    result = file_inside(run, Path(outcome["result"]))
    expected_result = result == table if continued else (
        result.name == "_result.txt" and result.is_relative_to(run / "eval_result")
    )
    if not expected_result:
        raise ValueError(f"Unexpected evaluation result path for {run.name}")
    with table.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    seeds = [int(row["scene_seed"]) for row in rows]
    successes = [int(row["success"]) for row in rows]
    if ([int(row["episode"]) for row in rows] != list(range(1, target + 1))
            or len(set(seeds)) != target or not set(successes) <= {0, 1}
            or sum(successes) != outcome["successes"]
            or abs(100 * sum(successes) / target - outcome["success_rate_pct"]) > 1e-8):
        raise ValueError(f"Evaluation table disagrees with the completion record for {run.name}")
    if not continued and abs(float(result.read_text().splitlines()[-1]) - sum(successes) / target) > 1e-8:
        raise ValueError(f"Evaluator result disagrees with the completion record for {run.name}")

    videos = {}
    for row in rows:
        index = int(row["episode"])
        source = run / row["video"] if continued else result.parent / f"episode{index - 1}.mp4"
        row["video"] = ""
        if continued and not source.is_file():
            continue
        source = file_inside(run, source)
        if source.suffix != ".mp4" or not source.is_relative_to(run / "eval_result"):
            raise ValueError(f"Invalid evaluation video for {run.name}, episode {index}")
        row["video"] = f"videos/episode_{index:03d}.mp4"
        videos[row["video"]] = str(source.relative_to(run))
    segments = [target]
    if continued:
        additional = outcome["additional_episodes"]
        if type(additional) is not int or not 0 < additional < target:
            raise ValueError(f"Invalid continuation counts for {run.name}")
        segments = [target - additional, additional]
    summary = dict(task=run.name, training_steps=outcome["steps"], evaluated_episodes=target,
                   successes=sum(successes), success_rate_pct=outcome["success_rate_pct"],
                   method="continuation" if continued else "single_run", segment_episode_counts=segments,
                   video_count=len(videos), eval_seconds=outcome.get("eval_seconds"),
                   complete_recorded_at_utc=datetime.fromtimestamp(marker.stat().st_mtime, timezone.utc).isoformat())
    return dict(summary=summary, rows=rows, videos=videos,
                raw_result=None if continued else str(result.relative_to(run)))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def git(repo, *args, timeout=60, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], env=GIT_ENV, text=True,
                          capture_output=True, check=check, timeout=timeout).stdout.strip()


def lfs_object(repo, oid):
    media, = (line.partition("=")[2] for line in git(repo, "lfs", "env").splitlines()
              if line.startswith("LocalMediaDir="))
    return Path(media) / oid[:2] / oid[2:4] / oid


def ssh(args, command, **kwargs):
    return subprocess.run(["ssh", *SSH_OPTIONS, args.cloud, shlex.join(command)], check=True, **kwargs)


def get_plan(args, task):
    command = ["python3", "-B", "-", "--source", str(args.cloud_root), str(args.cloud_repo), task,
               str(args.target), str(args.demos), str(int(args.weights_only))]
    result = ssh(args, command, input=Path(__file__).read_text(), text=True, capture_output=True, timeout=45)
    return json.loads(result.stdout)


def retrieve(args, task, sources, staging):
    if not sources:
        return
    with tempfile.TemporaryFile() as archive:
        command = ["tar", "-C", str(args.cloud_root / task), "-cf", "-", "--", *sorted(sources)]
        ssh(args, command, stdout=archive, stderr=subprocess.PIPE, timeout=900)
        archive.seek(0)
        with tarfile.open(fileobj=archive) as bundle:
            remaining = set(sources)
            for member in bundle:
                if not member.isfile() or member.name not in remaining:
                    raise ValueError(f"Unexpected member in the artifact transfer for {task}")
                path = staging / member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as stream, path.open("wb") as output:
                    shutil.copyfileobj(stream, output)
                remaining.remove(member.name)
            if remaining:
                raise ValueError(f"Artifact transfer for {task} is incomplete")


def evaluation_matches(previous, evaluation, oid, table):
    if not previous or not table.is_file():
        return False
    fields = ("training_steps", "evaluated_episodes", "successes", "method", "segment_episode_counts")
    if (any(previous.get(field) != evaluation["summary"][field] for field in fields)
            or previous.get("checkpoint_sha256", oid) != oid):
        return False
    with table.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    columns = ("episode", "scene_seed", "success")
    return ([tuple(row[key] for key in columns) for row in rows]
            == [tuple(row[key] for key in columns) for row in evaluation["rows"]])


def stage_evaluation(root, task_path, evaluation, staging, oid):
    summary = dict(evaluation["summary"], checkpoint_sha256=oid)
    task = summary["task"]
    destination = task_path / f'eval_{summary["evaluated_episodes"]}'
    output = root / destination
    output.mkdir(parents=True, exist_ok=True)
    summary_file, episodes_file = output / "summary.json", output / "eval_episodes.csv"
    write_json(summary_file, summary)
    with episodes_file.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("episode", "scene_seed", "success", "video"))
        writer.writeheader()
        writer.writerows(evaluation["rows"])
    files = [summary_file, episodes_file]
    for name, source in evaluation["videos"].items():
        path = output / name
        path.parent.mkdir(exist_ok=True)
        shutil.copyfile(staging / source, path)
        files.append(path)
    if evaluation["raw_result"]:
        raw_result = output / "_result.txt"
        shutil.copyfile(staging / evaluation["raw_result"], raw_result)
        files.append(raw_result)

    results = root / FORMAL / f'evaluation_{summary["evaluated_episodes"]}.csv'
    rows = {}
    if results.is_file():
        with results.open(newline="") as stream:
            rows = {row["task"]: row for row in csv.DictReader(stream)}
    video_path = str(destination / "videos") if evaluation["videos"] else ""
    rows[task] = dict(task=task, training_steps=summary["training_steps"], episodes=summary["evaluated_episodes"],
                      successes=summary["successes"], success_rate_pct=summary["success_rate_pct"],
                      method=summary["method"], segment_episode_counts="+".join(map(str, summary["segment_episode_counts"])),
                      episode_results=str(destination / "eval_episodes.csv"), videos=video_path)
    with results.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows[name] for name in sorted(rows))
    details = dict(summary, summary=str(destination / "summary.json"), results=str(destination / "eval_episodes.csv"))
    if video_path:
        details["video_directory"] = video_path
    return [*files, results], details


def publish(args, plan, checkout, staging):
    task = plan["task"]
    task_path = FORMAL / task
    root = checkout / ARTIFACTS
    snapshot = root / "snapshot.json"
    manifest = json.loads(snapshot.read_text())
    task_info = manifest["tasks"].setdefault(task, {})
    weight = plan["weight"]
    weight_info = plan["models"][weight]
    oid = weight_info["sha256"]
    pointer_path = ARTIFACTS / task_path / weight
    pointer = git(checkout, "show", f"HEAD:{pointer_path}", check=False)
    expected_pointer = f'version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {weight_info["bytes"]}'
    model_needed = pointer != expected_pointer
    if model_needed and git(checkout, "check-attr", "filter", "--", str(pointer_path)).rsplit(": ", 1)[-1] != "lfs":
        raise ValueError(f"Git LFS filter is missing for {pointer_path}")

    evaluation = plan["evaluation"]
    eval_key = f"evaluation_{args.target}"
    eval_needed = False
    if evaluation:
        previous_result = root / task_path / f"eval_{args.target}" / "eval_episodes.csv"
        eval_needed = not evaluation_matches(
            task_info.get(eval_key), evaluation, oid, previous_result
        ) or (bool(pointer) and model_needed)
    if not model_needed and not eval_needed:
        print(f"{task}: already published ({oid[:12]})", flush=True)
        return

    sources = set(plan["models"]) if model_needed else set()
    if model_needed:
        cached = lfs_object(checkout, oid)
        if cached.is_file() and file_info(cached) == weight_info:
            sources.remove(weight)
            local = staging / weight
            local.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached, local)
    if eval_needed:
        sources.update(evaluation["videos"].values())
        if evaluation["raw_result"]:
            sources.add(evaluation["raw_result"])
    retrieve(args, task, sources, staging)

    entries = {entry["path"]: entry for entry in manifest["files"]}
    files = []
    if model_needed:
        for name, expected in plan["models"].items():
            source = staging / name
            if file_info(source) != expected:
                raise ValueError(f"Transferred artifact checksum mismatch for {task}: {name}")
            path = root / task_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
            files.append(path)
        task_info.update(training_completed=True, train_step=plan["steps"], target_steps=plan["steps"],
                         train_seconds=plan["train_seconds"], checkpoint=str(task_path / weight),
                         checkpoint_bytes=weight_info["bytes"], checkpoint_sha256=oid)
        task_info.setdefault("phase", "trained")
    if eval_needed:
        eval_files, task_info[eval_key] = stage_evaluation(root, task_path, evaluation, staging, oid)
        files.extend(eval_files)
        task_info["phase"] = "complete"
    elif model_needed and task_info.get(eval_key):
        task_info["phase"] = "complete"
    for path in files:
        relative = str(path.relative_to(root))
        entries[relative] = dict(path=relative, **file_info(path), lfs=path.suffix == ".safetensors")
    manifest["files"] = [entries[key] for key in sorted(entries)]
    write_json(snapshot, manifest)
    git(checkout, "add", "-f", "--", *(str(path.relative_to(checkout)) for path in [snapshot, *files]), timeout=120)
    if model_needed:
        if git(checkout, "show", f":{pointer_path}") != expected_pointer:
            raise ValueError(f"Git did not stage the expected Git LFS pointer for {task}")
        git(checkout, "lfs", "push", "--object-id", args.remote, oid, timeout=900)
    git(checkout, "commit", "-m", f"Publish C7 {'evaluation and model' if eval_needed else 'final model'} for {task}")
    git(checkout, "push", args.remote, f"HEAD:refs/heads/{args.branch}", timeout=900)
    print(f"{task}: published {git(checkout, 'rev-parse', 'HEAD')} ({oid[:12]})", flush=True)


def publish_from_latest(args, plan):
    ref = f"refs/remotes/{args.remote}/{args.branch}"
    git(REPO, "fetch", "--no-tags", args.remote, f"+refs/heads/{args.branch}:{ref}")
    with tempfile.TemporaryDirectory(prefix="sem-c7-publish-") as directory:
        temp = Path(directory)
        checkout = temp / "checkout"
        git(REPO, "worktree", "add", "--detach", str(checkout), ref)
        try:
            publish(args, plan, checkout, temp / "transfer")
        finally:
            git(REPO, "worktree", "remove", "--force", str(checkout))


def main():
    config = json.loads((REPO / "configs/project.json").read_text())
    tasks = [item["name"] for item in config["tasks"] if item["include"]]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloud", required=True, help="SSH host or alias for the cloud instance")
    parser.add_argument("--cloud-root", type=Path, default=Path("/root/sj-tmp/SEM-RoboTwin/runs/c7-formal"))
    parser.add_argument("--cloud-repo", type=Path, default=Path("/root/SEM-RoboTwin-git"))
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--task", action="append", choices=tasks, help="Repeat to select tasks; default is all configured tasks")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--watch", action="store_true", help="Keep polling until all selected tasks are published")
    mode.add_argument("--check", action="store_true", help="Read cloud status without publishing")
    parser.add_argument("--weights-only", action="store_true", help="Publish finished training even before evaluation")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if args.interval <= 0 or args.cloud.startswith("-") or not args.cloud_root.is_absolute() or not args.cloud_repo.is_absolute():
        parser.error("Use a positive interval, an SSH host, and absolute cloud paths")
    args.target = config["eval_episodes_target"]
    args.demos = config["episodes_per_task_target"]
    pending = list(dict.fromkeys(args.task or tasks))
    while pending:
        failed = False
        for task in pending[:]:
            try:
                plan = get_plan(args, task)
                if args.check or plan is None:
                    print(f"{task}: {'ready' if plan else 'waiting'}", flush=True)
                else:
                    publish_from_latest(args, plan)
                    pending.remove(task)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                detail = getattr(error, "stderr", None) or str(error)
                if isinstance(detail, bytes):
                    detail = detail.decode(errors="replace")
                print(f"{task}: {detail.strip()}", file=sys.stderr, flush=True)
                failed = True
        if not args.watch:
            return int(failed)
        if pending:
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--source"]:
        _, root, repo, task, target, demos, weights_only = sys.argv[1:]
        sys.path.insert(0, str(Path(repo) / "scripts"))
        print(json.dumps(source_plan(Path(root).resolve(strict=True), task, int(target), int(demos), weights_only == "1")))
    else:
        sys.exit(main())
