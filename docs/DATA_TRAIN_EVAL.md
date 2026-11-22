# 采集、SEM训练与评估

以下命令在配置好依赖和资产的云端环境执行。`PREP`、`ROBOTWIN`、`SEM`、`CLOUD_BASE`和外部权重路径见[运行环境](CLOUD_HANDOFF.md)。配置生成工具读取`src/`中的锁定源码。

## 评估已发布权重

以下以`place_shoe`为例。其他任务的权重路径、训练步数和SHA256见[产物校验清单](../artifacts/sem-tiny/snapshot.json)。运行副本须完成资产和`sem_policy`部署。

```bash
(
set -euo pipefail
cd "$PREP"
TASK=place_shoe
WEIGHT="artifacts/sem-tiny/c7-formal/$TASK/train/checkpoints/checkpoint_12/model.safetensors"
git lfs pull --include="$WEIGHT" --exclude=""
sha256sum "$WEIGHT"
RUN_DIR="$(mktemp -d "$CLOUD_BASE/runs/eval-$TASK.XXXXXX")"

python3 scripts/prepare_collection.py --task "$TASK" --episodes 100 \
  --out "$RUN_DIR/staged/demo_clean.yml"
python3 scripts/make_training_config.py --task "$TASK" --data-path "$RUN_DIR/lmdb" \
  --urdf "$KINEMATICS_URDF" --max-step 50000 --out "$RUN_DIR/staged/train_config.py"
python3 scripts/make_eval_config.py --task "$TASK" --checkpoint "$PREP/$WEIGHT" \
  --config-file "$RUN_DIR/staged/train_config.py" --align-projection-dtype \
  --expert-data-num 100 --episodes 100 --out "$RUN_DIR/staged/sem_policy"
cp "$RUN_DIR/staged/demo_clean.yml" "$ROBOTWIN/task_config/demo_clean.yml"
cp "$RUN_DIR/staged/sem_policy/"{deploy_policy.yml,eval.sh} "$ROBOTWIN/policy/sem_policy/"
bash "$ROBOTWIN/policy/sem_policy/eval.sh" 2>&1 | tee "$RUN_DIR/eval.log"
python3 scripts/summarize_eval.py --log "$RUN_DIR/eval.log" --task "$TASK" \
  --expected-episodes 100 --episode-output "$RUN_DIR/eval_episodes.csv"
)
```

这里的LMDB路径用于生成模型配置，评估直接读取仿真观测。视频和`_result.txt`写入运行副本的`eval_result/`。逐回合CSV可按场景种子与发布记录对照。[已发布结果](../artifacts/sem-tiny/c7-formal/evaluation_100.csv)

## 采集与数据检查

首次完整闭环使用`RUN_DIR="$CLOUD_BASE/runs/place_empty_cup-smoke"`。在新的RoboTwin运行副本里，将`data/`链接到`$RUN_DIR/raw`，将`eval_result/`链接到`$RUN_DIR/eval_result`，并提前创建目标目录。串行正式入口会接管这两个链接。

1. 保持场景配置名`demo_clean`。在本包生成10条示范用配置，在独立云端运行副本审阅并应用到`task_config/demo_clean.yml`。默认相机为头部和双腕，采集需打开RGB、Depth、Endpose和QPos。
2. 将该运行副本的`data/`挂载或链接到独立数据盘目录。采集器会读取已有种子并跳过已有连续Episode，首次烟测应指向新的数据目录。指令输出也定位在RoboTwin的`data/`。
3. 从RoboTwin运行副本根目录使用生成器显示的`bash collect_data.sh place_empty_cup demo_clean 0`。检查成功示范、HDF5、视频、`scene_info.json`和指令文件。
4. 校验每个文件的Frame数、14维末端位置和关节状态、头部和双腕相机键、深度、相机矩阵与JPEG首尾帧。检查报告中的`has_episode_instructions`。

```bash
cd "$PREP"
python3 scripts/prepare_collection.py --task place_empty_cup --episodes 10 \
  --out "$RUN_DIR/staged/demo_clean.yml"
python3 scripts/inspect_hdf5.py --dataset-root "$ROBOTWIN/data" --task place_empty_cup \
  --episodes 10 --output "$RUN_DIR/hdf5_check.json"
```

上面第二条在采集完成后执行。也可用`--file <episodeN.hdf5> --sem`单独排查一个文件。

正式采集可从本包运行`python -u scripts/run_compressed_collection.py --runtime "$ROBOTWIN" --task place_empty_cup`。该入口校验锁定采集器和HDF5写入器，仅在写入相机深度数据集时启用HDF5无损压缩。对应的`demo_clean.yml`由`prepare_collection.py --episodes 100`生成并应用到运行副本。

## 打包与短训练

