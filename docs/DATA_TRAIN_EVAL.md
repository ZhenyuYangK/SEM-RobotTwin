# 数据采集→SEM训练→老师要求的评估：执行前核查

## 代码和接口出处

- SEM官方README：`https://github.com/HorizonRobotics/RoboOrchardLab/tree/master/projects/sem/robotwin`
- RoboTwin固定提交：`e71140e9734e69686daa420a9be8b75a20ff4587`
- SEM官方训练入口：`cd projects/sem/robotwin && python3 train.py --config config_sem_robotwin.py`
- SEM官方数据打包入口：`python robo_orchard_lab/dataset/robotwin/robotwin_packer.py --input_path ... --output_path ... --task_names ... --config_name demo_clean`。
- SEM官方示例输出数据结构：LMDB目录包含`depth/`、`image/`、`index/`、`meta/`。
- SEM官方部署：`projects/sem/robotwin/sem_policy/README.md`要求复制`config_sem_robotwin.py`、准备URDF与模型Checkpoint、复制`sem_policy`进`RoboTwin/policy/`，并将评估用task_config中的`depth`打开。
- 老师评估命令：`python script/eval_policy.py --config policy/sem_policy/deploy_policy.yml --overrides ...`；`seed=10000`、`demo_clean`、`instruction_type=unseen`。

**重要**：SEM README特别注明打包命令适用于所述RoboTwin旧版/Challenge-Cup版本；必须在本地锁定代码后验证选定提交与打包脚本的实际匹配情况。若数据采集格式与打包输入不匹配，记录差异并停止，不得默默编写猜测转换器。

## 本地可做的准备

1. 读取实际源码确定`collect_data.sh`、任务的`episode_num`配置、HDF5层级与深度数据开关。
2. 检查`robotwin_packer.py --help`及其`argparse`，核对所有参数。
3. 准备训练配置副本而不是在上游仓库直接改原始文件。固定`multi_task=False`、`task_names=[该任务]`、`with_depth=True`、`with_depth_loss=True`；数据与URDF路径指向部署环境实际路径。
4. 注意训练Checkpoint可能需要`model.safetensors`与相关模型配置文件、预处理器配置共同部署；检查`sem_policy/deploy_policy.py`的实际加载机制。
5. 评估的`expert_data_num`须阅读`script/eval_policy.py`源码确认；**不要**拿它控制测试次数。真实成功率从实际结果文件计算。

## 云端按序执行（Codex需要进一步给出锁定版准确命令）

1. 检测GPU/Vulkan，安装依赖并运行最小SAPIEN场景；验证老师URDF与资源加载。
2. 采集`place_empty_cup`的10条成功示范，检查RGB、Depth、机器人状态与动作。
3. 打包LMDB；验证`depth/image/index/meta`目录和dataset DataLoader。
4. 训练200~1000 Step并记录每1000 Step时间、显存峰值、Checkpoint加载能力。
5. 少量仿真评估和视频，核对seed、场景、评估计数。
6. 用户批准后进行正式5~10任务实验，逐任务保存配置快照、模型权重、随机种子、原始成功次数与日志。

## 结果文件

- 每任务：示范数量、Git提交、配置快照、train日志、loss曲线、Checkpoint、eval日志、成功次数/总次数、评估视频。
- 汇总：`scripts/summarize_eval.py`读取**真实数据填写**的CSV，输出逐任务及总体成功率；空数据行不产生结果。
