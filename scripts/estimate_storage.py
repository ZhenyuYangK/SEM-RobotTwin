#!/usr/bin/env python3
"""Estimate required disk capacity using real sample sizes, not guessed episode sizes."""
import argparse
from pathlib import Path


def estimate_storage(sample_raw_bytes, sample_lmdb_bytes, sample_count, tasks, episodes_per_task, extra_gib):
    if sample_count <= 0 or tasks <= 0 or episodes_per_task <= 0 or extra_gib < 0:
        raise ValueError('Invalid sample/task counts or extra reserve')
    if sample_raw_bytes < 0 or sample_lmdb_bytes < 0:
        raise ValueError('Negative bytes not allowed')
    n = tasks * episodes_per_task
    total = (sample_raw_bytes + sample_lmdb_bytes) / sample_count * n
    return {'episodes': n, 'raw_plus_lmdb_gib': total / (1024 ** 3), 'total_with_extra_gib': total / (1024 ** 3) + extra_gib}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sample-count', type=int, required=True, help='Number of episodes used for measurement')
    p.add_argument('--sample-raw-dir', type=Path, required=True)
    p.add_argument('--sample-lmdb-dir', type=Path, required=True)
    p.add_argument('--tasks', type=int, default=5)
    p.add_argument('--episodes-per-task', type=int, default=100)
    p.add_argument('--extra-gib', type=float, default=30.0, help='Fixed overhead for code, weights and videos (user assumption)')
    a = p.parse_args()
    def size(root):
        if not root.exists():
            p.error(f'Path does not exist: {root}')
        if root.is_file():
            return root.stat().st_size
        return sum(f.stat().st_size for f in root.rglob('*') if f.is_file())
    r = estimate_storage(size(a.sample_raw_dir), size(a.sample_lmdb_dir), a.sample_count, a.tasks, a.episodes_per_task, a.extra_gib)
    print('SCENARIO based on provided measured folders; account for duplicates/backups and room for growth.')
    for k, v in r.items():
        print(f'{k}: {v:.2f}' if isinstance(v, float) else f'{k}: {v}')


if __name__ == '__main__':
    main()