在已准备好的SEM运行环境中，从RoboOrchardLab根目录使用下列打包入口，选择新LMDB输出目录。随后检查`depth/`、`image/`、`index/`、`meta/`，用真实DataLoader读取首个Batch并核对指令、相机顺序和14维双臂状态。

```bash
cd "$SEM"
python robo_orchard_lab/dataset/robotwin/robotwin_packer.py \
  --input_path "$ROBOTWIN/data" --output_path "$RUN_DIR/lmdb" \
  --task_names place_empty_cup --config_name demo_clean
```

在本包运行配置生成器，`KINEMATICS_URDF`、`PRETRAINED`和`BERT_CHECKPOINT`由云端URDF与预训练权重验收提供。初次训练设置200～1000 Step，记录显存、吞吐、训练配置、`robotwin2_0_processor.json`和Checkpoint路径。生成器打印从SEM项目目录执行的训练入口。

```bash
cd "$PREP"
python3 scripts/make_training_config.py --task place_empty_cup \
  --data-path "$RUN_DIR/lmdb" --urdf "$KINEMATICS_URDF" \
  --pretrained-checkpoint "$PRETRAINED" --bert-checkpoint "$BERT_CHECKPOINT" \
  --max-step 1000 \
  --training-workspace "$RUN_DIR/train" --out "$RUN_DIR/staged/train_config.py"

printf '%s\n' '{"batch_size":2,"num_workers":4}' > "$RUN_DIR/staged/train_kwargs.json"
cd "$SEM/projects/sem/robotwin"
python -u train.py --config "$RUN_DIR/staged/train_config.py" \
  --workspace "$RUN_DIR/train" --kwargs "$RUN_DIR/staged/train_kwargs.json"
```

## 评估与统计

1. 在远程RoboTwin运行环境按既定要求安装RoboOrchardLab，部署审查过的`sem_policy`到`policy/sem_policy/`，保持`demo_clean`的Depth开启。确认`CHECKPOINT`指向实际训练产物，`EVAL_CONFIG`指向可加载的SEM Python配置。
2. 用刚实际参与训练的示范数量生成部署文件。核对YAML、路径和评估任务后应用到运行副本的策略目录。
3. 用`run_smoke_eval.py`验证模型加载、观测输入和14维双臂动作。该入口校验运行副本和锁定源码中的评估脚本一致，在内存中替换Episode数，并检查策略动作形状和有限值。C7正式评估回合数由`configs/project.json`的`eval_episodes_target`指定，当前为100，使用`seed=10000`、`sem_policy`、`demo_clean`、`unseen`和`ckpt_setting=none`。
4. 保存训练和评估配置、Git提交、原始日志、`_result.txt`与视频。统计用完成日志中的成功数和有效Episode数，CSV汇总输入示例见`templates/evaluation_results_template.csv`。

```bash
cd "$PREP"
CHECKPOINT="$RUN_DIR/train/checkpoints/checkpoint_1/model.safetensors"
EVAL_CONFIG="$RUN_DIR/staged/train_config.py"
python3 scripts/make_eval_config.py --task place_empty_cup \
  --checkpoint "$CHECKPOINT" --config-file "$EVAL_CONFIG" \
  --align-projection-dtype \
  --episodes 3 --expert-data-num 10 --out "$RUN_DIR/staged/sem_policy"
```

部署后可以从本包运行3个有效Episode的缩量评估，并用相同的Episode数统计。日志存放在此次冒烟运行的独立目录`RUN_DIR`。

```bash
cd "$PREP"
set -o pipefail
python -u scripts/run_smoke_eval.py --runtime "$ROBOTWIN" --task place_empty_cup \
  --episodes 3 --expert-data-num 10 --config "$RUN_DIR/staged/sem_policy/deploy_policy.yml" \
  2>&1 | tee "$RUN_DIR/phase6-eval.log"
python3 scripts/summarize_eval.py --log "$RUN_DIR/phase6-eval.log" --task place_empty_cup \
  --expected-episodes 3 --output "$RUN_DIR/eval_smoke_summary.csv"
```

正式评估用`make_eval_config.py --episodes 100`生成启动器，从已部署的`RoboTwin/policy/sem_policy/`运行`bash eval.sh`，将完整标准输出保留到`eval.log`。用`summarize_eval.py --log --expected-episodes 100`核对100条连续计数和结果保存标记。用`--input`可读取核对后的CSV。

验收用`--episode-output`导出每个有效回合的编号、场景种子和成败。场景种子来自评估日志中的`current seed`，评估启动参数仍为`seed=10000`。评估进行中或手动停止后，可用`--allow-incomplete`导出已完成的回合，并在汇总中标明状态和计划回合数。正式成绩以指定回合数完成后的汇总为准。

