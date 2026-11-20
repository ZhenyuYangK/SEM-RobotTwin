# C1云端环境预检

2026-11-19。SSH直连、工程迁移、提交与资料核对已通过，首次预检定位到容器缺少图形驱动组件。随后在隔离运行目录补齐匹配的用户态库，RTX4090通过Vulkan验收。

## 已核对

| 项目 | 结果 |
|---|---|
| 实例 | Ubuntu22.04.4，16个可见逻辑CPU，容器内存上限90GiB，Python3.10.12。 |
| GPU与CUDA | NVIDIA GeForce RTX4090，`nvidia-smi`报告23028MiB显存及驱动580.105.08。驱动显示支持CUDA13.0，本机`nvcc`为12.1.105。CUDA Driver API的`cuInit`成功，发现1张GPU，计算能力为8.9。 |
| 数据盘 | `/root/sj-tmp`为XFS挂载，约200GiB可用，临时文件读写通过，探针文件已清理。系统根目录约30GiB。 |
| 迁移 | 云端工程为`/root/SEM-RoboTwin`。云端镜像缺少rsync，工程文件由本地Git提交`56ef6e4`归档迁移。两份老师原件SHA256均匹配。 |
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
