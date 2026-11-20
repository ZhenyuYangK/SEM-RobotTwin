#!/usr/bin/env python3
"""Generate evaluation configuration drafts for the fixed SEM protocol; never launches evaluation."""
import argparse
import json
import re
import shlex
from pathlib import Path

from audit_sources import require_locked_files
from discover_tasks import SAFE_NAME, require_locked_task

POLICY = 'projects/sem/robotwin/sem_policy'


def projection_config(source):
    return f'''from runpy import run_path

from robo_orchard_lab.dataset.robotwin.transforms import ConvertDataType, GetProjectionMat


original = run_path({str(source)!r})
config = original['config']
build_model = original['build_model']


def build_transforms(config, calibration=None):
    train, validation = original['build_transforms'](config, calibration)
    index, = (i for i, transform in enumerate(validation) if transform['type'] is GetProjectionMat)
    match_projection_dtype = dict(type=ConvertDataType, convert_map={{
        name: 'float32' for name in ('intrinsic', 'T_world2cam', 'T_base2world')
    }})
    return train, [*validation[:index], match_projection_dtype, *validation[index:]]
'''


def create_files(task, checkpoint, config_file, expert_data_num, template_dir, *, episodes=100):
    if not SAFE_NAME.fullmatch(task):
        raise ValueError('Unsafe task name')
    if expert_data_num < 1:
        raise ValueError('expert_data_num must be a positive integer')
    if not 1 <= episodes <= 100:
        raise ValueError('Evaluation must use 1–100 valid episodes')
    for label, value in [('checkpoint', checkpoint), ('config_file', config_file)]:
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError(f'Invalid {label} string')
    if not config_file.endswith('.py'):
        raise ValueError('config_file must end in .py')
    yml = (template_dir / 'deploy_policy.yml.template').read_text(encoding='utf-8')
    sh = (template_dir / 'eval.sh.template').read_text(encoding='utf-8')
    values = {'@@CHECKPOINT@@': json.dumps(checkpoint, ensure_ascii=False),
              '@@CONFIG_FILE@@': json.dumps(config_file, ensure_ascii=False)}
    yml = re.sub(r'@@(?:CHECKPOINT|CONFIG_FILE)@@', lambda match: values[match[0]], yml)
    workspace = template_dir.resolve().parent
    values = {'TASK': task, 'EXPERT_DATA_NUM': str(expert_data_num), 'EPISODES': str(episodes),
              'WORKSPACE': shlex.quote(str(workspace)),
              'EVAL_RUNNER': shlex.quote(str(workspace / 'scripts/run_smoke_eval.py'))}
    sh = re.sub(r'@@([A-Z_]+)@@', lambda match: values[match[1]], sh)
    return yml, sh


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', default='.')
    p.add_argument('--task', required=True)
    p.add_argument('--checkpoint', required=True, help='Absolute runtime path or relative to the deployed sem_policy directory')
    p.add_argument('--config-file', default='config_sem_robotwin.py')
    p.add_argument('--align-projection-dtype', action='store_true',
                   help='Stage an evaluation config that casts projection matrices to float32 before multiplying')
    p.add_argument('--expert-data-num', type=int, required=True, help='Training demonstration count recorded by the evaluation workflow')
    p.add_argument('--episodes', type=int, default=100, help='Number of valid evaluation episodes')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    created = []
    try:
        robotwin = require_locked_task(a.workspace, a.task, 'script/eval_policy.py')
        sem = require_locked_files(a.workspace, 'RoboOrchardLab', f'{POLICY}/deploy_policy.py',
                                   f'{POLICY}/deploy_policy.yml', f'{POLICY}/eval.sh')
        dest = Path(a.out).resolve()
        if any(dest.is_relative_to(path) for path in (robotwin, sem)):
            raise ValueError('Stage the policy configuration outside the upstream checkouts')
        files = []
        config_file = a.config_file
        if a.align_projection_dtype:
            source = Path(config_file).resolve(strict=True)
            if not source.is_file() or source.suffix != '.py':
                raise ValueError('Projection dtype alignment needs an existing Python config')
            config_file = str(dest / 'eval_config.py')
            files.append(('eval_config.py', projection_config(source)))
        yml, script = create_files(a.task, a.checkpoint, config_file, a.expert_data_num, root / 'templates',
                                   episodes=a.episodes)
        files.extend([('deploy_policy.yml', yml), ('eval.sh', script)])
        dest.mkdir(parents=True, exist_ok=True)
        for name, content in files:
            path = dest / name
            with path.open('x', encoding='utf-8') as handle:
                created.append(path)
                handle.write(content)
    except (OSError, ValueError) as error:
        for path in created:
            path.unlink()
        p.error(str(error))
    print(f'Staged evaluation configuration and launcher in {dest}')
    print(f'Apply after checking checkpoint, config and depth in the cloud. Evaluation uses {a.episodes} valid episodes.')


if __name__ == '__main__':
    main()
