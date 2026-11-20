#!/usr/bin/env python3
"""Make a human-reviewable runbook for verified tasks; never execute remote commands."""
import argparse
import json
from pathlib import Path


def runbook(cfg):
    tasks = [t['name'] for t in cfg['tasks'] if t.get('include') and t.get('status') == 'verified_in_pinned_source']
    if not tasks:
        raise ValueError('Select at least one task with status verified_in_pinned_source after code inspection')
    seed = cfg['eval_seed']
    if cfg['train_mode'] != 'single_task' or cfg['eval_policy'] != 'sem_policy' or cfg['task_config'] != 'demo_clean':
        raise ValueError('This runbook generator only supports teacher-aligned single task SEM baseline')
    sections = [
        '# 云端任务执行草案（不是可直接粘贴执行的脚本）',
        '',
        f'任务：{", ".join(tasks)}；seed={seed}；task_config=demo_clean。',
        '',
        '## 全局先决条件',
        '- 用户已明确同意付费GPU操作；完成Vulkan和数据盘挂载验证。',
        '- 核实RoboTwin固定提交、SEM提交、任务配置、深度数据开关以及所有权重和URDF路径。',
        '- 从锁定版`collect_data.sh`、`robotwin_packer.py`、`train.py`、`eval_policy.py`再次审查CLI。',
        '- 原始数据、LMDB、训练日志和Checkpoint全部保存到真实数据盘。',
        '',
    ]
    for task in tasks:
        sections += [
            f'## 任务`{task}`',
            '1. 采集10条成功演示（先修改并核实该任务的`episode_num`及depth开关）。',
            f'   - 官方示例入口：`cd <RoboTwin> && bash collect_data.sh {task} demo_clean 0`',
            '2. 使用`inspect_hdf5.py`验证一条真实样本的路径、shape和状态信息。',
            '3. 在SEM源码根目录核实打包器CLI。README示例：',
            f'   - `python robo_orchard_lab/dataset/robotwin/robotwin_packer.py --input_path <raw_hdf5_root> --output_path <lmdb_path> --task_names {task} --config_name demo_clean`',
            '4. 使用`make_training_config.py`从实际SEM配置生成单任务副本，设置真实LMDB与URDF路径、初次`max_step=1000`。',
            '5. 在SEM的`projects/sem/robotwin`目录运行`python3 train.py --config <审查通过的训练配置路径>`并记录Step速度/显存。',
            '6. 根据老师文档生成并审查`deploy_policy.yml`和`eval.sh`；确认真实Checkpoint路径与depth输入。',
            f'7. `cd <RoboTwin>/policy/sem_policy && bash eval.sh`（须经过正确复制到policy目录，任务为`{task}`）。',
            '8. 从真实`eval_result`提取有效Episode数与成功次数，填入CSV，使用`summarize_eval.py`汇总。',
            '9. 用户明确批准后扩大到每任务正式数据量和训练步数。',
            '',
        ]
    sections += ['**以上命令是受控执行草案；路径与依赖环境由Codex审查后填充。严禁直接在未知环境中批量粘贴运行。**', '']
    return '\n'.join(sections)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default='configs/project.json')
    p.add_argument('--output', default='reports/cloud_runbook.md')
    a = p.parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding='utf-8'))
    text = runbook(cfg)
    out = Path(a.output)
    if out.exists():
        raise SystemExit(f'Refusing to overwrite existing runbook {out}')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    print(f'Wrote review-required runbook to {out}')


if __name__ == '__main__':
    main()
