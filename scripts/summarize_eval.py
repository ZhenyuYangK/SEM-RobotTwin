#!/usr/bin/env python3
"""Aggregate verified evaluation counts; never invent success counts from logs or checkpoints."""
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

from discover_tasks import SAFE_NAME


REQUIRED = {'task_name', 'episodes', 'successes'}
ANSI = re.compile(r'\x1b\[[0-9;]*m')
PROGRESS = re.compile(r'^Success rate: ([0-9]+)/([0-9]+) =>', re.M)


def eval_log_row(log, task, expected):
    if not SAFE_NAME.fullmatch(task) or expected < 1:
        raise ValueError('Use a valid task name and positive expected episode count')
    clean = ANSI.sub('', log)
    if not re.search(rf'^Task Name: {re.escape(task)}\s*$', clean, re.M):
        raise ValueError(f'Evaluation log does not identify {task}')
    if not re.search(r'^Policy Name: sem_policy\s*$', clean, re.M):
        raise ValueError('Evaluation log does not identify sem_policy')
    previous = 0
    matches = PROGRESS.findall(clean)
    for step, (raw_successes, raw_episodes) in enumerate(matches, 1):
        successes, episodes = int(raw_successes), int(raw_episodes)
        if episodes != step or successes - previous not in (0, 1):
            raise ValueError(f'Evaluation count sequence is inconsistent at episode {step}')
        previous = successes
    if len(matches) != expected or 'Data has been saved to ' not in clean:
        raise ValueError(f'Expected a finished run with {expected} episodes. Found {len(matches)} counts')
    return {'task_name': task, 'episodes': str(expected), 'successes': str(previous)}


def aggregate(rows):
    results = defaultdict(lambda: [0, 0, 0])  # attempts, success, number of records
    skipped = 0
    protocols = {}
    runs = set()
    for line_number, row in enumerate(rows, 2):
        task = (row.get('task_name') or '').strip()
        raw_n = (row.get('episodes') or '').strip()
        raw_s = (row.get('successes') or '').strip()
        if not raw_n and not raw_s:
            skipped += 1
            continue
        if not task or not raw_n or not raw_s:
            raise ValueError(f'CSV line {line_number}: missing name/episodes/successes')
        try:
            n, s = int(raw_n), int(raw_s)
        except ValueError as exc:
            raise ValueError(f'CSV line {line_number}: invalid integer') from exc
        if n < 1 or s < 0 or s > n:
            raise ValueError(f'CSV line {line_number}: invalid counts (successes must be between 0 and episodes)')
        protocol = tuple((row.get(key) or '').strip() for key in ('checkpoint', 'task_config', 'git_commit'))
        if protocols.setdefault(task, protocol) != protocol:
            raise ValueError(f'CSV line {line_number}: mixed checkpoint, task_config or Git commit for {task}')
        seed = (row.get('seed') or '').strip()
        if seed:
            try:
                run = (task, int(seed))
            except ValueError as error:
                raise ValueError(f'CSV line {line_number}: invalid seed') from error
            if run in runs:
                raise ValueError(f'CSV line {line_number}: repeated seed for {task}')
            runs.add(run)
        results[task][0] += n
        results[task][1] += s
        results[task][2] += 1
    output = []
    for task, (n, s, cnt) in sorted(results.items()):
        output.append({'task_name': task, 'episodes': n, 'successes': s, 'success_rate_pct': round(s/n*100, 4), 'records': cnt})
    return output, skipped


def main():
    p = argparse.ArgumentParser(description=__doc__)
    inputs = p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--input', type=Path, help='Reviewed CSV counts')
    inputs.add_argument('--log', type=Path, help='Complete locked RoboTwin eval stdout log')
    p.add_argument('--task', help='Task in the evaluation log')
    p.add_argument('--expected-episodes', type=int, help='Expected log count (default: 100)')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        if a.log:
            if not a.task:
                raise ValueError('--log requires --task')
            expected = 100 if a.expected_episodes is None else a.expected_episodes
            report, skipped = aggregate([eval_log_row(a.log.read_text(encoding='utf-8'), a.task, expected)])
        else:
            if a.task or a.expected_episodes is not None:
                raise ValueError('--task and --expected-episodes are for --log')
            with a.input.open(encoding='utf-8-sig', newline='') as handle:
                reader = csv.DictReader(handle)
                missing = REQUIRED - set(reader.fieldnames or [])
                if missing:
                    raise ValueError(f'CSV missing fields: {sorted(missing)}')
                report, skipped = aggregate(reader)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with a.output.open('x', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['task_name', 'episodes', 'successes', 'success_rate_pct', 'records'])
            writer.writeheader()
            writer.writerows(report)
    except (OSError, ValueError) as error:
        p.error(str(error))
    if report:
        mean = 100 * sum(r['successes'] / r['episodes'] for r in report) / len(report)
        weighted = 100 * sum(r['successes'] for r in report) / sum(r['episodes'] for r in report)
        print(f'Tasks: {len(report)}, skipped empty rows: {skipped}; task mean={mean:.2f}%; pooled success={weighted:.2f}%')
    else:
        print(f'No verified evaluation counts to summarize. Skipped {skipped} empty row(s); output has headers only.')
    print(f'Wrote: {a.output}')


if __name__ == '__main__':
    main()
