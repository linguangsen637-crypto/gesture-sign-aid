# SignAid · 美国手语辅助取物

SignAid 面向使用美国手语（ASL）的用户，旨在基于 WLASL 数据集构建限定词汇范围内的手语识别功能，将识别结果映射为取物请求，由 SO-101 机械臂抓取对应物品并送至固定取物盘。

SignAid aims to assist American Sign Language (ASL) users through a limited-vocabulary sign recognition system built using the WLASL dataset. Recognized signs are mapped to item retrieval requests, enabling an SO-101 robotic arm to pick up the requested item and place it in a designated pickup tray.

## 当前可运行内容

已接入固定版本 WLASL 官方仓库，提供词汇查询、子集导出、上游视频脚本工作目录准备、本地视频索引和词汇到取物请求的映射。基础框架提供自动执行与结果验收状态、模拟机械臂、测试和协作文档。摄像头页面支持本机 WLASL2000 I3D 推理，显示预测词、分数和对应需求。实际 ASL 动作识别效果待现场评估，真实 SO-101 与 ACT 执行仍待接入。

## 摄像头手语识别

当前 Mac 的权重和标签已放在 `models/wlasl-i3d/`。在项目根目录执行。

```bash
uv sync --extra vision --extra wlasl
uv run --extra vision --extra wlasl signaid camera
```

打开 `http://localhost:8765`，点击“开始识别”并允许摄像头访问。页面优先选择 Mac 内置摄像头，也可以停止后从列表选择其他相机。让脸部和双手保持在画面框内，每轮采集约 2.6 秒完整动作，再显示模型前五项预测。点击“停止”释放摄像头，切换到后台或关闭页面也会释放。

模型使用 CPU 在本机推理，浏览器将 JPEG 片段发送到本机服务，在内存中处理。初始分数阈值为 0.5，可用 `--threshold` 调整；该值需通过实际正负样本校准。当前采用固定长度片段，动作跨越片段边界可能影响识别，自动动作分段待实现。摄像头页面展示识别结果与需求，机械臂连接状态为待接入。

其他协作者需要从 [模型镜像文件列表](https://huggingface.co/spaces/cedssama/I3D_Sign_Language_Classification/tree/38f30b7a60a9e7336167b1c1eed5b3923a11da9d) 下载 `weights/asl2000/FINAL_nslt_2000_iters=5104_top1=32.48_top5=57.31_top10=66.31.pt` 和 `wlasl_class_list.txt`，分别保存为 `models/wlasl-i3d/model.pt` 和 `models/wlasl-i3d/labels.txt`。模型文件由 Git 忽略，来源及校验值见 `THIRD_PARTY_NOTICES.md`。

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

# 不明确的识别结果保持等待
uv run signaid demo --intent unclear

# 运行流程测试
uv run python -m unittest discover -s tests -v
```

每次 demo 命令启动一个独立的内存会话。输出中的 `mode` 为 `simulation`，完整交付示例中的结果也为模拟结果。`--gloss` 接受人工指定的标签，视频到标签的识别模型待接入。

WLASL 固定版本包含 2,000 个 ASL 词汇、21,083 条视频标注。其中 `cup` 有 13 条，`water` 有 18 条，`tissue` 有 8 条，实际视频可用性需下载后检查。视频准备、可选依赖、FFmpeg 和上游识别方法见 [WLASL 接入指南](docs/wlasl.md)。

## 模块与分工

| 目录 | 工作 |
| --- | --- |
| `src/gesture_aid/perception/` | 连续画面输入、ASL 识别、WLASL 词汇映射 |
| `src/gesture_aid/datasets/` | WLASL 标注、子集和视频索引 |
| `third_party/WLASL/` | 固定提交的上游仓库子模块 |
| `src/gesture_aid/workflow/` | 自动执行、任务状态与请求去重 |
| `src/gesture_aid/robot/` | SO-101、ACT 模型加载、抓放与停止机制 |
| `src/gesture_aid/dashboard/` | 用户交互和操作员界面 |
| `configs/` | 手语词目来源和动作策略配置示例 |
| `docs/` | 架构、数据与模型、评估、任务清单和演示 |

建议按识别、设备、训练、界面与流程、产品与评估分工。队员在任务中认领负责人。

## 第一版范围

- 第一版采用 WLASL 的 `cup`，自动抓取打印杯并送至固定取物盘。现有 `water`、`tissue` 映射供后续扩展。
- 先训练 `pick_cup` ACT 策略。
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
