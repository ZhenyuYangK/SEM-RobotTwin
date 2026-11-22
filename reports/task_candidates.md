# RoboTwin训练任务与源码依据

在RoboTwin提交`e71140e9734e69686daa420a9be8b75a20ff4587`执行`python3 scripts/discover_tasks.py --workspace . --list`，发现50个任务模块。下列五项均有同名任务类、专家轨迹、成功判据、seen/unseen指令模板和评估步长，均对应上游SEM结果表中的任务类别。任务范围以`configs/project.json`为准，每项独立训练。

| 顺序 | 源码任务 | 专家动作与成功判据 | 评估步长 |
|---|---|---|---:|
| 1 | `place_empty_cup` | 单臂抓取空杯并放到杯垫，按杯与垫的功能点间距和双夹爪打开判定。RoboTwin `envs/place_empty_cup.py:54–97` | 500 |
| 2 | `adjust_bottle` | 选择对应机械臂挪正瓶子，按功能点所在侧和高度判定。RoboTwin `envs/adjust_bottle.py:36–67` | 400 |
| 3 | `beat_block_hammer` | 抓锤并接触方块，按锤与方块功能点水平对齐和接触判定。RoboTwin `envs/beat_block_hammer.py:56–87` | 400 |
| 4 | `place_shoe` | 按鞋的初始位置选择机械臂，将鞋放到垫上。按鞋的位置、朝向和双夹爪打开判定。RoboTwin `envs/place_shoe.py:62–100` | 500 |
| 5 | `place_container_plate` | 单臂将容器放到盘上，按容器位置和双夹爪打开判定。RoboTwin `envs/place_container_plate.py:55–98` | 400 |

补充任务`click_bell`的专家动作为按铃，按夹爪与铃顶接触位置判定成功，评估步长为400。源码见RoboTwin的`envs/click_bell.py:38–80`。[补充实验记录](cloud_preflight.md#c7正式实验进展)

步长见RoboTwin的`task_config/_eval_step_limit.yml`，指令见`description/task_instruction/<任务>.json`，SEM任务类别见RoboOrchardLab的`projects/sem/robotwin/README.md:268–275`。`place_shoe`的10条`unseen`模板均要求将鞋放到垫上。已评估的场景种子在各任务逐回合CSV中。[100回合汇总](../artifacts/sem-tiny/c7-formal/evaluation_100.csv) · [RoboTwin任务说明](https://robotwin-platform.github.io/doc/tasks/place_shoe.html)
