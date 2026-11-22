# 训练资源预算

官方SEM默认`max_step=100000`、`batch_size=8`（以实际代码为准）。单任务训练耗时：

`训练小时 = 单任务Step数 ÷ 1000 × 每1000Step耗时(分钟) ÷ 60`

五项正式实验包含3项100000步和2项50000步，补充实验另计50000步。按训练步数组合分别估算，再考虑环境调试、数据采集、评估和磁盘费用。[实际训练步数](../artifacts/sem-tiny/c7-formal/evaluation_100.csv)

先采集10条并打包LMDB，分别用总字节数除以10计算单条体积。预算示例使用C5训练后段实测的0.28秒/步，折合每1000步约4.67分钟，费率使用原实验的1.98元/小时。并行执行时按实例实际运行时间核对账单。[短训练实测](../reports/cloud_preflight.md#c5打包与短训练)

```bash
python3 scripts/estimate_budget.py --tasks 3 --steps 100000 --minutes-per-1000 4.67 --hourly-rate 1.98
python3 scripts/estimate_budget.py --tasks 2 --steps 50000 --minutes-per-1000 4.67 --hourly-rate 1.98
```

初期数据盘**200GB总容量**是成本优先的规划值。根据10条样本尺寸与固定资产占用，重新核算保留5个任务的原始RGB-D、LMDB和视频所需的容量。

若已在云端完成10条原始HDF5示范和对应LMDB，使用真实目录大小估算：

```bash
python3 scripts/estimate_storage.py \
  --sample-count 10 \
  --sample-raw-dir "${SAMPLE_RAW_DIR:?请设置10条原始示范目录}" \
  --sample-lmdb-dir "${SAMPLE_LMDB_DIR:?请设置对应LMDB目录}" \
  --tasks 5 --episodes-per-task 100 --extra-gib 30
```

注意采样数据目录应仅包含这10条对应的文件，不要混入其他任务或重复副本。
