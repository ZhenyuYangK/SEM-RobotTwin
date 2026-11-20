# 云端迁移与启动前清单

## 代码同步

- [ ] 在本地运行`bash scripts/run_local_checks.sh`，确认5个任务、原件哈希与锁定提交。提交代码后运行`git push origin main`。
- [ ] 云端首次检出后运行下列检查。以后在`/root/SEM-RoboTwin-git`执行`git pull --ff-only`同步代码。

```bash
git clone --branch main https://github.com/ZhenyuYangK/SEM-cloud.git /root/SEM-RoboTwin-git
cd /root/SEM-RoboTwin-git
sha256sum -c reports/teacher_inputs_sha256.txt
bash scripts/bootstrap_sources.sh --clone
bash scripts/run_local_checks.sh
```

- [ ] 两个上游运行副本分别核对RoboTwin `e71140e9734e69686daa420a9be8b75a20ff4587`和RoboOrchardLab `41112765f9904efb2374dd9c8946fb5af452861a`。保存每个副本相对固定提交的配置差异。
- [ ] 复用`/root/SEM-RoboTwin/.runtime/`的Vulkan运行库与`/root/sj-tmp/SEM-RoboTwin/venv`的Python环境。实验数据和产物保存在数据盘，SSH凭据保存在本机SSH配置或平台凭据管理处。
- [ ] 在本包运行`python3 scripts/create_cloud_runbook.py --output <新清单路径>`可生成已确认的5个任务的启动清单。

## 启动前预检

| 次序 | 启动前验证 | 应记录的证据 |
|---|---|---|
| 1 | 核对驱动、GPU、显存、CUDA和Vulkan。项目目标为RTX4090 24GB与CUDA12.1.1镜像。 | `nvidia-smi`、`vulkaninfo --summary`、Python和PyTorch版本及PyTorch实际CUDA。Vulkan输出应枚举NVIDIA物理设备。 |
| 2 | 核对数据盘的真实挂载点。把RoboTwin运行副本的`data/`映射到数据盘，确保LMDB、训练目录、评估日志和视频也落盘。 | `lsblk -f`、`df -hT`、实际目录与可用容量。取得第一批真实示范和LMDB后再估算正式容量。 |
| 3 | 对照锁定源码和上游指南审核依赖安装计划，验收SAPIEN最小场景、CuRobo、FFmpeg及可编辑的RoboOrchardLab安装。 | 运行环境依赖清单、最小场景、GPU渲染、规划及视频编码输出。 |
| 4 | 在获准的云端阶段准备所需权重、场景与机械臂资产。对比老师URDF和实际资产，确认仿真加载URDF和SEM运动学URDF各自的路径和用途。 | 原件与参照SHA256、`audit_urdf.py --compare`报告、Mesh加载、关节索引、夹爪约定和正运动学核对结果。 |
| 5 | 先执行`place_empty_cup`的10条冒烟采集、HDF5校验、LMDB打包与DataLoader读取，再按200～1000 Step短训练。 | 数据目录、种子、示范数量、路径和形状报告、显存峰值、Step吞吐、Checkpoint及processor导出。 |
| 6 | 完成策略加载与推理。对少量仿真评估审核独立入口或测试副本。正式评估沿用固定版100个有效Episode。 | 训练产物加载、14维动作、`unseen`指令、有效Episode和成功计数、日志、`_result.txt`与视频。 |
| 7 | 首任务闭环后，按固定的5个任务清单逐项推进其余4个独立任务。 | 每任务配置、Git提交、原始数据清单、Checkpoint、时间及实际统计。 |

各阶段接口和配置见[采集与训练评估](DATA_TRAIN_EVAL.md)。停机前备份Checkpoint、配置和评估日志，并核对云端计费状态及数据盘保留状态。
