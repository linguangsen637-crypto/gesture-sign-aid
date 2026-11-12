# SignAid · 美国手语辅助取物

SignAid 面向使用美国手语（ASL）的用户，旨在基于 WLASL 数据集构建限定词汇范围内的手语识别功能，将识别结果映射为取物请求，由 SO-101 机械臂抓取对应物品并送至固定取物盘。

SignAid aims to assist American Sign Language (ASL) users through a limited-vocabulary sign recognition system built using the WLASL dataset. Recognized signs are mapped to item retrieval requests, enabling an SO-101 robotic arm to pick up the requested item and place it in a designated pickup tray.

## 当前可运行内容

已接入固定版本 WLASL 官方仓库，提供词汇查询、子集导出、上游视频脚本工作目录准备、本地视频索引和词汇到取物请求的映射。基础框架提供确认与结果验收状态、模拟机械臂、测试和协作文档。VLM 视频识别、上游识别模型实际推理、真实 SO-101、ACT 执行和图形界面均为待接入模块。

## 快速开始

需要 Python 3.12 和 uv，在 macOS 或 Ubuntu 执行。

```bash
git clone --recurse-submodules https://github.com/linguangsen637-crypto/gesture-sign-aid.git
cd gesture-sign-aid
uv sync --locked

# 已有工作副本获取上游源码与标注
git submodule update --init --recursive

# 查询实际标注和导出子集
uv run signaid wlasl stats --gloss water tissue
uv run signaid wlasl export --gloss water tissue --output data/wlasl/subset.json

# 准备上游下载、预处理脚本及子集标注
uv run signaid wlasl prepare --gloss water tissue --output data/wlasl

# 模拟识别器输出的词汇，接入原有取物流程
uv run signaid demo --gloss water --confirm --delivered

# 模拟识别，流程停在等待确认
uv run signaid demo --intent request_water

# 模拟确认与执行，流程停在等待结果验收
uv run signaid demo --intent request_water --confirm

# 模拟完整交付
uv run signaid demo --intent request_tissue --confirm --delivered

# 不明确的识别结果保持等待
uv run signaid demo --intent unclear

# 运行流程测试
uv run python -m unittest discover -s tests -v
```

每次 demo 命令启动一个独立的内存会话。输出中的 `mode` 为 `simulation`，完整交付示例中的结果也为模拟结果。`--gloss` 接受人工指定的标签，视频到标签的识别模型待接入。

WLASL 固定版本包含 2,000 个 ASL 词汇、21,083 条视频标注。其中 `water` 有 18 条，`tissue` 有 8 条，实际视频可用性需下载后检查。视频准备、可选依赖、FFmpeg 和上游识别方法见 [WLASL 接入指南](docs/wlasl.md)。

## 模块与分工

| 目录 | 工作 |
| --- | --- |
| `src/gesture_aid/perception/` | 连续画面输入、ASL 识别、WLASL 词汇映射 |
| `src/gesture_aid/datasets/` | WLASL 标注、子集和视频索引 |
| `third_party/WLASL/` | 固定提交的上游仓库子模块 |
| `src/gesture_aid/workflow/` | 确认、取消、任务状态与请求去重 |
| `src/gesture_aid/robot/` | SO-101、ACT 模型加载、抓放与停止机制 |
| `src/gesture_aid/dashboard/` | 用户交互和操作员界面 |
| `configs/` | 手语词目来源和动作策略配置示例 |
| `docs/` | 架构、数据与模型、评估、任务清单和演示 |

建议按识别、设备、训练、界面与流程、产品与评估分工。队员在任务中认领负责人。

## 第一版范围

- WLASL 的 `water`、`tissue` 两类 ASL 词汇，在取物交互场景中映射为水和纸巾请求。
- 每种物品先训练一个 ACT 策略。
- 识别后确认，机械臂将物品放入固定取物盘并退回。
- 运行结束后独立确认交付结果。
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
