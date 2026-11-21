"""Run an individual C7 workflow in its isolated RoboTwin runtime."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(os.environ.get("CLOUD_BASE", "/root/sj-tmp/SEM-RoboTwin")).resolve()
REPO = Path(__file__).resolve().parents[2]
CONTROL = BASE / "runs/c7-parallel-control"
OUTPUT = BASE / "runs/c7-formal"
ROBOTWIN = BASE / "work/RoboTwin"
ORCHARD = BASE / "work/RoboOrchardLab"
TRAIN_DIR = ORCHARD / "projects/sem/robotwin"
URDF = ROBOTWIN / "assets/embodiments/aloha-agilex/urdf/arx5_description_isaac.urdf"
PRETRAINED = BASE / "weights/groundingdino_swint_ogc_mmdet-822d7e9d-rename.pth"
BERT = BASE / "weights/bert-base-uncased-86b5e0934494bd15c9632b12f734a8a67f723594"
DEMOS = 100
TASKS = tuple(
    task["name"] for task in json.loads((REPO / "configs/project.json").read_text())["tasks"]
    if task["include"]
)
SOURCES = {
    "adjust_bottle": BASE / "runs/adjust_bottle-parallel-check/raw",
    "beat_block_hammer": BASE / "runs/beat_block_hammer-parallel-check/raw",
}
sys.path.insert(0, str(REPO / "scripts"))
from run_formal_experiments import completed_training_steps, run_logged, training_steps_target
from summarize_eval import eval_log_row

def evaluation_target():
    episodes = json.loads((REPO / "configs/project.json").read_text())["eval_episodes_target"]
    if type(episodes) is not int or not 1 <= episodes <= 100:
        raise ValueError("eval_episodes_target must be an integer from 1 to 100")
    return episodes

def tool(name, *args):
    subprocess.run([sys.executable, REPO / "scripts" / f"{name}.py", *args], cwd=REPO, check=True)

def write_json(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)

def state(task, phase, **details):
    write_json(CONTROL / f"{task}.state.json", {"task": task, "phase": phase, "time": time.time(), **details})
    print(f"{task}: {phase}", flush=True)

def layout(task):
    run_dir = OUTPUT / task
    runtime = CONTROL / "runtimes" / task
    for key in ("raw", "staged", "train", "eval_result"):
        (run_dir / key).mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)
    for key in ("description", "envs", "script", "task_config", "policy"):
        if not (runtime / key).exists():
            shutil.copytree(ROBOTWIN / key, runtime / key, symlinks=True)
    for name, target in (("assets", ROBOTWIN / "assets"),
                         ("data", run_dir / "raw"), ("eval_result", run_dir / "eval_result")):
        link = runtime / name
        if link.is_symlink():
            if link.resolve() != target:
                raise ValueError(f"Incorrect link {link}")
        else:
            link.symlink_to(target, target_is_directory=True)
    return run_dir, runtime

def verified_inputs():
    for directory, name, paths in (
        (ROBOTWIN, "RoboTwin", ("script/eval_policy.py", "script/collect_data.py", "envs/utils/pkl2hdf5.py")),
        (ORCHARD, "RoboOrchardLab", ("projects/sem/robotwin/train.py",
                                   "robo_orchard_lab/dataset/robotwin/robotwin_packer.py")),
    ):
        for path in paths:
            if (directory / path).read_bytes() != (REPO / "src" / name / path).read_bytes():
                raise ValueError(f"Runtime does not match pinned source: {path}")
    for path in (URDF, PRETRAINED, BERT / "model.safetensors"):
        if not path.stat().st_size:
            raise ValueError(f"Empty required input {path}")

def train_task(task):
    run_dir, runtime = layout(task)
    raw, staged, lmdb, training = (run_dir / key for key in ("raw", "staged", "lmdb", "train"))
    if task in SOURCES:
        source = SOURCES[task] / task
        if not (raw / task).exists():
            subprocess.run(["cp", "-a", "--reflink=auto", source, raw / task], check=True)
    demo = staged / "demo_clean.yml"
    tool("prepare_collection", "--task", task, "--episodes", str(DEMOS), "--out", demo)
    shutil.copyfile(demo, runtime / "task_config/demo_clean.yml")
    os.environ["XDG_CACHE_HOME"] = str(runtime / "cache")
    (runtime / "cache").mkdir(exist_ok=True)
    state(task, "collect")
    run_logged([sys.executable, REPO / "scripts/run_compressed_collection.py", "--runtime", runtime, "--task", task],
               REPO, run_dir / "collect.log", monitor_gpu=True)
    report_path = run_dir / "hdf5_check.json"
    tool("inspect_hdf5", "--dataset-root", raw, "--task", task, "--episodes", str(DEMOS), "--output", report_path)
    report = json.loads(report_path.read_text())
    videos = raw / task / "demo_clean/video"
    if report["episode_count"] != DEMOS or not all(item["has_episode_instructions"] for item in report["episodes"]):
        raise ValueError(f"Incomplete demonstrations or instructions for {task}")
    if not all((videos / f"episode{i}.mp4").stat().st_size for i in range(DEMOS)):
        raise ValueError(f"Incomplete demonstration videos for {task}")
    state(task, "pack")
    run_logged([sys.executable, "robo_orchard_lab/dataset/robotwin/robotwin_packer.py",
                "--input_path", raw, "--output_path", lmdb, "--task_names", task, "--config_name", "demo_clean"],
               ORCHARD, run_dir / "pack.log")
    if not all((lmdb / name / "data.mdb").stat().st_size for name in ("image", "depth", "index", "meta")):
        raise ValueError(f"Incomplete LMDB for {task}")
    config = staged / "train_config.py"
    steps = training_steps_target()
    tool("make_training_config", "--task", task, "--data-path", lmdb, "--urdf", URDF,
         "--pretrained-checkpoint", PRETRAINED, "--bert-checkpoint", BERT, "--max-step", str(steps), "--out", config)
    kwargs = staged / "train_kwargs.json"
    write_json(kwargs, {"batch_size": 2, "num_workers": 4})
    state(task, "train", target_steps=steps)
    elapsed = run_logged([sys.executable, "train.py", "--config", config, "--workspace", training,
                          "--kwargs", kwargs], TRAIN_DIR, run_dir / "train.log", monitor_gpu=True)
    write_json(run_dir / "training_complete.json", {"train_seconds": elapsed})
    state(task, "trained")

def evaluate(task):
    episodes = evaluation_target()
    run_dir, runtime = layout(task)
    raw, staged, training, videos = (run_dir / key for key in ("raw", "staged", "train", "eval_result"))
    shutil.copyfile(staged / "demo_clean.yml", runtime / "task_config/demo_clean.yml")
    steps = completed_training_steps(run_dir)
    checkpoint = max(training.glob("checkpoints/checkpoint_*/model.safetensors"),
                     key=lambda path: int(path.parent.name.rsplit("_", 1)[-1]))
    if not checkpoint.stat().st_size or not (training / "robotwin2_0_processor.json").stat().st_size:
        raise ValueError(f"Incomplete checkpoint artifacts for {task}")
    config = staged / "train_config.py"
    tool("make_eval_config", "--task", task, "--checkpoint", checkpoint, "--config-file", config,
         "--align-projection-dtype", "--expert-data-num", str(DEMOS), "--episodes", str(episodes),
         "--out", staged / "sem_policy")
    policy = runtime / "policy/sem_policy"
    for name in ("eval.sh", "deploy_policy.yml"):
        shutil.copyfile(staged / "sem_policy" / name, policy / name)
    os.environ["XDG_CACHE_HOME"] = str(runtime / "cache")
    (runtime / "cache").mkdir(exist_ok=True)
    state(task, "eval")
    eval_log = run_dir / "eval.log"
    eval_seconds = run_logged(["bash", "eval.sh"], policy, eval_log, monitor_gpu=True)
    log = eval_log.read_text()
    counts = eval_log_row(log, task, episodes)
    saved, = re.findall(r"^Data has been saved to (.+)$", log, re.M)
    result = (runtime / saved.strip()).resolve(strict=True)
    successes = int(counts["successes"])
    if (not result.is_relative_to(videos) or result.name != "_result.txt"
            or abs(float(result.read_text().splitlines()[-1]) - successes / episodes) > 1e-8
            or any(not (result.parent / f"episode{i}.mp4").stat().st_size for i in range(episodes))):
        raise ValueError(f"Incomplete evaluation results or videos for {task}")
    summary_args = ("--log", eval_log, "--task", task, "--expected-episodes", str(episodes))
    tool("summarize_eval", *summary_args, "--output", run_dir / "eval_summary.csv")
    tool("summarize_eval", *summary_args, "--episode-output", run_dir / "eval_episodes.csv")
    elapsed = json.loads((run_dir / "training_complete.json").read_text())["train_seconds"]
    outcome = dict(task=task, demos=DEMOS, steps=steps, episodes=episodes, successes=successes,
                   success_rate_pct=100 * successes / episodes, checkpoint=str(checkpoint),
                   result=str(result), train_seconds=elapsed, eval_seconds=eval_seconds)
    write_json(run_dir / "completion.json", outcome)
    state(task, "complete")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("train", "eval", "full"))
    parser.add_argument("task", choices=TASKS)
    args = parser.parse_args()
    phase, task = args.phase, args.task
    try:
        verified_inputs()
        if phase in ("train", "full"):
            train_task(task)
        if phase in ("eval", "full"):
            evaluate(task)
    except Exception as error:
        state(task, "failed", operation=phase, error=str(error))
        raise

if __name__ == "__main__":
    main()
