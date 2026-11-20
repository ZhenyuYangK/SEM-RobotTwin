# 云端迁移与启动前清单

## 迁移

- [ ] 用户批准云端实例操作后配置SSH。账号、主机地址和私钥放在本机SSH配置或平台凭据管理处。
- [ ] 在本地运行`bash scripts/run_local_checks.sh`，确认5个任务、原件哈希与锁定提交。保存本地预开发仓库的Git提交号。
- [ ] 先预览迁移文件。已配置SSH别名`sem4090`时可从本包根目录执行以下预览命令，审核后再去掉`--dry-run`。

```bash
rsync -av --dry-run --filter=':- .gitignore' --exclude='.git/' \
  ./ sem4090:~/SEM-RoboTwin/
```

- [ ] 云端再次校验`sha256sum -c reports/teacher_inputs_sha256.txt`。用`bash scripts/bootstrap_sources.sh --clone`在`src/`复现两个稀疏源码检出，供本包校验与生成工具使用。
- [ ] 云端另准备可运行的独立副本，分别核对RoboTwin `e71140e9734e69686daa420a9be8b75a20ff4587`和RoboOrchardLab `41112765f9904efb2374dd9c8946fb5af452861a`。保存每个副本相对固定提交的配置差异，保持本包`src/`可用于回溯。
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
| 7 | 首任务闭环后再逐项开展首批5个独立任务。 | 每任务配置、Git提交、原始数据清单、Checkpoint、时间及实际统计。 |

各阶段接口和配置见[采集与训练评估](DATA_TRAIN_EVAL.md)。停机前备份Checkpoint、配置和评估日志，并核对云端计费状态及数据盘保留状态。
