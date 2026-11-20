# SEM-Tiny×RoboTwin2.0锁定源码审计

| 仓库 | 实际提交 |
|---|---|
| RoboOrchardLab | `41112765f9904efb2374dd9c8946fb5af452861a` |
| RoboTwin | `e71140e9734e69686daa420a9be8b75a20ff4587` |

两个检出目录位于`src/`，记录见`source_revisions.json`。下文核对Git源码及默认配置，运行验收见`local_readiness.md`。

## SEM模型与训练

| 核对项 | 结论与源码证据 |
|---|---|
| Tiny骨干 | `SwinTransformer`的`embed_dims=96`、`depths=[2,2,6,2]`、`num_heads=[3,6,12,24]`。默认独立单任务，模型走3个特征层。RoboOrchardLab `projects/sem/robotwin/config_sem_robotwin.py:17–39,162–167,190–214`；同目录`README.md:22–47`。 |
| 默认值与权重 | `multi_task=False`、`task_names=["place_empty_cup"]`、`with_depth=True`、`with_depth_loss=True`、Batch=8、100000 Step。训练初始化权重为`./ckpt/groundingdino_swint_ogc_mmdet-822d7e9d-rename.pth`，`bert_checkpoint=./ckpt/bert-base-uncased`仅供`multi_task`分支构建文本编码器。数据默认为`./data/lmdb`，URDF为`./urdf/arx5/arx5_description_isaac.urdf`。同配置文件`:17–39,215–257,313–314,537–541,622–642`。 |
| 训练入口 | 从`projects/sem/robotwin/`执行`python3 train.py --workspace <实验目录> --config <Python配置文件>`。另有`--kwargs`（JSON文件或JSON对象字符串，覆盖配置字典）。配置由`importlib`执行，文件须为`.py`，切换配置文件位置不会切换当前工作目录。RoboOrchardLab `projects/sem/robotwin/train.py:52–94,130–152`、`utils.py:28–34,57–73`。 |
| 训练输出 | 写出`<workspace>/robotwin2_0_processor.json`；训练Hook从配置读取保存频率，默认每4000 Step，正常结束的Hook也保存。存储包含Accelerate状态及单模型导出的`model/`目录。云端以实际保存日志定位`model.safetensors`。同`train.py:71–76,113–125,139–148`；`robo_orchard_lab/pipeline/hooks/checkpoint.py:56–83,254–284,348–364`。 |

## 采集与打包

| 核对项 | 结论与源码证据 |
|---|---|
| 采集入口 | 在RoboTwin根目录执行`bash collect_data.sh <task> demo_clean <GPU索引>`。Shell传前两个位置参数给`script/collect_data.py`，第三个设`CUDA_VISIBLE_DEVICES`。Python入口先跑`Sapien_TEST()`，再解析两个位置参数并从`envs.<task>`实例化同名类。Shell第7行尝试执行`script/.update_path.sh`，该路径在此提交Git树中缺失，Shell继续执行第12行。RoboTwin `collect_data.sh:1–12`、`script/collect_data.py:22–29,39–74,236–250`。 |
| 默认场景 | `demo_clean`的`episode_num=100`、`save_path=./data`、机器人`aloha-agilex`，启用头部与腕部相机、RGB和qpos，关闭depth和endpose。SEM采集须在云端独立工作副本的同名YAML启用depth和endpose，并通过`episode_num`设小样本数量。RoboTwin `task_config/demo_clean.yml:1–36`、`envs/_base_task.py:437–452,467–524`。 |
| 输出与恢复 | `data/<task>/demo_clean/seed.txt`索引成功示范，依次写`data/episodeN.hdf5`、`video/episodeN.mp4`、`scene_info.json`。采集会跳过前面已存在的连续文件。语言生成在Python侧使用RoboTwin项目的`data/`约定目录写指令。读取`scene_info.json`时使用`save_path`，修改该值可能使指令与采集数据分离，数据盘应挂载或链接到项目`data/`。RoboTwin `script/collect_data.py:100–174,184–233`、`envs/_base_task.py:565–581`、`description/utils/generate_episode_instructions.py:134–175,253–287`。 |
| HDF5形状与内容 | `endpose`每帧为左右两侧各XYZ/RPY/夹爪共14值，`joint_action/vector`拼接双臂关节状态和夹爪。每个`observation/<camera>/`需`rgb`（每帧JPEG，固定宽度HDF5字节串）、`depth`（每帧二维，毫米）、`intrinsic_cv`和`extrinsic_cv`。RoboTwin `envs/_base_task.py:437–524`、`envs/camera/camera.py:295–321,412–448`、`envs/utils/pkl2hdf5.py:10–22,57–87`；SEM打包器`:150–192`。 |
| 打包入口与目录 | 从RoboOrchardLab根目录运行`python robo_orchard_lab/dataset/robotwin/robotwin_packer.py --input_path <RoboTwin/data> --output_path <新LMDB目录> --task_names <任务> --config_name demo_clean`。`--task_names`以逗号分隔。旧分支用的`--embodiment`、`--robotwin_aug`、`--camera_name`仍存在。遍历`<input>/<task>/<config>/seed.txt`及其`data/episodeN.hdf5`，使用N索引种子；读取同级`instructions/episodeN.json`。输出`depth/`、`image/`、`index/`、`meta/`。RoboOrchardLab `robo_orchard_lab/dataset/robotwin/robotwin_packer.py:43–132,150–237,241–274`、`projects/sem/robotwin/README.md:69–105`。 |
| 兼容性结论 | 固定版采集目录、键名和数据表示与所选打包器静态匹配，前提是启用depth和endpose。官方README对旧分支范围有备注，按首批真实文件完成HDF5→LMDB→DataLoader闭环。SEM `projects/sem/robotwin/README.md:73–105`、`robo_orchard_lab/dataset/robotwin/robotwin_lmdb_dataset.py:173–272`。 |

