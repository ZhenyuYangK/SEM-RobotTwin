# 本地→SSH云服务器迁移清单

## 1. 在本地配置SSH

```bash
sudo apt install -y openssh-client rsync git
ssh-keygen -t ed25519 -C sem-cloud  # 如已有可复用密钥则跳过
# ~/.ssh/config：
# Host sem4090
#   HostName <服务器地址>
#   User <用户名>
#   Port <平台端口>
#   IdentityFile ~/.ssh/id_ed25519
#   ServerAliveInterval 30
ssh sem4090
```

SSH账号、私钥、凭据不要放在本项目工作区。VS Code安装Remote-SSH和Codex扩展，以实际远程插件支持为准。

## 2. 本地完成验收，再同步轻量内容

```bash
bash scripts/run_local_checks.sh
# 最初推荐仅同步轻量内容，避免把本地数据缓存与模型权重推送到云端
rsync -av --dry-run --exclude 'src/' --exclude 'datasets/' --exclude 'runs/' --exclude '.git/' ./ sem4090:~/SEM-RoboTwin/
# 确认清单后去掉--dry-run（只同步代码、配置、文档）
```

首次云端源码由`bootstrap_sources.sh --clone`从GitHub克隆，或在无法访问GitHub时另行同步本地完整源码。云端必须对比提交哈希。

## 3. 云端预检命令（先不开始长任务）

```bash
hostname; uname -a; nvidia-smi
which nvcc && nvcc --version || true
lsblk -f; df -hT; free -h
command -v vulkaninfo && vulkaninfo --summary || true
python3 --version
```

- `vulkaninfo`必须看到NVIDIA物理设备而不是只看到llvmpipe。
- 若运行在容器中，检查NVIDIA驱动graphics能力；CUDA可用不等同于Vulkan可用。
- 检查数据盘的**真实挂载目录**，把数据集、LMDB、模型及视频写入数据盘，不能凭空假设`/data`存在。
- 初始数据盘按200GB估算，采集10条并打包后计算每条Episode大小再扩容。
- 当前费用参考¥1.98/小时；任何开始收费的实例操作由用户自己确认。

## 4. 云端停止与备份

- tmux保持SSH断连后训练进程；断连**不代表停止云GPU计费**。
- 先备份最终Checkpoint与评估日志到本地或持久云盘，再关停实例。
- 训练前确认租用平台停止计费和数据盘保留策略。
