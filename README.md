# SEM-Tiny×RoboTwin2.0

本包用于在Ubuntu22.04上锁定并审计SEM和RoboTwin源码，准备任务配置、URDF报告、数据工具和云端启动清单。本地验收见[本地就绪报告](reports/local_readiness.md)。

## 本地检查

在包含本README的目录执行以下命令。源码未检出时，原件校验、单测和URDF结构检查仍可离线运行。

```bash
bash scripts/run_local_checks.sh
```

获取GitHub源码前，核对目标为`HorizonRobotics/RoboOrchardLab`和`RoboTwin-Platform/RoboTwin`。脚本在`src/`稀疏检出文本源码，跳过Git LFS与子模块。下载、仿真和模型配置的细节见[源码审计](reports/code_audit.md)。

```bash
bash scripts/bootstrap_sources.sh --clone
python3 scripts/audit_sources.py --workspace .
python3 scripts/discover_tasks.py --workspace . --list
python3 scripts/discover_tasks.py --workspace . --validate
```

RoboTwin锁定`e71140e9734e69686daa420a9be8b75a20ff4587`，RoboOrchardLab锁定首次实际检出并审计的`41112765f9904efb2374dd9c8946fb5af452861a`。两份原始资料位于`teacher_inputs/`，哈希清单见`reports/teacher_inputs_sha256.txt`。

## 训练任务与工具

训练范围固定为`configs/project.json`中已确认的5个任务。先完成`place_empty_cup`的云端闭环，再逐项推进其余4个独立单任务实验。源码证据见[任务报告](reports/task_candidates.md)。

| 工具 | 用途 |
|---|---|
| `audit_urdf.py` | 检查原始URDF结构及当前资源，支持对本地参照URDF输出差异报告。 |
| `prepare_collection.py` | 生成云端暂存`demo_clean.yml`，开启Depth和Endpose并设置示范条数。 |
| `run_compressed_collection.py` | 运行锁定采集器，以无损压缩写入相机深度。 |
| `inspect_hdf5.py` | 检查真实单个HDF5文件，或按任务核验SEM采集目录、种子及数据键。 |
| `make_training_config.py` | 基于锁定SEM配置生成独立单任务Python配置。 |
| `make_eval_config.py` | 生成既定协议的部署YAML和启动器，`--expert-data-num`显式记录训练示范数。 |
| `run_smoke_eval.py` | 用锁定评估入口执行C6的缩量验证，在内存中调整Episode数。 |
| `summarize_eval.py` | 从完成日志或经核对的CSV统计有效Episode和成功数。 |
| `create_cloud_runbook.py` | 依据已确认任务生成云端逐项执行清单。 |
| `run_formal_experiments.py` | 通过C6后，按配置顺序运行5项正式实验并核对各项训练和评估产物。 |

云端步骤见[采集与训练评估](docs/DATA_TRAIN_EVAL.md)和[迁移与启动清单](docs/CLOUD_HANDOFF.md)。阶段验收见[阶段计划](docs/PHASE_PLAN.md)。
