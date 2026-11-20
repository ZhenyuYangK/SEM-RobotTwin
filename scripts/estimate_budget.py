#!/usr/bin/env python3
"""Scenario-based training budget calculator (not a timing benchmark)."""
import argparse


def estimate(tasks, steps, minutes_per_1000, hourly_rate, overhead_hours=0):
    if tasks <= 0 or steps <= 0 or minutes_per_1000 <= 0 or hourly_rate < 0 or overhead_hours < 0:
        raise ValueError('tasks, steps, minutes-per-1000 must be >0; prices and overhead must be >=0')
    per_task_hours = steps / 1000 * minutes_per_1000 / 60
    return {
        'training_hours_per_task': per_task_hours,
        'training_hours_all_tasks': tasks * per_task_hours,
        'training_plus_overhead_hours': tasks * per_task_hours + overhead_hours,
        'estimated_gpu_cost_cny': (tasks * per_task_hours + overhead_hours) * hourly_rate,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tasks', type=int, required=True)
    p.add_argument('--steps', type=int, required=True)
    p.add_argument('--minutes-per-1000', type=float, required=True, help='Observed OR explicitly hypothetical minutes per 1000 steps')
    p.add_argument('--hourly-rate', type=float, required=True)
    p.add_argument('--overhead-hours', type=float, default=0)
    a = p.parse_args()
    r = estimate(a.tasks, a.steps, a.minutes_per_1000, a.hourly_rate, a.overhead_hours)
    print('SCENARIO ONLY: rates and throughput are user inputs, not measured by this script')
    for k, v in r.items():
        print(f'{k}: {v:.2f}')


if __name__ == '__main__':
    main()
