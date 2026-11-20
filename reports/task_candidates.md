# 首批5个RoboTwin任务候选

在RoboTwin提交`e71140e9734e69686daa420a9be8b75a20ff4587`执行`python3 scripts/discover_tasks.py --workspace . --list`，发现50个任务模块。下列五项均有同名任务类、专家轨迹、成功判据、seen/unseen指令模板和评估步长，均对应上游SEM结果表中的任务类别。待确认后写入`configs/project.json`，首轮按顺序从`place_empty_cup`开始，每项独立训练。

| 顺序 | 源码任务 | 专家动作与成功判据 | 评估步长 |
|---|---|---|---:|
| 1 | `place_empty_cup` | 单臂抓取空杯并放到杯垫，按杯与垫的功能点间距和双夹爪打开判定。RoboTwin `envs/place_empty_cup.py:54–98` | 500 |
| 2 | `adjust_bottle` | 选择对应机械臂挪正瓶子，按功能点所在侧和高度判定。RoboTwin `envs/adjust_bottle.py:36–67` | 400 |
| 3 | `beat_block_hammer` | 抓锤并接触方块，按锤与方块功能点水平对齐和接触判定。RoboTwin `envs/beat_block_hammer.py:56–87` | 400 |
| 4 | `handover_block` | 两臂交接后放下方块，按放置误差和右夹爪打开判定。RoboTwin `envs/handover_block.py:49–116` | 800 |
| 5 | `place_container_plate` | 单臂将容器放到盘上，按容器位置和双夹爪打开判定。RoboTwin `envs/place_container_plate.py:55–98` | 400 |

步长见RoboTwin `task_config/_eval_step_limit.yml:1–28`，指令见`description/task_instruction/<任务>.json:5,57`，SEM任务类别见RoboOrchardLab `projects/sem/robotwin/README.md:268–275`。专家成功率及可采集种子需要用云端仿真验证。
