# 本地RTX4060 8GB：模型推理与调试准备

## 可以提前做

- Ubuntu22.04、NVIDIA驱动与`nvidia-smi`可用；VS Code、Git、OpenSSH、rsync已经配置。
- 查看SEM源代码中的`sem_policy/deploy_policy.py`和`config_sem_robotwin.py`，准备与训练环境一致的Python依赖版本记录（不要盲装新版本）。
- 本地下载云端最终的`model.safetensors`、模型配置、预处理器配置、对应URDF/机械臂参数等部署必需文件。

## 云端结果传回后怎么验证

1. 先只运行SEM-Tiny加载及**单样本无梯度推理**（`torch.inference_mode()`），记录显存峰值。
2. 再试最小RoboTwin场景；SAPIEN、CuRobo、Vulkan与SEM叠加显存可能超过8GB。
3. 如OOM，查看实际图像数量、分辨率、batch size和是否同时启动仿真；不要擅自修改模型输入维度并把它作为可比实验结果。
4. 正式成功率评估仍在云端RTX4090上执行，避免由于硬件和渲染条件不同影响可比性。

## 验收文件

记录`torch.__version__`、`torch.version.cuda`、GPU型号、CUDA显存峰值、模型输出维度、一次推理时间以及与云端模型输出的一致性检验（保持输入相同）。
