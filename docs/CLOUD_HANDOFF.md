# 云端运行环境

C7使用Ubuntu22.04.4、Python3.10.12、RTX4090 24GB和CUDA12.1。实测关键组件为Torch2.4.1、TorchVision0.19.1（均为CUDA12.1构建）、SAPIEN3.0.0b1、CuRobo0.7.8、Warp1.8.1、PyTorch3D0.7.8与FFmpeg的`libx264`。原实验完整的`pip freeze`记录在云端数据盘的`logs/python-freeze.txt`。[环境实测记录](../reports/cloud_preflight.md#c2续跑记录)

## 代码同步

- [ ] 在本地运行`bash scripts/run_local_checks.sh`，确认5个任务、原件哈希与锁定提交。提交代码后运行`git push origin main`。
- [ ] 首次检出时跳过Git LFS权重。需要评估某个模型时再下载对应任务的权重。

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/ZhenyuYangK/SEM-cloud.git
cd SEM-cloud
export PREP="$(pwd -P)"
bash scripts/bootstrap_sources.sh --clone
bash scripts/run_local_checks.sh
```

## 准备运行副本和外部输入

将`CLOUD_BASE`设为数据盘上的工程绝对路径。在全新环境中，执行以下命令创建独立副本，并补齐RoboOrchardLab可编辑安装所需的版本、许可和打包元数据。

```bash
export ROBOTWIN="$CLOUD_BASE/work/RoboTwin"
export SEM="$CLOUD_BASE/work/RoboOrchardLab"
mkdir -p "$CLOUD_BASE/work" "$CLOUD_BASE/runs" "$CLOUD_BASE/weights"
cp -an "$PREP/src/RoboTwin" "$PREP/src/RoboOrchardLab" "$CLOUD_BASE/work/"
git -C "$SEM" restore --ignore-skip-worktree-bits -- VERSION NOTICE MANIFEST.in
git -C "$ROBOTWIN" rev-parse HEAD
git -C "$SEM" rev-parse HEAD
```

两个提交应分别为RoboTwin的`e71140e9734e69686daa420a9be8b75a20ff4587`和RoboOrchardLab的`41112765f9904efb2374dd9c8946fb5af452861a`。在隔离的Python环境中按固定源码的SEM指南和C2实测记录补齐依赖，运行`python -m pip install -e "$SEM"`和`python -m pip check`，然后把锁定版`"$SEM/projects/sem/robotwin/sem_policy"`复制到`"$ROBOTWIN/policy/"`。原云端可以直接加载已有的`runtime/env.sh`。[固定源码审计](../reports/code_audit.md#运行依赖与环境验证) · [云端Vulkan与依赖记录](../reports/cloud_preflight.md)

| 输入 | 来源及放置位置 |
|---|---|
| 场景与机械臂资产 | 从固定资产版本`3dc3b798668feb99ac61cc9086d84cbcc3d79186`获取`objects.zip`和`embodiments.zip`，校验后解压至`$ROBOTWIN/assets/`。在RoboTwin运行副本根目录执行`python script/update_embodiment_config_path.py`生成CuRobo配置。[资产版本](https://huggingface.co/datasets/TianxingChen/RoboTwin2.0/tree/3dc3b798668feb99ac61cc9086d84cbcc3d79186) |
| 运动学URDF | `KINEMATICS_URDF="$ROBOTWIN/assets/embodiments/aloha-agilex/urdf/arx5_description_isaac.urdf"`。用`sha256sum`与`reports/teacher_inputs_sha256.txt`比对。 |
| GroundingDINO-Tiny预训练权重 | 按固定SEM源码中`projects/sem/robotwin/README.md`下载原始`groundingdino_swint_ogc_mmdet-822d7e9d.pth`并运行上游`tools/ckpt_rename.py`。将`PRETRAINED`设为转换后的`groundingdino_swint_ogc_mmdet-822d7e9d-rename.pth`绝对路径。 |
| BERT目录 | 将`BERT_CHECKPOINT`设为包含`model.safetensors`的模型目录。原运行使用`google-bert/bert-base-uncased`的`86b5e0934494bd15c9632b12f734a8a67f723594`版本。[BERT版本](https://huggingface.co/google-bert/bert-base-uncased/tree/86b5e0934494bd15c9632b12f734a8a67f723594) |

在下载目录用发布源登记的SHA256校验两个压缩包。

```bash
sha256sum -c <<'ASSET_SHA256'
6aa56b3cf1e1064f7c809308144da36b00815f8b137fef2d7e4de856f8becf27  objects.zip
85ffeff55a5066def5931224a85cfa3f8abaa1fbf779bd17789a7fb3f85bc789  embodiments.zip
ASSET_SHA256
```

从采集开始重跑时，数据盘保存原始示范、LMDB、日志与Checkpoint。运行前核对空间、Vulkan渲染与GPU规划。已发布权重的评估使用相同场景与机械臂资产。[资源预算](RESOURCE_BUDGET.md) · [采集和评估操作](DATA_TRAIN_EVAL.md)

### 本地URDF检查

如需运行URDF静态审计，先从上述固定版本获取`embodiments.zip`并核对压缩包SHA256。将其中的`aloha-agilex/urdf/arx5_description_isaac.urdf`提取到本地`teacher_inputs/`。运行本地检查脚本可核对该文件SHA256并检查关节与链接结构。[原件SHA256清单](../reports/teacher_inputs_sha256.txt) · [与官方资产的比对记录](../reports/urdf_differences.md#c3云端验收)

## 启动前预检

| 次序 | 启动前验证 | 应记录的证据 |
|---|---|---|
| 1 | 核对驱动、GPU、显存、CUDA和Vulkan。项目目标为RTX4090 24GB与CUDA12.1.1镜像。 | `nvidia-smi`、`vulkaninfo --summary`、Python和PyTorch版本及PyTorch实际CUDA。Vulkan输出应枚举NVIDIA物理设备。 |
| 2 | 核对数据盘的真实挂载点。把RoboTwin运行副本的`data/`映射到数据盘，确保LMDB、训练目录、评估日志和视频也落盘。 | `lsblk -f`、`df -hT`、实际目录与可用容量。取得第一批真实示范和LMDB后再估算正式容量。 |
| 3 | 对照锁定源码和上游指南审核依赖安装计划，验收SAPIEN最小场景、CuRobo、FFmpeg及可编辑的RoboOrchardLab安装。 | 运行环境依赖清单、最小场景、GPU渲染、规划及视频编码输出。 |
| 4 | 在获准的云端阶段准备所需权重、场景与机械臂资产。对比原始URDF和实际资产，确认仿真加载URDF和SEM运动学URDF各自的路径和用途。 | 原件与参照SHA256、`audit_urdf.py --compare`报告、Mesh加载、关节索引、夹爪约定和正运动学核对结果。 |
| 5 | 先执行`place_empty_cup`的10条冒烟采集、HDF5校验、LMDB打包与DataLoader读取，再按200～1000 Step短训练。 | 数据目录、种子、示范数量、路径和形状报告、显存峰值、Step吞吐、Checkpoint及processor导出。 |
| 6 | 完成策略加载与推理。对少量仿真评估审核独立入口或测试副本，正式评估回合数按项目配置。 | 训练产物加载、14维动作、`unseen`指令、有效Episode和成功计数、日志、`_result.txt`与视频。 |
| 7 | 首任务闭环后，按固定的5个任务清单逐项推进其余4个独立任务。 | 每任务配置、Git提交、原始数据清单、Checkpoint、时间及实际统计。 |

各阶段接口和配置见[采集与训练评估](DATA_TRAIN_EVAL.md)。停机前备份Checkpoint、配置和评估日志，并核对云端计费状态及数据盘保留状态。
