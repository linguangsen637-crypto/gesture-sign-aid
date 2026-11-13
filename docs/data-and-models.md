# 数据与模型

## 存储约定

| 内容 | 位置 |
| --- | --- |
| Mac 机器人示教数据 | `~/.cache/huggingface/lerobot/<repo_id>/` |
| Ubuntu 训练数据 | 在训练机器记录完整路径或 Hugging Face 数据集版本 |
| ACT 模型与恢复状态 | Ubuntu 训练输出目录，逐次记录实际路径 |
| Mac 部署模型 | 本机模型目录，通过个人配置指定 |
| 手语示范及测试片段 | 独立资料目录或获授权的数据集仓库 |

同步 LeRobot 数据集时保留完整 `data/`、`videos/`、`meta/`。部署模型保留权重、配置和归一化参数。恢复训练所需的 checkpoint 状态单独保存。

## pick_cup 训练记录

记录来自公开模型卡、`config.json`、`train_config.json` 和数据集 `meta/info.json`。Hub 最后更新时间为 2026-11-13 14:51（Asia/Macau）。权重不进入 Git。

| 字段 | 值 |
| --- | --- |
| 任务 | `pick_cup`。数据集只有 1 个任务，模型卡中的任务字符串是 `uo` |
| 数据集 ID、版本和有效回合数 | [`axellin/cupfinal`](https://huggingface.co/datasets/axellin/cupfinal)，提交 `555ccf86f422f44ba5a14c89077b8cb9513f92fa`，LeRobot dataset v3.0。49 回合、17690 帧，划分 `train: 0:49` |
| 训练机器与 GPU | 未写入检查点。`output_dir` 为 `/tmp/makermodslab/train`，作业镜像为 `huggingface/lerobot-gpu:latest`，`wandb.enable` 为 false |
| Python、LeRobot、PyTorch 版本与源码提交 | 模型卡写明 LeRobot 0.6.2。Python、PyTorch 和 LeRobot 源码提交未写入该检查点 |
| 相机名称、分辨率、帧率 | 机器人类型 `so_follower`。唯一相机 `top`，640×480，30 FPS，键 `observation.images.top`。策略输入为 CHW `(3, 480, 640)` |
| 标定标识、起始姿态和桌面布局 | 未记录 |
| batch size、步数和其他超参数 | batch size 8，10000 步，AdamW，学习率 `1e-5`，权重衰减 `1e-4`，梯度裁剪 10，seed 1000。`chunk_size` 100，`n_action_steps` 100，`n_obs_steps` 1，ResNet18，`use_vae` true，`kl_weight` 10。保存间隔 1000 步 |
| 模型及训练日志位置 | [`axellin/act_cupfinal_2026-11-13_14-34-08`](https://huggingface.co/axellin/act_cupfinal_2026-11-13_14-34-08)，提交 `3240600b11fa941067649a06e00d03d4d8402145`，Apache-2.0，51,668,614 个 F32 参数。根目录是可加载策略；同仓库另有 `checkpoints/001000` 至 `checkpoints/010000`。未见单独训练日志 |
| 关节顺序 | `shoulder_pan.pos`、`shoulder_lift.pos`、`elbow_flex.pos`、`wrist_flex.pos`、`wrist_roll.pos`、`gripper.pos`。状态和动作都是 6 维 |
| Mac 加载、推理速度和实机结果 | 未测 |

索引与本地配置核对：

```bash
uv run signaid robot show
uv run signaid robot check --config /path/to/config.json
uv run signaid robot command --port /dev/tty.usbmodem --camera-index 0 --device cpu
```

这三条命令都不连接电机。`command` 打印 `--duration=60` 的 rollout 参数，相机名是 `top`。在已验证的 LeRobot 0.6.2 环境里完成现场安全检查后再执行。`CUP_POLICY_PATH` 或 `--policy-path` 可改成本地目录。

## 下一次训练记录

复制下表，填写真实结果后提交文档更新。

| 字段 | 值 |
| --- | --- |
| 任务 | 待填写 |
| 数据集 ID、版本和有效回合数 | 待填写 |
| 训练机器与 GPU | 待填写 |
| Python、LeRobot、PyTorch 版本与源码提交 | 待填写 |
| 相机名称、分辨率、帧率 | 待填写 |
| 标定标识、起始姿态和桌面布局 | 待填写 |
| batch size、步数和其他超参数 | 待填写 |
| 模型及训练日志位置 | 待填写 |
| Mac 加载、推理速度和实机结果 | 待填写 |

Mac 与 Ubuntu 的路径分别填写。GitHub 记录索引和配置示例，视频、数据集和权重由外部存储管理。

## WLASL 感知数据

上游源码与标注位于 `third_party/WLASL`。生成的子集、视频和索引保存于 `data/wlasl`，通过数据同步或获授权的数据存储共享。手语视频与机器人示教数据分别记录，详情见 [WLASL 指南](wlasl.md)。
