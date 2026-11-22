# 本地RTX4060 8GB：模型推理与调试准备

P8单样本推理待实测。已有本地环境验证记录及RTX4090正式评估成绩可作参考。[本地环境](../reports/local_readiness.md#已有本地robotwin环境) · [100回合汇总](../artifacts/sem-tiny/c7-formal/evaluation_100.csv)

## 单样本推理准备

- 确认Ubuntu22.04环境和NVIDIA驱动，用`nvidia-smi`核对可用显存。
- 查看锁定SEM源码中的`sem_policy/deploy_policy.py`和`config_sem_robotwin.py`，记录本地依赖版本。
- 选择一个任务，获取其已发布权重、模型配置、预处理器配置以及对应URDF和机械臂参数。[权重路径与校验值](../artifacts/sem-tiny/snapshot.json)

## 推理验收步骤

1. 先只运行SEM-Tiny加载及**单样本无梯度推理**（`torch.inference_mode()`），记录显存峰值。
2. 再试最小RoboTwin场景；SAPIEN、CuRobo、Vulkan与SEM叠加显存可能超过8GB。
3. 如OOM，查看实际图像数量、分辨率、batch size和是否同时启动仿真；不要擅自修改模型输入维度并把它作为可比实验结果。
4. 正式成功率评估仍在云端RTX4090上执行，避免由于硬件和渲染条件不同影响可比性。

## 验收文件

记录`torch.__version__`、`torch.version.cuda`、GPU型号、CUDA显存峰值、模型输出维度、一次推理时间以及与云端模型输出的一致性检验（保持输入相同）。
