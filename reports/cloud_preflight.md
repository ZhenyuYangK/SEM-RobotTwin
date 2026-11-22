# 云端环境与实验记录

本报告按实验进程保存环境排查、采集、训练及续评记录。五项正式任务和补充任务`click_bell`均已完成。各任务的实际训练步数、评估方式及最终成绩见[100回合汇总](../artifacts/sem-tiny/c7-formal/evaluation_100.csv)。重跑步骤见[采集、训练与评估指南](../docs/DATA_TRAIN_EVAL.md)。

2026-11-19。SSH直连、工程迁移、提交与资料核对已通过，首次预检定位到容器缺少图形驱动组件。随后在隔离运行目录补齐匹配的用户态库，RTX4090通过Vulkan验收。

## 已核对

| 项目 | 结果 |
|---|---|
| 实例 | Ubuntu22.04.4，16个可见逻辑CPU，容器内存上限90GiB，Python3.10.12。 |
| GPU与CUDA | NVIDIA GeForce RTX4090，`nvidia-smi`报告23028MiB显存及驱动580.105.08。驱动显示支持CUDA13.0，本机`nvcc`为12.1.105。CUDA Driver API的`cuInit`成功，发现1张GPU，计算能力为8.9。 |
| 数据盘 | `/root/sj-tmp`为XFS挂载，约200GiB可用，临时文件读写通过，探针文件已清理。系统根目录约30GiB。 |
| 迁移 | 云端工程为`/root/SEM-RoboTwin`。云端镜像缺少rsync，工程文件由本地Git提交`56ef6e4`归档迁移。两份原始资料SHA256均匹配。 |
| 源码与任务 | 云端重新稀疏检出RoboTwin `e71140e9734e69686daa420a9be8b75a20ff4587`及RoboOrchardLab `41112765f9904efb2374dd9c8946fb5af452861a`，工作树均干净。云端运行`bash scripts/run_local_checks.sh`，22项单测通过，5项选定任务通过检查。 |
| 基础工具 | Git与FFmpeg已存在。初始Python环境缺少PyTorch、TorchVision、SAPIEN、CuRobo、h5py和LMDB。 |

## 首次Vulkan故障

