#!/usr/bin/env python3
"""Aggregate verified evaluation counts; never invent success counts from logs or checkpoints."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path


REQUIRED = {'task_name', 'episodes', 'successes'}


def aggregate(rows):
    results = defaultdict(lambda: [0, 0, 0])  # attempts, success, number of records
    skipped = 0
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
        results[task][0] += n
        results[task][1] += s
        results[task][2] += 1
    output = []
    for task, (n, s, cnt) in sorted(results.items()):
        output.append({'task_name': task, 'episodes': n, 'successes': s, 'success_rate_pct': round(s/n*100, 4), 'records': cnt})
    return output, skipped


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    with Path(a.input).open(encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        if not REQUIRED.issubset(set(reader.fieldnames or [])):
            raise SystemExit(f'CSV missing fields: {sorted(REQUIRED)}')
        report, skipped = aggregate(list(reader))
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=['task_name','episodes','successes','success_rate_pct','records'])
        writer.writeheader()
        writer.writerows(report)
    if report:
        mean = sum(r['success_rate_pct'] for r in report) / len(report)
        weighted = 100 * sum(r['successes'] for r in report) / sum(r['episodes'] for r in report)
        print(f'Tasks: {len(report)}, skipped empty rows: {skipped}; task mean={mean:.2f}%; pooled success={weighted:.2f}%')
    else:
        print(f'No verified evaluation counts to summarize. Skipped {skipped} empty row(s); output has headers only.')
    print(f'Wrote: {output}')


if __name__ == '__main__':
    main()
