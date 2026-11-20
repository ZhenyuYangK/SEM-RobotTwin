# 老师URDF与RoboTwin资产差异报告

- 老师原件`teacher_inputs/arx5_description_isaac.urdf`的SHA256为`097c59fb19a7b482249c6097df8319586ea7cfd268c015516f103b289a7e761a`。XML解析与连通树检查通过，唯一根为`footprint`，54个Link、53个Joint，其中15个固定、10个连续、24个旋转、4个移动关节。30条唯一Mesh路径均为`aloha_maniskill_sim/meshes/…`，在本地原件目录均未解析。完整清单见`urdf_audit.json`。
- RoboTwin固定提交Git树中有0个URDF，本地`src/RoboTwin/assets/`也无URDF。默认`demo_clean`选`aloha-agilex`，映射到`assets/embodiments/aloha-agilex/`，另有独立`ARX-X5`条目。实际仿真URDF由资产目录的`config.yml`指定。SEM部署文档给出可能用于其运动学的`assets/embodiments/aloha-agilex/urdf/arx5_description_isaac.urdf`。本地差异核对状态为参照文件缺失。RoboTwin `task_config/demo_clean.yml:5–6`、`task_config/_embodiment_config.yml:1–14`、`script/collect_data.py:32–36`、`envs/robot/robot.py:40–79,105–119`；SEM `projects/sem/robotwin/sem_policy/README.md:15–27`。

## C3云端验收

- 官方`embodiments.zip`解包后，`aloha-agilex/config.yml`选择`urdf/arx5_description_isaac.urdf`。该文件与老师原件SHA256相同。官方资产URDF目录可解析全部30条Mesh路径，左右CuRobo配置已从官方模板生成。[RoboTwin官方机械臂资产](https://huggingface.co/datasets/TianxingChen/RoboTwin2.0/tree/3dc3b798668feb99ac61cc9086d84cbcc3d79186)
- SAPIEN加载54个Link和38个活动自由度。SEM运动学默认左臂索引10～15、右臂索引18～23，依次对应RoboTwin的`fl_joint1`～`fl_joint6`与`fr_joint1`～`fr_joint6`。夹爪基关节为`fl_joint7`与`fr_joint7`，各自带同侧随动关节，驱动区间为`[-0.01, 0.045]`。
- 两组姿态中，左右腕部和夹爪连杆的SAPIEN与SEM运动学变换矩阵最大元素差为`2.09e-7`。对比报告与实测日志在云端数据盘`logs/c3-urdf-comparison.json`和`logs/c3-fk.log`。
- 老师文件同时包含底盘和`fl`、`fr`、`lr`、`rr`四条臂链。SEM默认运动学用前两臂的`fl_link1..8`和`fr_link1..8`，这些名称都在老师文件中。运行时将14维双臂输入中的两组六个旋转关节写入运动学链索引`10..15`与`18..23`。云端需由真实解析器检查关节索引、夹爪数值约定、前臂连杆的正运动学与仿真一致性，并检查可视和碰撞网格。老师URDF`:543–853,884–1196,1226–1436,1462–1670`；SEM `robo_orchard_lab/dataset/robotwin/transforms.py:551–609,645–688`。
- 云端参照到位后，可给`scripts/audit_urdf.py`加`--compare <参照URDF> --asset-root <实际Mesh搜索目录> --output <报告路径>`，报告双方哈希、Link和Joint名称、同名关节父子关系、类型、轴、原点、限位和Mesh路径差异。
