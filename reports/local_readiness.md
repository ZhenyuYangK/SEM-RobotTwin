# 本地预开发就绪报告

2026-11-19，在Ubuntu22.04.5、Python3.10.12、Git2.34.1笔记本完成。首轮15项离线单测通过，最终22项通过。两份原始资料在首轮及最终检查均通过`sha256sum -c reports/teacher_inputs_sha256.txt`。阶段提交记录保存在本包Git仓库。

## 本地已验证

| 检查 | 实际结果 |
|---|---|
| 两份原始资料 | `SEM评估流程.md`为`22c5a51582bf232ac4bc7aefcc518323f65a536216cb098a574dcba25d0c3e19`，`arx5_description_isaac.urdf`为`097c59fb19a7b482249c6097df8319586ea7cfd268c015516f103b289a7e761a`。两份均按原件保留。 |
| 源码 | `bash scripts/bootstrap_sources.sh --clone`完成文本源码检出，整个`src/`约21MiB。RoboTwin为`e71140e9734e69686daa420a9be8b75a20ff4587`，RoboOrchardLab为`41112765f9904efb2374dd9c8946fb5af452861a`。源码审计与证据行号见`code_audit.md`。 |
| URDF | 静态结构通过，54个Link、53个Joint、唯一根为`footprint`。30个Mesh路径本地未解析。报告路径指向输入文件的硬链接时，脚本正确拒绝写入。参照库存与结构结果见`urdf_differences.md`和`urdf_audit.json`。 |
| 任务 | `discover_tasks.py --workspace . --list`发现50个任务。`--validate`通过当前5个任务，顺序为`place_empty_cup`、`adjust_bottle`、`beat_block_hammer`、`place_shoe`、`place_container_plate`。源码证据见`task_candidates.md`。 |
| 入口与产物 | 在临时目录生成`demo_clean.yml`、SEM训练配置、部署YAML、评估启动器及5任务云端清单。对采集、打包、训练提取锁定源码中的`argparse`声明验证参数。评估对启动器执行`bash -n`，使用命令捕获替代运行环境，再调用锁定版解析函数核对参数与路径。统计CLI通过空模板和合成日志检查。 |
| 操作范围 | 按用户范围只在本地预开发。未连接GPU服务器、安装仿真依赖、下载权重或资产，也未启动采集、训练或仿真评估。 |

### 最终单测

通过`bash scripts/run_local_checks.sh`运行`python3 -m unittest discover -s tests -v`，22项全部通过。另在临时目录用仅含本包版本文件的归档复跑，22项仍通过，缺少源码的状态正确显示为`NOT_READY`。

| 套件 | 结果 | 覆盖 |
|---|---:|---|
| `TestCollection` | 3/3 | 采集配置开关、种子与文件编号、SEM数据键与帧数。 |
| `TestEval` | 6/6 | 评估参数、非法任务名、计数范围、空记录、重复种子、混合Checkpoint和完成日志。 |
| `TestTrainAndSource` | 9/9 | 配置补丁、任务源码检查、未核验任务拦截、预算与容量估算。 |
| `TestURDF` | 4/4 | 原始URDF、非法关节引用、非连通树、同名关节限位差异。 |

## 已有本地RoboTwin环境

在已有Conda环境`RoboTwin`核对Torch2.4.1+cu121、TorchVision0.19.1、SAPIEN3.0.0b1、MPLib0.2.1、NumPy1.26.4和h5py3.16.0。已用该环境通过HDF5深度无损压缩往返测试。

## 云端GPU验证

- 在RTX4090目标环境验证GPU驱动、Vulkan、CUDA、SAPIEN、CuRobo、可编辑安装和FFmpeg。
- 获取授权的真实机械臂资产后，完成原始URDF与RoboTwin参照的逐项对比、Mesh解析、14维状态顺序、运动学索引及夹爪映射验证。
- 先采集`place_empty_cup`的10条成功示范，核对实际HDF5、RGB-D、相机参量、机器人状态、示范种子与指令。随后验证HDF5→LMDB→DataLoader。
- 用已核验的LMDB、预训练权重和运行路径完成200～1000 Step短训练，再验收Checkpoint保存和加载。记录显存、吞吐和动作形状。
- 使用审定的少量评估入口验证仿真与统计闭环。正式评估由固定源码运行100个有效Episode，通过人工审核的原始日志和结果文件核对计数。详见`docs/CLOUD_HANDOFF.md`。

## 启动阻塞项

| 阻塞项 | 解除条件 |
|---|---|
| 参照URDF与Mesh缺失 | 在云端获准取得资产，核对`aloha-agilex`实际URDF和SEM运动学参照文件。 |
| 默认`demo_clean`关闭Depth及Endpose | 在独立云端运行副本应用`prepare_collection.py`生成且审核通过的同名YAML。 |
| 缺少真实HDF5与本机h5py | 在目标环境取得首批示范并用`inspect_hdf5.py`运行真实文件校验。 |
| 依赖与权重尚未到位 | 按云端检查清单备齐真实依赖和指定权重，完成最小环境、加载和数据读取验证。 |
| 固定版评估无缩量CLI | 在云端审查独立冒烟入口或隔离测试副本。`expert_data_num`保留为训练示范数，正式入口保留100个有效Episode。 |
