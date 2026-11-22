# SEM-Tiny×RoboTwin2.0

本项目使用SEM-Tiny在RoboTwin2.0中训练独立单任务策略，涵盖RGB-D示范采集、LMDB打包、训练和仿真评估。仓库包含五项C7正式实验和一项补充实验的训练配置、最终权重与逐回合结果。

## 复现入口

| 目标 | 入口 |
|---|---|
| 核对已发布成绩 | [100回合汇总](artifacts/sem-tiny/c7-formal/evaluation_100.csv) · [逐回合结果与视频](artifacts/sem-tiny/c7-formal/) · [SHA256清单](artifacts/sem-tiny/snapshot.json) |
| 评估已发布权重 | [下载指定任务权重并生成本机路径的评估配置](docs/DATA_TRAIN_EVAL.md#评估已发布权重) |
| 从采集开始重跑 | [准备运行环境](docs/CLOUD_HANDOFF.md) · [按已发布训练步数重跑](docs/DATA_TRAIN_EVAL.md#c7正式实验与补充实验) |
| 查阅原始实验过程 | [云端实验记录](reports/cloud_preflight.md#c7正式实验进展) · [验收阶段](docs/PHASE_PLAN.md) · [训练曲线](C7_curves/) |

每项实验使用100条示范，评估协议为`demo_clean`、`sem_policy`、`seed=10000`和`unseen`，每项统计100个有效回合。

| 任务 | 训练步数 | 成功回合 |
|---|---:|---:|
| `place_empty_cup` | 100000 | 91/100 |
| `adjust_bottle` | 100000 | 98/100 |
| `beat_block_hammer` | 100000 | 87/100 |
| `place_shoe` | 50000 | 75/100 |
| `place_container_plate` | 50000 | 94/100 |
| `click_bell`（补充） | 50000 | 55/100 |

## 本地检查

在项目根目录用Python3.10执行以下命令。脚本运行离线单测，并按本地可用文件执行原件校验、URDF结构检查及上游源码验证。检查报告写入临时目录，退出时自动清理。

```bash
bash scripts/run_local_checks.sh
```

获取GitHub源码前，核对目标为`HorizonRobotics/RoboOrchardLab`和`RoboTwin-Platform/RoboTwin`。脚本在`src/`稀疏检出文本源码，跳过Git LFS与子模块。下载、仿真和模型配置的细节见[源码审计](reports/code_audit.md)。

```bash
bash scripts/bootstrap_sources.sh --clone
python3 scripts/discover_tasks.py --workspace . --list
bash scripts/run_local_checks.sh
```

RoboTwin锁定`e71140e9734e69686daa420a9be8b75a20ff4587`，RoboOrchardLab锁定`41112765f9904efb2374dd9c8946fb5af452861a`。原始资料保存在本地`teacher_inputs/`，哈希值随仓库发布。公开检出可从锁定的RoboTwin资产取得同一URDF。[URDF来源](docs/CLOUD_HANDOFF.md#本地urdf检查) · [原件SHA256清单](reports/teacher_inputs_sha256.txt)

## 训练任务与工具

`configs/project.json`记录五项正式任务及补充任务`click_bell`。源码证据见[任务报告](reports/task_candidates.md)。

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
| `run_formal_experiments.py` | 校验任务和训练计划。通过C6后，可从采集开始运行指定单任务实验。 |