- 镜像缺少Vulkan loader和`vulkaninfo`。为实际检查，从Ubuntu软件源取`libvulkan1`与`vulkan-tools`共369kB，在临时目录解包运行`vulkaninfo --summary`。结果为`vkCreateInstance failed with ERROR_INCOMPATIBLE_DRIVER`。探针与软件包已清理。
- 在容器的Vulkan清单目录和图形库目录均未发现NVIDIA Vulkan ICD或`libGLX_nvidia`、`libEGL_nvidia`。`NVIDIA_DRIVER_CAPABILITIES`未设置。结合CUDA探针成功与Vulkan实例创建失败，现有证据指向容器缺少NVIDIA图形驱动组件。[NVIDIA容器驱动能力说明](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html#driver-capabilities)
## Vulkan恢复与复测

在云端从NVIDIA官方Ubuntu22.04仓库下载与宿主`580.105.08`匹配的GL、GPU编译、通用配置及CFG用户态包，4个包共167169904字节，均通过官方包索引的SHA256验证。另解包Ubuntu的`libvulkan1`、`vulkan-tools`和`libegl1`。兼容的运行库保存在`/root/SEM-RoboTwin/.runtime/nvidia-vulkan-580.105.08/`，下载包与临时探针目录已清理，未运行包安装脚本。[NVIDIA580.105.08驱动组件说明](https://download.nvidia.com/XFree86/Linux-x86_64/580.105.08/README/installedcomponents.html)

GLX清单仍返回`ERROR_INCOMPATIBLE_DRIVER`。换用引用`libEGL_nvidia.so.0`的无头清单后，`vulkaninfo --summary`枚举到`NVIDIA GeForce RTX 4090`，设备类型为独立GPU，驱动为`NVIDIA_PROPRIETARY`，设备Vulkan API为1.4.312。

在云端为当前进程加载隔离驱动后可复查。若实例宿主驱动版本变化，先核对运行库版本。

```bash
driver="$HOME/SEM-RoboTwin/.runtime/nvidia-vulkan-580.105.08"
LD_LIBRARY_PATH="$driver/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  VK_ICD_FILENAMES="$driver/active-icd.json" "$driver/usr/bin/vulkaninfo" --summary
```

## C2进度

- 在云端数据盘`/root/sj-tmp/SEM-RoboTwin/venv`安装锁定RoboTwin所用的SAPIEN3.0.0b1。`pip check`通过。旧版SAPIEN导入时需要`pkg_resources`，隔离环境使用`setuptools==75.8.2`。安装包经临时目录转运，已清理。
- 沿用锁定版RoboTwin的Engine、Renderer及`rt`着色器路径，渲染内置方块并读取64×48相机的RGB和Position缓冲。实测RGBA形状为`(48,64,4)`，RGB值域差为0.510，中心深度为1700.00mm，与设置的1.7m近表面距离一致。场景使用内置几何体。RoboTwin `script/test_render.py:56–77`、`envs/camera/camera.py:412–448`。
- 为SAPIEN进程另设置`__EGL_VENDOR_LIBRARY_FILENAMES`为`$driver/usr/share/glvnd/egl_vendor.d/10_nvidia.json`，其中`$driver`与上一节相同。使用隔离库时，`LD_LIBRARY_PATH`、`VK_ICD_FILENAMES`和该变量需在启动Python前设置。
- CuRobo待完成CUDA版PyTorch安装、扩展编译和GPU功能验收。计划采用Torch2.4.1、TorchVision0.19.1的CUDA12.1版本及CuRobo v0.7.8提交`d64c4b005459db10c5dd867d8b30a87d5bda9bdb`。[PyTorch历史版本](https://pytorch.org/get-started/previous-versions/#v241) · [CuRobo v0.7.8编译配置](https://raw.githubusercontent.com/NVlabs/curobo/v0.7.8/setup.py)

## C2续跑记录

- 复查RTX4090为23028MiB显存，空闲时使用1MiB。数据盘约200GiB可用。FFmpeg列出`libx264`编码器。
- 云端Python3.10.12缺少`Python.h`。用Ubuntu快照中与已安装解释器同版本的`libpython3.10-dev`解包至数据盘`runtime/python-headers-3.10.12-1~22.04.4/`，软件包SHA256与Ubuntu包索引匹配。编译扩展时应把该目录下的`usr/include/python3.10`和`usr/include/x86_64-linux-gnu/python3.10`加入头文件搜索路径。[Ubuntu软件仓库快照](https://snapshot.ubuntu.com/ubuntu/20240715T000000Z/pool/main/p/python3.10/)
- 数据盘已准备两个锁定提交的独立运行副本。RoboOrchardLab运行副本缺失的3个打包文件从本地同一提交转运，Git对象哈希匹配。
- 原SSH连接在下载期间停止响应。重新登录后完成CUDA12.1版Torch2.4.1安装，并在RTX4090上验证CUDA卷积与cuDNN9.1.0。Torch、TorchVision和CUDA依赖的wheel均与发布源SHA256匹配。CuRobo首次编译因缺少多架构头文件的根目录失败，修正头文件搜索路径后重新编译。
- CuRobo0.7.8的5个CUDA扩展均编译并加载成功。UR5e带长方体障碍物的最小场景生成了31×6的有限GPU轨迹，终点位置误差为0.0m，单次规划约0.064秒，PyTorch峰值保留显存298MiB。Warp1.6.2在R580驱动上记录了`cuDeviceGetUuid`兼容提示，升级至上游修复版本Warp1.8.1后成功枚举RTX4090。[NVIDIA Warp驱动兼容记录](https://github.com/NVIDIA/warp/issues/940)
- C2通过。`pip check`通过，已验证RoboTwin和SEM的运行包导入及PyTorch3D0.7.8的GPU最远点采样。软件版本清单在数据盘`logs/python-freeze.txt`，下载暂存文件已清理。

## C4示范采集

- 官方`objects.zip`共3737778549字节，通过发布清单SHA256校验。锁定的`demo_clean`关闭背景随机化，物体和机械臂资源已满足本次采集。解包完成后已清理下载包。[RoboTwin官方资产](https://huggingface.co/datasets/TianxingChen/RoboTwin2.0/tree/3dc3b798668feb99ac61cc9086d84cbcc3d79186)
- `place_empty_cup`使用种子0～9生成10条成功示范，共1739帧，每条167～185帧。4路相机为前视、头部和双腕，深度分辨率为320×240。10条示范的RGB-D、相机参量、14维末端状态、14维关节动作和`seen`/`unseen`指令检查全部通过。10个视频已生成。
- 采集耗时251.6秒，显存采样峰值5772MiB。HDF5共4365619317字节。数据与证据在云端数据盘`runs/place_empty_cup-smoke/`，其中`hdf5_check.json`记录每条示范的结构、种子和文件大小。
- 首条示范的HDF5为447026974字节。对4路深度使用逐帧分块、`shuffle`和`gzip`级别1后，深度存储量从437452800字节降至57475873字节，读取后的数值和数据类型逐元素一致。据此估算首条压缩示范约67MB。正式采集入口在首次写入时启用该无损压缩。

## C5打包与短训练

- 10条示范已打包为148656393字节的LMDB。`image`、`depth`、`index`和`meta`均生成。DataLoader读到4路图像和深度，原始关节和末端状态为14维。变换后的动作训练输入包含`(1, 64, 14, 8)`的预测窗口。
- SEM-Tiny以`batch_size=2`、4个DataLoader工作进程运行1000步。训练日志记录`GlobalStep[1000/1000]`，含启动和保存耗时315秒，训练后段约0.28秒/步，显存采样峰值2508MiB。最终Checkpoint文件为198329592字节。
- 最终模型、处理器配置和训练日志保存在`runs/place_empty_cup-smoke/train-batch-2/`，Checkpoint为`checkpoints/checkpoint_1/model.safetensors`。C6已成功加载该Checkpoint。

## C6策略加载与缩量评估

- 首次推理在投影矩阵乘法处遇到`float32`与`float64`混用。生成的评估配置在乘法前把相机内参、世界到相机矩阵和机器人基座矩阵统一为`float32`。同一Checkpoint复测通过，动作序列形状为`(32, 14)`，数值均为有限值。
- 按`sem_policy`、`demo_clean`、`seed=10000`、`unseen`、`ckpt_setting=none`使用3个有效Episode验收，结果为0/3。日志、`_result.txt`、CSV计数和3个可读取的视频一致。实际评估耗时299.1秒，显存采样峰值5566MiB。
- 证据保存在数据盘`runs/place_empty_cup-smoke/`的`eval_smoke_projection.log`、`eval_smoke_summary.csv`和`eval_result/`。

## C7正式实验启动

- 启动时使用`run_formal_experiments.py`从`place_empty_cup`开始。初始计划为每任务采集100条成功示范、以`batch_size=2`独立训练100000步、评估100个有效回合。
- 结果目录为数据盘`runs/c7-formal/`，总控日志为`logs/c7-formal.log`。启动时可用容量约180GiB。按初始计划和C5后段0.28秒/步估算，5项训练约38.9小时，以当时的1.98元/小时计算约77元。该预算覆盖训练阶段。
- 首项100条示范通过结构与文件检查，原始目录为6338551210字节，LMDB为1448296725字节。首条正式HDF5为67100223字节，4路深度均使用无损`gzip`级别1。`place_empty_cup`正式训练已开始，超过1000步时的平均耗时为0.28秒/步。

## C7正式实验进展

2026-11-20 20:07（太平洋时间）进度快照。云端最多同时运行3项独立实验。[并行调度代码](../scripts/c7_parallel)

| 任务 | 训练进度 | 正式评估 |
| --- | --- | --- |
| `place_empty_cup` | 100000/100000步，约9小时14分钟 | 手动停止。计划100回合，已完成94回合，其中86次成功（91.49%） |
| `adjust_bottle` | 100000/100000步，训练完成 | 15/15次成功（100.00%）。[前15回合记录](../artifacts/sem-tiny/c7-formal/adjust_bottle/eval_episodes.csv) · [评估视频第1至15段](../artifacts/sem-tiny/c7-formal/adjust_bottle/eval_100/videos) |
| `beat_block_hammer` | 100000/100000步，训练完成 | 13/15次成功（86.67%）。[前15回合记录](../artifacts/sem-tiny/c7-formal/beat_block_hammer/eval_episodes.csv) · [评估视频第1至15段](../artifacts/sem-tiny/c7-formal/beat_block_hammer/eval_100/videos) |
| `place_container_plate` | 18800/50000步 | 待训练完成，目标15回合 |

`place_empty_cup`使用100条成功示范和`batch_size=2`完成训练。最终Checkpoint为`runs/c7-formal/place_empty_cup/train/checkpoints/checkpoint_25/model.safetensors`，大小为198329592字节。训练日志记录`GlobalStep[100000/100000]`及结束保存，评估日志保存在同一任务目录的`eval.log`。

### 验收文件与代码

- `place_empty_cup`于10:48手动停止评估，汇总按已完成的94个有效回合计算。任务目录的`review_videos/`保留14条成功视频和1条失败视频，合计4分37秒。`selection.csv`记录原始回合与场景种子，其余80个评估视频文件已移至数据盘回收站。
- 云端调度已切换为后续任务每项15个有效回合。新调度器接管了`adjust_bottle`和`beat_block_hammer`的原训练进程。`place_container_plate`等待空闲名额。

- `main`上的验收包保留最终权重、模型与处理器配置、实测训练和评估配置、训练损失CSV、评估汇总、逐回合结果和视频。`place_empty_cup`保留代表视频。`adjust_bottle`和`beat_block_hammer`最初15回合的视频各自对应`eval_100/videos/`中的第1至15段。逐回合CSV记录场景种子和成败，视频编号对应回合编号。权重通过Git LFS下载，清单提供每个文件的SHA-256。[验收文件](../artifacts/sem-tiny/c7-formal) · [早期评估汇总](../artifacts/sem-tiny/c7-formal/results.csv) · [校验清单](../artifacts/sem-tiny/snapshot.json)
- 首项运行的工程检出为`3a20e74`，上游为RoboTwin `e71140e`和RoboOrchardLab `4111276`。已核对运行副本的任务、训练、打包和评估入口，以及SEM部署策略文件，均与锁定源码一致。[实际训练入口](https://github.com/ZhenyuYangK/SEM-cloud/blob/3a20e74496401cd1f09f36b23b5e006bfbfe6384/scripts/run_formal_experiments.py) · [历史并行调度](https://github.com/ZhenyuYangK/SEM-cloud/tree/3d681efcd425377bdf905df3666a39b7d2d8cd5b/artifacts/sem-tiny/c7-parallel-control) · [RoboTwin源码](https://github.com/RoboTwin-Platform/RoboTwin/tree/e71140e9734e69686daa420a9be8b75a20ff4587) · [RoboOrchardLab源码](https://github.com/HorizonRobotics/RoboOrchardLab/tree/41112765f9904efb2374dd9c8946fb5af452861a)
- 完整日志和可续训状态留在云端。先前的全量产物快照可按历史提交访问。[历史快照](https://github.com/ZhenyuYangK/SEM-cloud/tree/93e69994c7fb033d9e52de27e15b4fceadcd353f/artifacts/sem-tiny)

11:03（太平洋时间）确认云端调度已加载50000步和15个有效评估回合的目标，排队的`place_container_plate`将使用这套配置。`adjust_bottle`和`beat_block_hammer`在交接后沿用100000步，验收使用各自的实际训练配置、完成日志和Checkpoint。[项目配置](../configs/project.json)

项目评估目标已恢复为100回合。按原评估日志，`adjust_bottle`续评从候选种子`1000100022`开始，`beat_block_hammer`从`1000100018`开始，各增加85个有效回合。[续评入口](../scripts/c7_parallel/extend_eval.py)

### 100回合评估视频

完整归档的视频按评估回合编号保存，逐回合CSV将视频与场景种子及成败对应。汇总记录实际回合数及单次评估或分段续评的方式。[100回合汇总](../artifacts/sem-tiny/c7-formal/evaluation_100.csv)

云端调度已加载100回合目标，并接管`place_container_plate`原有训练进程。`adjust_bottle`和`beat_block_hammer`依次续评，各自沿用原Checkpoint和指令采样设置。合并后核对了原15条记录、100个唯一场景种子、成功计数和对应视频文件。

| 任务 | 原评估 | 新增评估 | 合计 | 新增评估耗时 |
| --- | --- | --- | --- | --- |
| `adjust_bottle` | 15/15 | 83/85 | 98/100（98%） | 4296.71秒 |
| `beat_block_hammer` | 13/15 | 74/85 | 87/100（87%） | 3674.62秒 |

串行续评实测合计7971.33秒。云端各任务目录的`eval_to_100/`保存合并结果，原评估和续评各自的日志与视频保留在任务目录中。

2026-11-21，`place_empty_cup`沿用100000步Checkpoint和原评估设置，从候选种子`1000100110`开始续评6个有效回合。新增成功5次，耗时337.10秒，合并结果为91/100（91%）。已逐条核对原94回合及合并后的100个唯一场景种子。新增6段视频保存在云端续评目录。[逐回合结果](../artifacts/sem-tiny/c7-formal/place_empty_cup/eval_100/eval_episodes.csv) · [评估摘要](../artifacts/sem-tiny/c7-formal/place_empty_cup/eval_100/summary.json)

2026-11-21，`place_shoe`列入C7正式任务。锁定源码与本地配置生成已核对，待采集100条成功示范、训练50000步并评估100个有效回合。[任务清单](task_candidates.md)

2026-11-21，`place_shoe`已开始50000步训练。`place_container_plate`的最终模型`checkpoint_12`已补传。GitHub可下载4个已完成任务的最终权重，每个文件198329592字节，SHA-256均与云端对应Checkpoint一致。[C7验收文件](../artifacts/sem-tiny/c7-formal) · [发布脚本](../scripts/c7_parallel/publish.py)

2026-11-21，`place_shoe`和补充实验`click_bell`均完成50000步训练和100回合评估，分别成功75次和55次。两项的最终权重、逐回合结果及各100段评估视频已发布。[100回合汇总](../artifacts/sem-tiny/c7-formal/evaluation_100.csv)
