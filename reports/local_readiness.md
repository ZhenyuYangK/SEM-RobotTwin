# 本地环境与验证记录

2026-11-19，在Ubuntu22.04.5、Python3.10.12、Git2.34.1笔记本完成。首轮15项离线单测通过，最终22项通过。两份原始资料在首轮及最终检查均通过`sha256sum -c reports/teacher_inputs_sha256.txt`。阶段提交记录保存在本包Git仓库。

## 本地已验证

| 检查 | 实际结果 |
|---|---|
| 两份原始资料 | `SEM评估流程.md`为`22c5a51582bf232ac4bc7aefcc518323f65a536216cb098a574dcba25d0c3e19`，`arx5_description_isaac.urdf`为`097c59fb19a7b482249c6097df8319586ea7cfd268c015516f103b289a7e761a`。原件由本地保管。[URDF来源](../docs/CLOUD_HANDOFF.md#本地urdf检查) |
| 源码 | `bash scripts/bootstrap_sources.sh --clone`完成文本源码检出，整个`src/`约21MiB。RoboTwin为`e71140e9734e69686daa420a9be8b75a20ff4587`，RoboOrchardLab为`41112765f9904efb2374dd9c8946fb5af452861a`。源码审计与证据行号见`code_audit.md`。 |
| URDF | 静态结构通过，54个Link、53个Joint、唯一根为`footprint`。30个Mesh路径本地未解析。报告路径指向输入文件的硬链接时，脚本正确拒绝写入。参照库存与结构结果见`urdf_differences.md`和`urdf_audit.json`。 |
| 任务 | `discover_tasks.py --workspace . --list`发现50个任务。`--validate`通过当前5个任务，顺序为`place_empty_cup`、`adjust_bottle`、`beat_block_hammer`、`place_shoe`、`place_container_plate`。源码证据见`task_candidates.md`。 |
| 入口与产物 | 在临时目录生成`demo_clean.yml`、SEM训练配置、部署YAML、评估启动器及5任务云端清单。对采集、打包、训练提取锁定源码中的`argparse`声明验证参数。评估对启动器执行`bash -n`，使用命令捕获替代运行环境，再调用锁定版解析函数核对参数与路径。统计CLI通过空模板和合成日志检查。 |
| 操作范围 | 按用户范围只在本地预开发。未连接GPU服务器、安装仿真依赖、下载权重或资产，也未启动采集、训练或仿真评估。 |

### 预开发阶段单测

通过`bash scripts/run_local_checks.sh`运行`python3 -m unittest discover -s tests -v`，22项全部通过。另在临时目录用仅含本包版本文件的归档复跑，22项仍通过，缺少源码的状态正确显示为`NOT_READY`。

| 套件 | 结果 | 覆盖 |
|---|---:|---|
| `TestCollection` | 3/3 | 采集配置开关、种子与文件编号、SEM数据键与帧数。 |
| `TestEval` | 6/6 | 评估参数、非法任务名、计数范围、空记录、重复种子、混合Checkpoint和完成日志。 |
| `TestTrainAndSource` | 9/9 | 配置补丁、任务源码检查、未核验任务拦截、预算与容量估算。 |
| `TestURDF` | 4/4 | 原始URDF、非法关节引用、非连通树、同名关节限位差异。 |

## 已有本地RoboTwin环境

在已有Conda环境`RoboTwin`核对Torch2.4.1+cu121、TorchVision0.19.1、SAPIEN3.0.0b1、MPLib0.2.1、NumPy1.26.4和h5py3.16.0。已用该环境通过HDF5深度无损压缩往返测试。

## 复现整理验证

26项单测、两份原件SHA256、上游锁定提交、五项正式任务和补充任务`click_bell`均通过本地检查。六项任务重新生成的采集与训练配置均与归档一致，100000步和50000步两组正式命令通过`--dry-run`。已核对六张100回合表的种子和成功数、599项文件清单及六个Git LFS指针，其中三个权重完整文件位于本地缓存并通过SHA256检查。本轮验收覆盖本地脚本、配置和产物，端到端仿真以云端实测记录为准。[云端实测记录](cloud_preflight.md)

## 云端验收与本地推理

RTX4090已完成环境、URDF、示范采集、LMDB打包、短训练与评估验收，五项正式实验和一项补充实验均已发布。P8的RTX4060单样本推理仍待实测。[云端记录](cloud_preflight.md) · [阶段进度](../docs/PHASE_PLAN.md) · [本地推理计划](../docs/LOCAL_4060.md)

## 预开发阶段的启动检查

| 初期发现 | 对应记录 |
|---|---|
| 本地缺少参照URDF与Mesh | 已在云端核对同一原件及实际资产。[URDF验收](urdf_differences.md#c3云端验收) |
| 默认`demo_clean`关闭Depth及Endpose | 用`prepare_collection.py`构建采集配置。[配置步骤](../docs/DATA_TRAIN_EVAL.md#采集与数据检查) |
| 初期缺少真实HDF5与h5py | 云端已校验首批示范，本地Conda环境已通过HDF5压缩往返检查。[云端采集记录](cloud_preflight.md#c4示范采集) |
| 初期依赖与权重待准备 | 云端已完成运行环境和模型加载验收。[评估实测](cloud_preflight.md#c6策略加载与缩量评估) |
| 固定版评估入口缺少缩量参数 | 用`run_smoke_eval.py`完成3回合冒烟。正式评估保持100个有效回合。[评估步骤](../docs/DATA_TRAIN_EVAL.md#评估与统计) |
