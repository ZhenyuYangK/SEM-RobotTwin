# Codex执行规范：SEM-Tiny×RoboTwin2.0

## 目标与边界
- 当前阶段：**仅本地预开发**，Ubuntu22.04+RTX4060 8GB。不得操作云GPU；不得下载完整模型、仿真资产和数据集。
- 后续云端：RTX4090 24GB、CUDA12.1.1镜像，16核CPU/90GB内存。独立单任务SEM-Tiny实验固定为配置中的5个任务，先验证第1个任务，再逐项推进其余4个。多任务联合训练需要独立审批与实验编号。
- 原始资料仅保存在本地`teacher_inputs/`并始终只读，仓库记录其SHA256和URDF的官方资产来源。禁止自动修补URDF的网格路径、关节拓扑、角度与关节限位。
- 优先维护本仓库`configs/`、`scripts/`、`tests/`、`docs/`。不要在未经批准时改动上游`src/RoboTwin`或`src/RoboOrchardLab`代码。

## 执行纪律
1. 一切上游路径、CLI参数、数据键名都从实际锁定版本源码检查，禁止编造。旧版RoboTwin使用`script/eval_policy.py`，新版主分支可能不同；不可自动升级。
2. 不使用`sudo pip install`，不升级系统CUDA/驱动，不执行大规模下载、不自动开启仿真或训练。
3. 有成本、破坏性或长时间操作（克隆大型子模块、仿真资产下载、数据集复制、GPU训练、删目录/重写Checkpoint）先列出命令和风险，经用户确认再做。
4. 运行前列出环境、输入/输出、预期显存/磁盘占用；默认`dry-run`，必须显式执行才动资源。
5. 既定的`sem_policy`、`demo_clean`、`seed=10000`、`instruction_type=unseen`固定。`expert_data_num`由当前源码核对含义，切勿当作评估次数。
6. `config_sem_robotwin.py`训练默认`multi_task=False`；必须核对实际模型Tiny骨干和预训练权重路径。
7. 缺少真实数据、未安装依赖、无法运行GPU时，清楚区分“静态测试已通过”与“云端集成尚未验证”。
8. 修改后运行`bash scripts/run_local_checks.sh`；更新`reports/`下结果与`docs/PHASE_PLAN.md`的进度，不用虚构实验结果。
9. 产生临时文件使用`tempfile`/系统临时目录；每次交付前清理可再生缓存；不要删原始数据和正式训练产物。
10. 不将云端IP、SSH私钥、API key、Token和凭据写入仓库或日志。
11. 每一阶段执行完毕同步进度表述，并进行阶段git提交，并推送到main
12. 环境有需要时优先寻找本地是否已经有符合但是没有找过的环境例如cuda等，如果没有再下载相关依赖，同时记录本地哪些环境已经满足

## 本地与云端的Git同步

- 项目远端为GitHub仓库`ZhenyuYangK/SEM-cloud`，保留用户确认的公开可见性。
- 代码、配置和文档在本地提交到`main`并推送`origin`。云端在`/root/SEM-RoboTwin-git`执行`git pull --ff-only`同步。常规改动走Git。
- 云端检出后由`scripts/bootstrap_sources.sh --clone`复现锁定的上游源码。Vulkan运行库继续从`/root/SEM-RoboTwin/.runtime/`加载，Python环境及实验数据保存在数据盘。运行库、虚拟环境、模型权重、采集数据和SSH凭据保留在版本库之外。

## 本地验收门槛
- 源码已克隆并记录提交号；RoboTwin为固定提交。
- 通过原始URDF静态检查、路径资源差异报告；机器人运动学运行检验记作云端待执行。
- 任务列表来自锁定版`envs`，并在`configs/project.json`中标明经过验证的5个候选。
- 数据转换器、训练入口、评估入口和参数有可复核的源码位置；本地工具有测试。
- 准备云端逐阶段验收文档；未获批准不租用和启动云GPU。
