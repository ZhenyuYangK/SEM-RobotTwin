#!/usr/bin/env python3
"""Run the locked RoboTwin evaluator with a smaller episode count in memory."""
import argparse
import os
from pathlib import Path
import sys

from discover_tasks import require_locked_task


EVALUATOR = 'script/eval_policy.py'
EPISODE_LIMIT = b'\n    test_num = 100\n'
MODEL_LOAD = b'\n    model = get_model(usr_args)\n'


def check_policy_actions(model):
    import numpy as np

    predict = model.get_action
    first_call = True

    def checked_predict(data):
        nonlocal first_call
        actions = predict(data)
        if actions.ndim != 2 or not actions.shape[0] or actions.shape[1] != 14:
            raise ValueError(f'Expected nonempty (steps, 14) policy actions, got {actions.shape}')
        if not np.isfinite(actions).all():
            raise ValueError('Policy returned nonfinite actions')
        if first_call:
            print(f'Policy action shape: {actions.shape}')
            first_call = False
        return actions

    model.get_action = checked_predict
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--episodes', type=int, required=True)
    parser.add_argument('--expert-data-num', type=int, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.episodes < 100 or args.expert_data_num < 1:
        parser.error('Use 1–99 smoke evaluation episodes and a positive training demo count')

    try:
        pinned = require_locked_task(args.workspace, args.task, EVALUATOR)
        runtime = args.runtime.resolve(strict=True)
        evaluator = runtime / EVALUATOR
        config = args.config.resolve(strict=True)
        source = (pinned / EVALUATOR).read_bytes()
        if runtime == pinned or evaluator.read_bytes() != source:
            raise ValueError('Use a separate runtime copy with the unchanged locked evaluator')
        if source.count(EPISODE_LIMIT) != 1 or source.count(MODEL_LOAD) != 1:
            raise ValueError('Unexpected episode limit or model initialization in the locked evaluator')
    except (OSError, ValueError) as error:
        parser.error(str(error))

    os.chdir(runtime)
    sys.path.insert(0, str(evaluator.parent))
    sys.argv = [
        str(evaluator), '--config', str(config), '--overrides',
        '--task_name', args.task, '--task_config', 'demo_clean',
        '--ckpt_setting', 'none', '--expert_data_num', str(args.expert_data_num),
        '--seed', '10000', '--policy_name', 'sem_policy', '--instruction_type', 'unseen',
    ]
    patched = source.replace(EPISODE_LIMIT, f'\n    test_num = {args.episodes}\n'.encode())
    patched = patched.replace(MODEL_LOAD, b'\n    model = check_policy_actions(get_model(usr_args))\n')
    exec(compile(patched, str(evaluator), 'exec'), {
        '__name__': '__main__', '__file__': str(evaluator), 'check_policy_actions': check_policy_actions,
    })


if __name__ == '__main__':
    main()