```bash
python3 scripts/summarize_eval.py --log "$RUN_DIR/eval.log" --task adjust_bottle \
  --expected-episodes 100 --episode-output "$RUN_DIR/eval_episodes.csv"
```

## C7正式实验与补充实验

在完成C6的同一环境中，每条命令使用新的输出目录。保留`--dry-run`可先核对任务和训练计划，移除后才启动采集、训练和评估。每项使用100条示范、Batch 2和4个DataLoader工作进程。

```bash
cd "$PREP"
python -u scripts/run_formal_experiments.py --base "$CLOUD_BASE" \
  --output "$CLOUD_BASE/runs/reproduce-100k" --max-step 100000 --batch-size 2 \
  --task place_empty_cup --task adjust_bottle --task beat_block_hammer \
  --pretrained "$PRETRAINED" --bert "$BERT_CHECKPOINT" --dry-run
python -u scripts/run_formal_experiments.py --base "$CLOUD_BASE" \
  --output "$CLOUD_BASE/runs/reproduce-50k" --max-step 50000 --batch-size 2 \
  --task place_shoe --task place_container_plate --task click_bell \
  --pretrained "$PRETRAINED" --bert "$BERT_CHECKPOINT" --dry-run
```

串行入口每项从协议初始种子评估100回合。任务目录保存Checkpoint、部署配置、训练与评估日志、`_result.txt`和视频，输出根目录的`results.csv`汇总各任务。正式训练数据由采集器重新生成。原始示范、完整训练日志和云端环境全量清单保存在原数据盘。

### 历史并行调度与续评

本次云端运行采用[并行调度脚本](../scripts/c7_parallel)，最多同时运行3项独立实验。每项使用自己的RoboTwin运行副本，并独立保存训练与评估产物。调度状态记录在数据盘`runs/c7-parallel-control/queue.json`。

`schedule.py --preflight`校验运行副本和权重。`--adopt`用于本次从串行入口交接首项训练，需要原入口及其训练和监控进程仍在运行，同时两个后续任务的工作进程已启动。交接会终止原串行入口进程，由并行调度继续跟踪其训练子进程。`--check-resume`可先校验续接快照中的进程和排队任务。

`schedule.py --resume`可从云端控制目录里的交接快照接管正在运行的训练。快照记录训练PID、显存监控PID、开始时间和待运行任务。接管后的评估按当前项目配置执行。

已完成15回合的`adjust_bottle`和`beat_block_hammer`各续评85回合。续评沿用各自的Checkpoint、评估配置和指令候选数，从原日志最后一个有效场景种子的下一值开始。启动前在已加载云端环境的项目检出目录执行`python scripts/c7_parallel/extend_eval.py --check adjust_bottle beat_block_hammer`。通过后去掉`--check`运行。每项`eval_to_100/`中的`completion.json`和`eval_episodes.csv`汇总两段评估的100个回合，逐回合CSV包含原视频路径。

`place_empty_cup`先记录94个有效回合，再从候选种子`1000100110`开始续评6回合。两段的指令候选数均为100。历史分段设置和场景种子见[评估摘要](../artifacts/sem-tiny/c7-formal/place_empty_cup/eval_100/summary.json)与[逐回合记录](../artifacts/sem-tiny/c7-formal/place_empty_cup/eval_100/eval_episodes.csv)。

### 评估产物自动发布

在能SSH登录云端且有GitHub写权限的本机运行。将`CLOUD_SSH`设为已有的SSH主机别名，可重复传入`--task`监控指定任务，默认监控项目配置中的全部任务。

```bash
python3 scripts/c7_parallel/publish.py --cloud "$CLOUD_SSH" --check
python3 scripts/c7_parallel/publish.py --cloud "$CLOUD_SSH" --watch --task place_shoe
```

监控按配置的评估回合数识别任务完成，核对训练结束记录、评估逐回合数据和Checkpoint路径。每个任务单独发布到`origin/main`，归档包含评估摘要、逐回合CSV、可用的评估视频、权重和模型配置。权重使用Git LFS，传输后校验SHA-256。短评估完成后继续等待正式回合数，SSH或Git推送失败时下轮重试，所选任务全部发布后退出。需要提前备份已训练完成的权重时，使用`--weights-only`指定任务。本机后台服务`sem-c7-publish.service`的运行日志可用`journalctl --user -u sem-c7-publish.service`查看。

GitHub验收产物保留最终权重、模型与处理器配置、实际执行的训练和评估配置、结果汇总、逐回合CSV及评估视频。15回合的评估上传全部15段视频，视频编号与逐回合CSV对应。回合较多的评估保留代表视频。完整训练日志、原始视频和可续训状态在云端归档。保存本次运行的工程和上游提交号，便于从同一版本重新生成配置。`staged/`中的实测配置保留原运行路径，复现时用本节生成器写入本地路径。
