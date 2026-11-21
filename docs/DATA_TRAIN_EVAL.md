# 采集、SEM训练与评估

以下命令用于完成云端环境验收后的单任务闭环。路径与参数证据见[固定源码审计](../reports/code_audit.md)。示例中的`PREP`、`ROBOTWIN`、`SEM`、`RUN_DIR`均为云端实测的绝对路径，分别指本包根目录、两个运行副本和本次数据盘目录。暂存工具从本包`src/`中的干净锁定源码读取。

## 采集与数据检查

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
```

## 评估与统计

1. 在远程RoboTwin运行环境按既定要求安装RoboOrchardLab，部署审查过的`sem_policy`到`policy/sem_policy/`，保持`demo_clean`的Depth开启。确认`CHECKPOINT`指向实际训练产物，`EVAL_CONFIG`指向可加载的SEM Python配置。
2. 用刚实际参与训练的示范数量生成部署文件。核对YAML、路径和评估任务后应用到运行副本的策略目录。
3. 用`run_smoke_eval.py`验证模型加载、观测输入和14维双臂动作。该入口校验运行副本和锁定源码中的评估脚本一致，在内存中替换Episode数，并检查策略动作形状和有限值。C7后续任务评估15个有效Episode，使用`seed=10000`、`sem_policy`、`demo_clean`、`unseen`和`ckpt_setting=none`。
4. 保存训练和评估配置、Git提交、原始日志、`_result.txt`与视频。统计用完成日志中的成功数和有效Episode数，CSV汇总输入示例见`templates/evaluation_results_template.csv`。

```bash
cd "$PREP"
python3 scripts/make_eval_config.py --task place_empty_cup \
  --checkpoint "$CHECKPOINT" --config-file "$EVAL_CONFIG" \
  --align-projection-dtype \
  --expert-data-num 10 --out "$RUN_DIR/staged/sem_policy"
python3 scripts/summarize_eval.py --log "$RUN_DIR/eval.log" --task place_empty_cup \
  --output "$RUN_DIR/eval_summary.csv"
```

部署后可以从本包运行3个有效Episode的缩量评估，并用相同的Episode数统计。日志存放在此次冒烟运行的独立目录`RUN_DIR`。

```bash
cd "$PREP"
set -o pipefail
python -u scripts/run_smoke_eval.py --runtime "$ROBOTWIN" --task place_empty_cup \
  --episodes 3 --expert-data-num 10 --config "$RUN_DIR/staged/sem_policy/deploy_policy.yml" \
  2>&1 | tee "$RUN_DIR/eval_smoke.log"
python3 scripts/summarize_eval.py --log "$RUN_DIR/eval_smoke.log" --task place_empty_cup \
  --expected-episodes 3 --output "$RUN_DIR/eval_smoke_summary.csv"
```

正式评估用`make_eval_config.py --episodes 15`生成启动器，从已部署的`RoboTwin/policy/sem_policy/`运行`bash eval.sh`，将完整标准输出保留到`eval.log`。用`summarize_eval.py --log --expected-episodes 15`核对15条连续计数和结果保存标记。用`--input`可读取核对后的CSV。

验收用`--episode-output`导出每个有效回合的编号、场景种子和成败。场景种子来自评估日志中的`current seed`，评估启动参数仍为`seed=10000`。评估进行中或手动停止后，可用`--allow-incomplete`导出已完成的回合，并在汇总中标明状态和计划回合数。正式成绩以指定回合数完成后的汇总为准。

```bash
python3 scripts/summarize_eval.py --log "$RUN_DIR/eval.log" --task adjust_bottle \
  --expected-episodes 15 --episode-output "$RUN_DIR/eval_episodes.csv"
```

## C7五项正式实验

在已验收的云端环境中，`CLOUD_BASE`指向数据盘工程目录。`OUTPUT`是数据盘下新建的结果目录。`BATCH_SIZE`按C5实测选择。新启动的训练默认读取`configs/project.json`中的`train_steps_reference=50000`，串行入口支持用`--max-step`显式指定。

```bash
cd "$PREP"
source "$CLOUD_BASE/runtime/env.sh"
python -u scripts/run_formal_experiments.py --base "$CLOUD_BASE" --output "$OUTPUT" \
  --batch-size "$BATCH_SIZE" \
  --pretrained "$PRETRAINED" --bert "$BERT_CHECKPOINT"
```

入口按`configs/project.json`的顺序采集、打包、训练和评估。每项使用100条成功示范独立训练，评估回合数读取`eval_episodes_target`。任务目录保存Checkpoint、部署配置、训练和评估日志、`_result.txt`与视频。根目录的`results.csv`记录各任务实际完成的训练步数。并行调度用每项实验保存的训练配置和完成日志核对已启动任务。

本次云端运行采用[并行调度脚本](../scripts/c7_parallel)，最多同时运行3项独立实验。每项使用自己的RoboTwin运行副本，并独立保存训练与评估产物。调度状态记录在数据盘`runs/c7-parallel-control/queue.json`。

`schedule.py --preflight`校验运行副本和权重。`--adopt`用于本次从串行入口交接首项训练，需要原入口及其训练和监控进程仍在运行，同时两个后续任务的工作进程已启动。交接会终止原串行入口进程，由并行调度继续跟踪其训练子进程。`--check-resume`可先校验续接快照中的进程和排队任务。

`schedule.py --resume`可从云端控制目录里的交接快照接管正在运行的训练。快照记录训练PID、显存监控PID、开始时间和待运行任务。接管后的评估按当前项目配置执行。

GitHub验收产物保留最终权重、模型与处理器配置、实际执行的训练和评估配置、结果汇总、逐回合CSV及评估视频。15回合的评估上传全部15段视频，视频编号与逐回合CSV对应。回合较多的评估保留代表视频。完整训练日志、原始视频和可续训状态在云端归档。保存本次运行的工程和上游提交号，便于从同一版本重新生成配置。`staged/`中的实测配置保留原运行路径，复现时用本节生成器写入本地路径。
