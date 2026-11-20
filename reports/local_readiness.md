# 本地工程包初始状态（自动化工具已实际执行）

- 已执行：`bash scripts/run_local_checks.sh`。
- Python标准库单元测试：15项通过（参见`tests/test_tools.py`；使用者可自行复跑）。
- 老师URDF静态结构：通过，54 Link、53 Joint、30个唯一Mesh引用；当前无完整Mesh资源，30个引用路径尚未在附件目录解析。
- 老师原始文件SHA256：`reports/teacher_inputs_sha256.txt`。
- RoboTwin与RoboOrchardLab仓库：**未打包进此工程包、尚未在当前环境克隆**。克隆后需执行源码接口核验，当前不宣称相关训练命令经过本地集成验证。
- 云端Vulkan、SAPIEN、CuRobo、LMDB打包、训练和成功率评估：**尚未进行真实运行**；必须在云端各阶段验收。
- 配置和脚本：目前可生成待审核配置模板和实验方案；正式执行需要按所锁定的源码和实际目录验证。
