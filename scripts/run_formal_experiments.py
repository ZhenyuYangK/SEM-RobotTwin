#!/usr/bin/env python3
"""Run the five verified SEM single-task experiments on the prepared cloud instance."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from audit_sources import require_locked_files
from discover_tasks import require_locked_task, validate_config
from summarize_eval import eval_log_row


WORKSPACE = Path(__file__).resolve().parents[1]


def run_logged(command, cwd, log_path, monitor_gpu=False):
    start = time.monotonic()
    print(f'Running {log_path.stem}. Log at {log_path}', flush=True)
    with log_path.open('x') as log:
        if monitor_gpu:
            with log_path.with_suffix('.gpu.csv').open('x') as telemetry:
                monitor = subprocess.Popen([
                    'nvidia-smi', '--query-gpu=timestamp,memory.used,utilization.gpu',
                    '--format=csv', '-l', '2',
                ], stdout=telemetry)
        else:
            monitor = None
        try:
            subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)
        finally:
            if monitor is not None:
                monitor.terminate()
                monitor.wait()
    return round(time.monotonic() - start, 2)


def map_output(path, target):
    if path.exists() and not path.is_symlink():
        raise ValueError(f'Expected missing path or symlink at {path}')
    temporary = path.with_name(f'.{path.name}.{os.getpid()}')
    temporary.symlink_to(target, target_is_directory=True)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run_task(args, task, project, robotwin, orchard):
    run_dir = args.output / task
    raw, staged, training, videos = (run_dir / name for name in ('raw', 'staged', 'train', 'eval_result'))
    run_dir.mkdir()
    for path in (raw, staged, training, videos):
        path.mkdir()
    demos = str(project['episodes_per_task_target'])
    episodes = project['eval_episodes_target']
    print(f'Starting {task} with {demos} demonstrations, {args.max_step} steps and {episodes} evaluations', flush=True)

    def tool(name, *params):
        subprocess.run([sys.executable, WORKSPACE / 'scripts' / f'{name}.py', *params], cwd=WORKSPACE, check=True)

    map_output(robotwin / 'data', raw)
    map_output(robotwin / 'eval_result', videos)
    tool('prepare_collection', '--task', task, '--episodes', demos, '--out', staged / 'demo_clean.yml')
    shutil.copyfile(staged / 'demo_clean.yml', robotwin / 'task_config/demo_clean.yml')
    run_logged([sys.executable, WORKSPACE / 'scripts/run_compressed_collection.py', '--runtime', robotwin,
                '--task', task], WORKSPACE, run_dir / 'collect.log', monitor_gpu=True)
    report_path = run_dir / 'hdf5_check.json'
    tool('inspect_hdf5', '--dataset-root', raw, '--task', task, '--episodes', demos, '--output', report_path)
    report = json.loads(report_path.read_text())
    raw_videos = raw / task / 'demo_clean/video'
    if not all(item['has_episode_instructions'] for item in report['episodes']) or any(
        not (raw_videos / f'episode{index}.mp4').stat().st_size for index in range(int(demos))
    ):
        raise ValueError(f'Incomplete demonstration artifacts for {task}')

    lmdb = run_dir / 'lmdb'
    run_logged([sys.executable, 'robo_orchard_lab/dataset/robotwin/robotwin_packer.py',
                '--input_path', raw, '--output_path', lmdb, '--task_names', task, '--config_name', 'demo_clean'],
               orchard, run_dir / 'pack.log')
    if not all((lmdb / name / 'data.mdb').stat().st_size for name in ('image', 'depth', 'index', 'meta')):
        raise ValueError(f'Incomplete LMDB for {task}')

    config = staged / 'train_config.py'
    urdf = robotwin / 'assets/embodiments/aloha-agilex/urdf/arx5_description_isaac.urdf'
    tool('make_training_config', '--task', task, '--data-path', lmdb, '--urdf', urdf,
         '--pretrained-checkpoint', args.pretrained, '--bert-checkpoint', args.bert,
         '--max-step', str(args.max_step), '--out', config)
    kwargs = staged / 'train_kwargs.json'
    kwargs.write_text(json.dumps({'batch_size': args.batch_size, 'num_workers': 4}) + '\n')
    train_seconds = run_logged([sys.executable, 'train.py', '--config', config, '--workspace', training,
                                '--kwargs', kwargs], orchard / 'projects/sem/robotwin',
                               run_dir / 'train.log', monitor_gpu=True)
    checkpoints = list(training.glob('checkpoints/checkpoint_*/model.safetensors'))
    checkpoint = max(checkpoints, key=lambda path: int(path.parent.name.rsplit('_', 1)[-1]))
    if not checkpoint.stat().st_size or not (training / 'robotwin2_0_processor.json').stat().st_size:
        raise ValueError(f'Incomplete checkpoint artifacts for {task}')

    tool('make_eval_config', '--task', task, '--checkpoint', checkpoint, '--config-file', config,
         '--align-projection-dtype', '--expert-data-num', demos, '--episodes', str(episodes),
         '--out', staged / 'sem_policy')
    policy = robotwin / 'policy/sem_policy'
    for name in ('eval.sh', 'deploy_policy.yml'):
        shutil.copyfile(staged / 'sem_policy' / name, policy / name)
    eval_log = run_dir / 'eval.log'
    eval_seconds = run_logged(['bash', 'eval.sh'], policy, eval_log, monitor_gpu=True)
    log = eval_log.read_text()
    counts = eval_log_row(log, task, episodes)
    saved, = re.findall(r'^Data has been saved to (.+)$', log, re.M)
    result = (robotwin / saved.strip()).resolve(strict=True)
    successes = int(counts['successes'])
    if (not result.is_relative_to(videos) or result.name != '_result.txt'
            or abs(float(result.read_text().splitlines()[-1]) - successes / episodes) > 1e-8
            or any(not (result.parent / f'episode{index}.mp4').stat().st_size for index in range(episodes))):
        raise ValueError(f'Evaluation results or videos are incomplete for {task}')
    summary_args = ('--log', eval_log, '--task', task, '--expected-episodes', str(episodes))
    tool('summarize_eval', *summary_args, '--output', run_dir / 'eval_summary.csv')
    tool('summarize_eval', *summary_args, '--episode-output', run_dir / 'eval_episodes.csv')
    return dict(task=task, demos=int(demos), steps=args.max_step, episodes=episodes, successes=successes,
                success_rate_pct=100 * successes / episodes, checkpoint=str(checkpoint),
                result=str(result), train_seconds=train_seconds, eval_seconds=eval_seconds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True, help='Data disk project root from the cloud preparation')
    parser.add_argument('--output', type=Path, required=True, help='New results directory under the data disk project')
    parser.add_argument('--max-step', type=int, required=True)
    parser.add_argument('--batch-size', type=int, required=True)
    parser.add_argument('--pretrained', type=Path, required=True)
    parser.add_argument('--bert', type=Path, required=True)
    args = parser.parse_args()
    args.base, args.output = args.base.resolve(strict=True), args.output.resolve()
    args.pretrained, args.bert = args.pretrained.resolve(strict=True), args.bert.resolve(strict=True)
    if args.max_step <= 0 or args.batch_size <= 0 or not args.output.is_relative_to(args.base):
        parser.error('Use positive training parameters and put the outputs on the data disk')
    project = json.loads((WORKSPACE / 'configs/project.json').read_text())
    problems, _, selected_count = validate_config(WORKSPACE, project)
    if problems or selected_count != 5:
        parser.error(f'Expected the five verified tasks: {problems}')
    selected = [entry['name'] for entry in project['tasks'] if entry['include']]
    if project['episodes_per_task_target'] != 100 or not 1 <= project['eval_episodes_target'] <= 100:
        parser.error('The formal experiment requires 100 demonstrations and 1–100 valid evaluations per task')
    smoke_run = args.base / 'runs/place_empty_cup-smoke'
    if not any(re.search(r'^C6 passed ', log.read_text(), re.M) for log in smoke_run.glob('phase6*.log')):
        parser.error('Complete the three-episode cloud evaluation before starting formal experiments')
    if not args.pretrained.stat().st_size or not (args.bert / 'model.safetensors').stat().st_size:
        parser.error('Missing verified pretrained weights')
    robotwin, orchard = (args.base / 'work' / name for name in ('RoboTwin', 'RoboOrchardLab'))
    evaluator = 'script/eval_policy.py'
    train = 'projects/sem/robotwin/train.py'
    packer = 'robo_orchard_lab/dataset/robotwin/robotwin_packer.py'
    pinned_robotwin = require_locked_task(WORKSPACE, selected[0], evaluator)
    pinned_orchard = require_locked_files(WORKSPACE, 'RoboOrchardLab', train, packer)
    for runtime, pinned, entries in ((robotwin, pinned_robotwin, (evaluator,)),
                                     (orchard, pinned_orchard, (train, packer))):
        for entry in entries:
            if (runtime / entry).read_bytes() != (pinned / entry).read_bytes():
                parser.error(f'Runtime file differs from the locked source: {entry}')
    os.environ.update(PYTHONUNBUFFERED='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUDA_VISIBLE_DEVICES='0',
                      TORCH_EXTENSIONS_DIR=str(args.base / 'runtime/torch_extensions'))
    with (args.base / 'runs/formal.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        args.output.mkdir()
        for task in selected:
            outcome = run_task(args, task, project, robotwin, orchard)
            print(json.dumps(outcome), flush=True)
            summary = args.output / 'results.csv'
            write_header = not summary.exists()
            with summary.open('a', newline='') as output:
                writer = csv.DictWriter(output, fieldnames=list(outcome))
                if write_header:
                    writer.writeheader()
                writer.writerow(outcome)


if __name__ == '__main__':
    main()
