#!/usr/bin/env python3
"""Make a human-reviewable runbook for verified tasks; never execute remote commands."""
import argparse
import json
from pathlib import Path

from discover_tasks import require_locked_task, validate_config
from audit_sources import require_locked_files


def runbook(cfg):
    tasks = [t['name'] for t in cfg['tasks'] if t.get('include') and t.get('status') == 'verified_in_pinned_source']
    if not tasks:
        raise ValueError('Select at least one task with status verified_in_pinned_source after code inspection')
    seed = cfg['eval_seed']
    if (cfg['train_mode'], cfg['eval_policy'], cfg['task_config'], seed,
            cfg['eval_instruction_type'], cfg['eval_episodes_target']) != (
                'single_task', 'sem_policy', 'demo_clean', 10000, 'unseen', 100):
        raise ValueError('This runbook generator requires the fixed evaluation protocol and 100 evaluated episodes')
    sections = [
        '# 云端独立单任务启动清单',
        '',
        f'按已确认顺序推进清单中的{len(tasks)}个任务。启动前完成`docs/CLOUD_HANDOFF.md`的迁移与环境核验。',
        '采集、打包、训练、评估的参数与当前提交见`reports/code_audit.md`。',
        '',
    ]
    for task in tasks:
        sections += [
            f'## `{task}`',
            '1. 在独立云端工作副本保留默认`demo_clean`名称。用`prepare_collection.py`暂存10条冒烟采集用YAML，检查depth、endpose和`RoboTwin/data`的实际挂载。',
            '2. 按脚本输出的固定版入口采集。核对成功示范、种子、视频与指令。用`inspect_hdf5.py --dataset-root`校验采集输出。',
            '3. 从RoboOrchardLab根目录使用审计中的打包入口写入新LMDB目录。检查depth、image、index、meta及首批DataLoader样本。',
            '4. 使用`make_training_config.py`生成单任务配置，按审计的`train.py`入口在200～1000 Step内验证显存、吞吐和Checkpoint。',
            '5. 使用`make_eval_config.py`生成既定协议的YAML和启动器。核对Checkpoint、URDF、深度和14维动作。正式评估入口固定为100个有效Episode，缩量冒烟入口需另审。',
            '6. 保留完整评估日志、`_result.txt`和视频。使用`summarize_eval.py`读取完成日志或已核对的CSV。',
            '',
        ]
    return '\n'.join(sections)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', default='.')
    p.add_argument('--config', default='configs/project.json')
    p.add_argument('--output', default='reports/cloud_runbook.md')
    a = p.parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding='utf-8'))
    try:
        problems, _, _ = validate_config(a.workspace, cfg)
        if problems:
            raise ValueError('; '.join(problems))
        for entry in cfg['tasks']:
            if entry.get('include'):
                require_locked_task(a.workspace, entry['name'], 'collect_data.sh', 'script/eval_policy.py')
        require_locked_files(a.workspace, 'RoboOrchardLab', 'projects/sem/robotwin/train.py',
                             'robo_orchard_lab/dataset/robotwin/robotwin_packer.py')
        text = runbook(cfg)
    except (OSError, ValueError) as error:
        p.error(str(error))
    out = Path(a.output)
    if out.exists():
        raise SystemExit(f'Refusing to overwrite existing runbook {out}')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    print(f'Wrote review-required runbook to {out}')


if __name__ == '__main__':
    main()
