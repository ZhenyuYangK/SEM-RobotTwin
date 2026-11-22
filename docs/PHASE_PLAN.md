# 执行阶段与验收门槛

| 阶段 | 设备 | 工作 | 必须输出/验收 | 允许付费云GPU？ |
|---|---|---|---|---|
| L0 | 本地 | 核对可用原件SHA256，运行单测 | `scripts/run_local_checks.sh`输出 | 否 |
| L1 | 本地 | 获取Git源码并固定RoboTwin提交 | `audit_sources.py`生成的源码审计报告 | 否 |
| L2 | 本地 | 审计SEM模型和RoboTwin采集/评估接口 | 锁定源码、采集与评估入口 | 否 |
| L3 | 本地 | 用本地原件或锁定官方资产检查URDF结构、关节与Mesh | `audit_urdf.py`生成的结构报告 | 否 |
| L4 | 本地 | 从源码发现并选择5个候选任务 | `configs/project.json`及核验结果 | 否 |
| L5 | 本地 | 完成数据采集、打包、训练、评估脚本审查 | 命令清单、静态测试、无虚构参数 | 否 |
| L6 | 本地 | 统计工具、预算与云端迁移准备 | 单测通过，云端就绪清单 | 否 |
| C1 | 云端 | GPU/CUDA/驱动/Vulkan/磁盘检查 | `vulkaninfo`识别4090；数据盘已挂载 | 需要 |
| C2 | 云端 | 安装精确软件依赖、SAPIEN/CuRobo小场景 | 官方依赖功能通过 | 需要 |
| C3 | 云端 | 核对原始URDF与机械臂映射 | 正运动学、配置和Mesh能加载 | 需要 |
| C4 | 云端 | `place_empty_cup`的10条成功示范采集 | RGB-D+状态+动作完整 | 需要 |
| C5 | 云端 | HDF5→LMDB打包、加载数据、200~1000Step短训练 | LMDB的image/depth/index/meta存在；显存/速度已测 | 需要 |
| C6 | 云端 | 审核缩量入口并少量评估，核对日志统计 | 成功次数/有效Episode/视频目录 | 需要 |
| C7 | 云端 | 五项正式任务独立训练，每项统计100个有效评估回合 | 每任务Checkpoint、结果、日志与视频 | 需要 |
| P8 | 本地 | 从云端下载权重和配置，RTX4060单样本推理 | 测量GPU显存、无OOM、动作输出形状正确 | 否 |

**停止条件**：任一阶段的输入检查不通过，停在本阶段，不继续下载资产或启动长期训练。运行前获得用户明确批准。报告禁止把“设计/脚本编写”写成“真实跑通”。

## 特别说明

- 五项正式任务和补充任务`click_bell`均采用独立单任务SEM-Tiny训练。
- 通用入口默认50000步。按原实验复跑时显式指定每项的实际训练步数。[复现命令](DATA_TRAIN_EVAL.md#c7正式实验与补充实验)
- `expert_data_num`记录训练示范数量。项目通过`eval_episodes_target`指定评估回合数。
- 在实测第一批10个Episode磁盘占用前，数据盘200GB仅作**初期规划值**，而非总空间保证。

## 本地进度

| 阶段 | 结果 |
|---|---|
| L0 | Ubuntu22.04.5上核对两份原件哈希，基线15项单测通过。 |
| L1 | 两个Git源码检出完成，提交已记录。 |
| L2 | 完成SEM、采集、打包与评估接口逐项审计。 |
| L3 | 原始URDF静态结构通过。固定提交和本地资产目录均无参照URDF，实物差异对比纳入C3。 |
| L4 | 从50个真实源码任务中确认5个，保存所定顺序并验证配置。 |
| L5 | 工具的本地格式、配置和锁定版参数解析验证通过。 |
| L6 | 在锁定上游源码下，当前21项单测通过。[本地检查入口](../README.md#本地检查) |

P8的RTX4060单样本推理仍待实测。验收记录应包含模型加载结果、动作形状及显存峰值。[权重路径与校验值](../artifacts/sem-tiny/snapshot.json)

## 云端进度

C1与C2通过。RTX4090、Vulkan、SAPIEN的RGB-D渲染、Torch的CUDA卷积和CuRobo的GPU轨迹规划已验收。[云端运行环境](CLOUD_HANDOFF.md)

C3通过。原始URDF与官方仿真URDF的SHA256一致。已验证Mesh加载、双臂关节映射和正运动学。[URDF来源与校验](CLOUD_HANDOFF.md#本地urdf检查)

C4通过。`place_empty_cup`的10条成功示范已验证4路RGB-D、末端状态、关节动作及指令，并生成10个视频。[采集步骤](DATA_TRAIN_EVAL.md#采集与数据检查)

C5通过。LMDB和DataLoader已验收，1000步训练完成并保存Checkpoint。[短训练步骤](DATA_TRAIN_EVAL.md#打包与短训练)

C6通过。已验证Checkpoint加载、有限的32×14动作序列、3次有效评估和3个视频。短训练模型结果为0/3。[评估步骤](DATA_TRAIN_EVAL.md#评估与统计)

C7配置中的5项任务均已完成训练和100回合评估。`adjust_bottle`为98/100，`beat_block_hammer`为87/100，`place_empty_cup`为91/100，`place_container_plate`为94/100，`place_shoe`为75/100。5项最终权重均已通过Git LFS发布。[100回合汇总](../artifacts/sem-tiny/c7-formal/evaluation_100.csv)

补充实验`click_bell`完成50000步训练及100回合评估，成功55次，最终权重已发布。复现入口支持按任务指定已发布的训练步数。[100回合汇总](../artifacts/sem-tiny/c7-formal/evaluation_100.csv) · [复现命令](DATA_TRAIN_EVAL.md#c7正式实验与补充实验)
