# 执行阶段与验收门槛

| 阶段 | 设备 | 工作 | 必须输出/验收 | 允许付费云GPU？ |
|---|---|---|---|---|
| L0 | 本地 | 解压、校验原始资料、运行单测 | `reports/local_readiness.md` | 否 |
| L1 | 本地 | 获取Git源码并固定RoboTwin提交 | `reports/source_revisions.json` | 否 |
| L2 | 本地 | 审计SEM模型和RoboTwin采集/评估接口 | `reports/code_audit.md` | 否 |
| L3 | 本地 | URDF结构、关节、Mesh差异检查 | `reports/urdf_audit.json` | 否 |
| L4 | 本地 | 从源码发现并选择5个候选任务 | `configs/project.json`及核验结果 | 否 |
| L5 | 本地 | 完成数据采集、打包、训练、评估脚本审查 | 命令清单、静态测试、无虚构参数 | 否 |
| L6 | 本地 | 统计工具、预算与云端迁移准备 | 单测通过，云端就绪清单 | 否 |
| C1 | 云端 | GPU/CUDA/驱动/Vulkan/磁盘检查 | `vulkaninfo`识别4090；数据盘已挂载 | 需要 |
| C2 | 云端 | 安装精确软件依赖、SAPIEN/CuRobo小场景 | 官方依赖功能通过 | 需要 |
| C3 | 云端 | 核对原始URDF与机械臂映射 | 正运动学、配置和Mesh能加载 | 需要 |
| C4 | 云端 | `place_empty_cup`的10条成功示范采集 | RGB-D+状态+动作完整 | 需要 |
| C5 | 云端 | HDF5→LMDB打包、加载数据、200~1000Step短训练 | LMDB的image/depth/index/meta存在；显存/速度已测 | 需要 |
| C6 | 云端 | 审核缩量入口并少量评估，核对日志统计 | 成功次数/有效Episode/视频目录 | 需要 |
| C7 | 云端 | 完成固定5个任务的独立训练，后续每任务评估15次，首项保留已有评估记录 | 每任务Checkpoint+结果+日志+视频 | 需要 |
| P8 | 本地 | 从云端下载权重和配置，RTX4060单样本推理 | 测量GPU显存、无OOM、动作输出形状正确 | 否 |

**停止条件**：任一阶段的输入检查不通过，停在本阶段，不继续下载资产或启动长期训练。运行前获得用户明确批准。报告禁止把“设计/脚本编写”写成“真实跑通”。

## 特别说明

- 本轮固定为5个任务，均采用**独立单任务SEM-Tiny**训练。
- 上游参考为100000步。后续新启动的训练默认50000步，用1000步短训练测量吞吐。
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
| L6 | 22项最终单测通过。迁移和启动清单已写入`CLOUD_HANDOFF.md`。 |

本地执行记录分别见`reports/local_readiness.md`、`reports/code_audit.md`、`reports/urdf_differences.md`与`reports/task_candidates.md`。C1至C7及P8按顺序进入后续验收。

## 云端进度

C1与C2通过。RTX4090、Vulkan、SAPIEN的RGB-D渲染、Torch的CUDA卷积和CuRobo的GPU轨迹规划已验收。[云端预检报告](../reports/cloud_preflight.md)

C3通过。原始URDF与官方仿真URDF的SHA256一致。已验证Mesh加载、双臂关节映射和正运动学。[URDF验收报告](../reports/urdf_differences.md)

C4通过。`place_empty_cup`的10条成功示范已验证4路RGB-D、末端状态、关节动作及指令，并生成10个视频。[示范采集记录](../reports/cloud_preflight.md#c4示范采集)

C5通过。LMDB和DataLoader已验收，1000步训练完成并保存Checkpoint。[短训练记录](../reports/cloud_preflight.md#c5打包与短训练)

C6通过。已验证Checkpoint加载、有限的32×14动作序列、3次有效评估和3个视频。短训练模型结果为0/3。[缩量评估记录](../reports/cloud_preflight.md#c6策略加载与缩量评估)

C7运行中。`place_empty_cup`评估手动停止时86/94成功。`adjust_bottle`与`beat_block_hammer`的训练和15回合评估均已完成，验收包已归档。`handover_block`与`place_container_plate`仍在训练，目标分别为100000步与50000步。[正式实验进展](../reports/cloud_preflight.md#c7正式实验进展)
