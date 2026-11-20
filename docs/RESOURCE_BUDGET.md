# 资源预算方法（规划情景，不是实测）

官方SEM默认`max_step=100000`、`batch_size=8`（以实际代码为准）。单任务训练耗时：

`训练小时 = 单任务Step数 ÷ 1000 × 每1000Step耗时(分钟) ÷ 60`

后续新训练以50000步为预算参考。训练预算逐项估算后汇总。总费用还需加环境调试、数据采集、评估耗时，并考虑磁盘费用。

**测量要求**：先采集10条、转换LMDB，实测总字节数/10；再测试1000Step耗时及10次评估耗时。不要使用演示数值替代实测。

```bash
python3 scripts/estimate_budget.py --tasks 5 --steps 50000 --minutes-per-1000 20 --hourly-rate 1.98
```

初期数据盘**200GB总容量**是成本优先的规划值。根据10条样本尺寸与固定资产占用，重新核算保留5个任务的原始RGB-D、LMDB和视频所需的容量。

若已在云端完成10条原始HDF5示范和对应LMDB，使用真实目录大小估算：

```bash
python3 scripts/estimate_storage.py \
  --sample-count 10 \
  --sample-raw-dir <10条原始数据目录> \
  --sample-lmdb-dir <对应LMDB目录> \
  --tasks 5 --episodes-per-task 100 --extra-gib 30
```

注意采样数据目录应仅包含这10条对应的文件，不要混入其他任务或重复副本。
