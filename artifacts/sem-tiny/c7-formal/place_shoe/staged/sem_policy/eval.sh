#!/usr/bin/env bash
# 固定版RoboTwin单任务评估入口。
set -euo pipefail
policy_name=sem_policy
task_name="place_shoe"
task_config=demo_clean
ckpt_setting=none
expert_data_num="100"
episodes=100
seed=10000
gpu_id=0
export CUDA_VISIBLE_DEVICES="${gpu_id}"
export HYDRA_FULL_ERROR=1
cd "$(dirname "$0")/../.."
[[ -f script/eval_policy.py && -f "policy/${policy_name}/deploy_policy.yml" ]] || {
  echo "Deploy this launcher under RoboTwin/policy/sem_policy before starting." >&2
  exit 1
}
export PYTHONWARNINGS=ignore::UserWarning
if (( episodes < 100 )); then
  exec python -u /root/SEM-RoboTwin-git/scripts/run_smoke_eval.py --workspace /root/SEM-RoboTwin-git --runtime . \
    --task "${task_name}" --episodes "${episodes}" --expert-data-num "${expert_data_num}" \
    --config "policy/${policy_name}/deploy_policy.yml"
fi

exec python -u script/eval_policy.py \
  --config policy/${policy_name}/deploy_policy.yml --overrides \
  --task_name "${task_name}" --task_config "${task_config}" \
  --ckpt_setting "${ckpt_setting}" --expert_data_num "${expert_data_num}" \
  --seed "${seed}" --policy_name "${policy_name}"
