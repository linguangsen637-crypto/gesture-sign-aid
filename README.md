# SignAid · 美国手语辅助取物

SignAid 面向使用美国手语（ASL）的用户，旨在基于 WLASL 数据集构建限定词汇范围内的手语识别功能，将识别结果映射为取物请求，由 SO-101 机械臂抓取对应物品并送至固定取物盘。

SignAid aims to assist American Sign Language (ASL) users through a limited-vocabulary sign recognition system built using the WLASL dataset. Recognized signs are mapped to item retrieval requests, enabling an SO-101 robotic arm to pick up the requested item and place it in a designated pickup tray.

## 当前可运行内容

已接入固定版本 WLASL 官方仓库，提供词汇查询、子集导出、上游视频脚本工作目录准备、本地视频索引和词汇到取物请求的映射。基础框架提供自动执行与结果验收状态、模拟机械臂、测试和协作文档。摄像头页面支持本机 MediaPipe 关键点与 CUP 模板匹配，显示骨架、匹配距离和单次识别事件。实际 ASL 动作识别效果待现场评估。`pick_cup` 已索引 LeRobot ACT 策略 [`axellin/act_cupfinal_2026-11-13_14-34-08`](https://huggingface.co/axellin/act_cupfinal_2026-11-13_14-34-08)。`signaid robot` 只核对该策略并打印有限时长的 rollout 命令；电机仍由已验证的 LeRobot 环境在现场检查后启动。

## 摄像头手语识别

默认使用 MediaPipe 双手＋肩膀关键点与 DTW CUP 模板匹配。摄像头只产生本地识别事件，不连接机械臂。旧 I3D 后端保留用于对照实验。

```bash
uv sync --locked --extra landmarks
uv run --extra landmarks signaid templates setup
uv run --extra landmarks signaid camera
```

打开 `http://localhost:8765`，点击“开启摄像头”。页面显示双手骨架和肩膀位置，连续匹配完整动作。一次 CUP 通过两次连续匹配后只产生一个事件；双手移出画面至少 0.8 秒、距上次触发至少 1.5 秒后重新允许识别。停止、切换到后台或关闭页面都会释放摄像头。

首次使用先准备模板。可导入可用的 WLASL CUP 视频和其他词汇负样本：

```bash
uv run --extra landmarks signaid templates import-wlasl --gloss cup --label cup --download
uv run --extra landmarks signaid templates import-wlasl --gloss book --label negative --download
```

`--download` 只获取标注中可直接下载的完整单词 MP4；旧链接可能失效。YouTube 合集和 SWF 需按 [WLASL 指南](docs/wlasl.md) 另行准备。原 train 划分加入模板，val/test 留作测试，不参与匹配。模型与关键点模板分别保存在 Git 忽略的 `models/mediapipe/` 和 `data/cup-templates/`。

也可在页面选择 CUP 或干扰动作，点击“倒计时并录制 3 秒”。只保存关键点，不保存摄像头视频。务必补充现场挥手、挠头、拿杯等负样本，并在其他录制场次选择“独立测试样本”。没有正负模板、双手或肩膀检测不足、静止动作、模糊匹配时均不触发。

```bash
uv run --extra landmarks signaid templates stats
uv run --extra landmarks signaid templates evaluate
# 阈值是 DTW 距离，越低越严格；初始 0.4 未经现场校准
uv run --extra landmarks signaid camera --distance-threshold 0.4
```

当前是小词表研究原型，距离不等于识别概率。没有独立测试样本时，评估输出为空值，不报告准确率。模板回放只能用于回归检查。完整说明见 [关键点与模板匹配](docs/cup-landmarks.md)。

旧 I3D 实验入口：`uv run --extra vision signaid camera --backend i3d`，另需 `models/wlasl-i3d/model.pt` 和 `labels.txt`，来源见 `THIRD_PARTY_NOTICES.md`。

## 快速开始

需要 Python 3.12 和 uv，在 macOS 或 Ubuntu 执行。

```bash
git clone --recurse-submodules https://github.com/linguangsen637-crypto/gesture-sign-aid.git
cd gesture-sign-aid
uv sync --locked

# 已有工作副本获取上游源码与标注
git submodule update --init --recursive

# 查询实际标注和导出子集
uv run signaid wlasl stats --gloss cup
uv run signaid wlasl export --gloss cup --output data/wlasl/subset.json

# 准备上游下载、预处理脚本及子集标注
uv run signaid wlasl prepare --gloss cup --output data/wlasl

# 模拟识别器输出的词汇，接入原有取物流程
uv run signaid demo --gloss cup --delivered

# 模拟识别 cup 后自动执行取杯，流程停在等待结果报告
uv run signaid demo --gloss cup

# 模拟完整交付
uv run signaid demo --intent request_cup --delivered

# 查看已索引的 pick_cup 策略，并打印有限时长的 rollout 命令
uv run signaid robot show
uv run signaid robot command --port /dev/tty.usbmodem --camera-index 0

# 不明确的识别结果保持等待
uv run signaid demo --intent unclear

# 运行流程测试
uv run python -m unittest discover -s tests -v
```

每次 demo 命令启动一个独立的内存会话。输出中的 `mode` 为 `simulation`，完整交付示例中的结果也为模拟结果。`--gloss` 接受人工指定的标签；真实摄像头识别使用独立的 `camera` 命令。`robot show` 和 `robot command` 只读取技能索引并打印参数，端口和相机索引需要换成现场设备。

WLASL 固定版本包含 2,000 个 ASL 词汇、21,083 条视频标注。其中 `cup` 有 13 条，`water` 有 18 条，`tissue` 有 8 条，实际视频可用性需下载后检查。视频准备、可选依赖、FFmpeg 和上游识别方法见 [WLASL 接入指南](docs/wlasl.md)。

## 模块与分工

| 目录 | 工作 |
| --- | --- |
| `src/gesture_aid/perception/` | 连续画面输入、ASL 识别、WLASL 词汇映射 |
| `src/gesture_aid/datasets/` | WLASL 标注、子集和视频索引 |
| `third_party/WLASL/` | 固定提交的上游仓库子模块 |
| `src/gesture_aid/workflow/` | 自动执行、任务状态与请求去重 |
| `src/gesture_aid/robot/` | SO-101 技能索引、ACT 策略校验和 rollout 命令；电机生命周期留在 LeRobot 环境 |
| `src/gesture_aid/dashboard/` | 用户交互和操作员界面 |
| `configs/` | 手语词目来源和动作策略配置示例 |
| `docs/` | 架构、数据与模型、评估、任务清单和演示 |

建议按识别、设备、训练、界面与流程、产品与评估分工。队员在任务中认领负责人。

## 第一版范围

- 第一版采用 WLASL 的 `cup`，自动抓取打印杯并送至固定取物盘。现有 `water`、`tissue` 映射供后续扩展。
- `pick_cup` 使用已发布的 ACT 策略 `axellin/act_cupfinal_2026-11-13_14-34-08`。Mac 推理速度和实机交付仍待记录。
- 识别器提交有效请求后立即执行，机械臂将杯子放入固定取物盘并退回。
- 运行结束后由独立结果检测报告交付状态，再由调用方重置流程；结果检测仍待接入。
- 对其他表达和不完整动作输出 `unclear`。

## 协作入口

- [开发协作](CONTRIBUTING.md)
- [模块接口与状态](docs/architecture.md)
- [手语资料与核验](docs/sign-language-scope.md)
- [WLASL 接入指南](docs/wlasl.md)
- [上游来源与协议](THIRD_PARTY_NOTICES.md)
- [数据与模型](docs/data-and-models.md)
- [首批任务与里程碑](docs/backlog.md)
- [评估记录](docs/evaluation.md)
- [展示材料](docs/demo.md)

## 开发环境

本项目的 `.venv` 用于共享业务代码与数据工具。`uv sync --locked --extra wlasl` 安装上游视频脚本的可选 Python 依赖，FFmpeg 由系统或独立媒体工具环境提供。真实机器人适配需要在已验证的 MakerMods Lab / LeRobot 环境中完成并记录版本。词汇映射读取 `configs/sign_lexicon.json`，机器人模型路径通过配置示例约定，当前模拟技能使用内置映射。

当前已经验证的设备环境为 Apple M5、Python 3.12.16、MakerMods Lab 0.1.0、LeRobot 0.6.2、PyTorch 2.11.0。Ubuntu GPU 环境和真实设备流程待联调。

## 资料

- [WLASL](https://github.com/dxli94/WLASL)
- [LeRobot](https://github.com/huggingface/lerobot)
- [MakerMods Lab](https://github.com/makermods-robotics/makermodslab)
- [ACT](https://huggingface.co/docs/lerobot/act)
