# SEM-Tiny × RoboTwin 2.0｜本地预开发工程包

本工程包用于在**本地Ubuntu 22.04+VS Code+Codex+RTX 4060 8GB**上完成云服务器租用前的源码审计、老师URDF静态检查、任务发现、实验配置、数据/评估工具和测试。后续把通过验证的工作区同步至**RTX 4090 24GB云服务器**完成仿真采集、训练及成功率评估。

> 本包没有包含SEM/RoboTwin源码、模型权重、RoboTwin资产和训练数据；也没有声称完成任何GPU集成测试。联网克隆、依赖安装、数据采集、训练和评估均需显式操作。

## 0. 解压与离线自测（不连接云服务器）

```bash
unzip SEM_RoboTwin_LocalPrep_v1.zip
cd SEM_RoboTwin_LocalPrep
bash scripts/run_local_checks.sh
```

若脚本报告缺失`src/RoboTwin`和`src/RoboOrchardLab`，属于预期状态。初始离线自测应通过URDF解析、脚本单元测试、配置完整性等基础检查；源码检查会明确显示`NOT_READY`。

## 1. 用Codex获取并审计源码

把本目录用VS Code打开，先阅读`AGENTS.md`与`CODEX_START.md`。使用显式命令获取源码：

```bash
bash scripts/bootstrap_sources.sh --clone
python3 scripts/audit_sources.py --workspace .
python3 scripts/discover_tasks.py --workspace . --list
```

`bootstrap_sources.sh`仅克隆代码仓库、不下载模型、资产或数据；RoboTwin固定提交`e71140e9734e69686daa420a9be8b75a20ff4587`。RoboOrchardLab首次下载后锁定当前Git提交到`reports/source_revisions.json`，**再由Codex核验与SEM代码的兼容性**。

## 2. 选择任务、检查URDF、生成评估配置

```bash
python3 scripts/audit_urdf.py --urdf teacher_inputs/arx5_description_isaac.urdf --output reports/urdf_audit.json
python3 scripts/discover_tasks.py --workspace . --list
# 使用discover_tasks核验后，编辑configs/project.json中的tasks；默认仅选中place_empty_cup
python3 scripts/discover_tasks.py --workspace . --validate
python3 scripts/make_eval_config.py --task place_empty_cup --checkpoint checkpoints/place_empty_cup/model.safetensors --out generated/eval/place_empty_cup
```

生成的`deploy_policy.yml`和`eval.sh`是**待审核的部署草稿**，须与当前锁定的`sem_policy`及评估源码比对。不会直接复制到RoboTwin，不会执行评估。

## 3. 查看完整阶段计划和测试要求

- `docs/PHASE_PLAN.md`：本地完成、云端验收分界
- `docs/CLOUD_HANDOFF.md`：SSH、rsync迁移和云端清单
- `docs/DATA_TRAIN_EVAL.md`：数据采集、打包、训练、评估入口及核对项
- `docs/LOCAL_4060.md`：本地推理与8GB显存验证
- `docs/RESOURCE_BUDGET.md`：计费和容量估算
- `teacher_inputs/`：老师两份原文件，禁止改动

## 4. 云端使用原则

1. **先完成本地源码审计和脚本测试**，再租云GPU。
2. 云端按`Vulkan→小样本采集→打包→短训练→加载Checkpoint→少量评估→正式实验`逐级验收。
3. 先1任务，再5任务，再10任务。首轮独立单任务模型，明确`multi_task=False`，不把联合训练混进对照实验。
4. 每任务正式评估次数必须检查锁定版`script/eval_policy.py`，以真实日志和实际有效Episode计数为准；老师给定`seed=10000`、`demo_clean`、`sem_policy`不擅自修改。
5. 大文件只存入数据盘，记录每次训练Git提交、数据清单、参数快照、Checkpoint、结果和日志。

## 常用指令

```bash
bash scripts/run_local_checks.sh
python3 scripts/audit_sources.py --workspace .
python3 scripts/audit_urdf.py --urdf teacher_inputs/arx5_description_isaac.urdf --output reports/urdf_audit.json
python3 scripts/discover_tasks.py --workspace . --validate
python3 scripts/estimate_budget.py --tasks 5 --steps 100000 --minutes-per-1000 20 --hourly-rate 1.98
python3 scripts/summarize_eval.py --input templates/evaluation_results_template.csv --output reports/example_summary.csv
```

`evaluation_results_template.csv`只是格式示例，**里面不能写假成功率**：没有真实成功次数的数据行在汇总时会被跳过或报出提示。

云端有真实10条示范数据以后，可运行`scripts/estimate_storage.py`按样本字节测算200GB是否足够；在本地无示范数据时不要填虚拟大小冒充测量。