## 固定版评估

- `script/eval_policy.py --config policy/sem_policy/deploy_policy.yml --overrides ...`先加载YAML，再以成对参数覆盖，最后按`policy_name`导入`get_model`、`eval`和`reset_model`。沿用老师的`sem_policy`、`demo_clean`、`seed=10000`、`instruction_type=unseen`和`ckpt_setting=none`。上游入口先运行`Sapien_TEST()`，本地只做静态审查。RoboTwin `script/eval_policy.py:28–43,64–83,208–210,327–362`；RoboOrchardLab `projects/sem/robotwin/sem_policy/eval.sh:3–25`及同目录`__init__.py`。
- 老师`SEM评估流程.md:37–42`以`expert_data_num`记录训练示范数量。此提交的评估入口仅透传给策略，SEM的`get_model`只读取`ckpt_path`和`config_file`。其他策略可用它选训练产物，例如DP按该字段拼Checkpoint路径。固定版SEM正式评估由`test_num=100`决定，先过滤专家规划失败或场景不稳定的种子，再计数有效评估，初始场景种子为`100000 * (1 + seed)`。少量冒烟评估需另审独立入口或云端测试副本，没有已核实的缩量CLI。RoboTwin `script/eval_policy.py:153–183,200–260,291–324`、`policy/DP/deploy_policy.py:17–19`；RoboOrchardLab `projects/sem/robotwin/sem_policy/deploy_policy.py:193–195`。
- 策略部署至`RoboTwin/policy/sem_policy/`。`ckpt_path`和`config_file`若为相对路径，以策略模块目录解析。配置内的权重和URDF路径仍按各自加载器解析，部署建议用云端绝对路径。部署通过配置重建模型和Transform，从Safetensors加载参数，未读取训练导出的processor JSON。观测读取每个相机的RGB、depth和相机矩阵，双臂关节与夹爪按左、右拼接。RoboOrchardLab `projects/sem/robotwin/sem_policy/deploy_policy.py:30–85,92–127,130–177,193–207`。
- 输出为`eval_result/<task>/sem_policy/demo_clean/none/<时间>/_result.txt`，内容包含时间、指令类别和成功率。配置开启视频时写`episodeN.mp4`；有效Episode及成功计数从最后一条完成日志的`Success rate: S/N`审核录入，避免从小数反推。RoboTwin `script/eval_policy.py:124–132,176–185,262–289,303–324`。

## 安装留待云端

老师要求在RoboTwin运行环境中以可编辑模式安装RoboOrchardLab。SEM上游README列出PyTorch、TorchVision、Transformers、LMDB、Safetensors、Accelerate、Diffusers和h5py版本，且推荐CUDA11.8。项目计划使用CUDA12.1.1镜像，需在云端记录实际驱动、PyTorch所用CUDA、Vulkan和TorchVision等组件的验收结果。锁定RoboTwin的README第49–51行指向外部安装文档，资产下载及环境安装属于后续阶段。老师`SEM评估流程.md:3`；SEM `projects/sem/robotwin/README.md:50–67`；RoboTwin `README.md:49–51`。
