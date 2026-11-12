# SignAid · 国家通用手语辅助取物

SignAid 面向使用国家通用手语表达需求的用户，将限定范围内的手语表达转换为取物请求，由 SO-101 机械臂将物品送至固定取物盘。

SignAid helps users who communicate in Standard Chinese Sign Language by interpreting a limited set of signs as item retrieval requests. An SO-101 robotic arm then picks up the requested item and places it in a designated pickup tray.

## 当前可运行内容

基础框架提供命令行模拟流程、共享请求类型、确认与结果验收状态、模拟机械臂、测试和协作文档。VLM、摄像头、真实 SO-101、ACT 推理和图形界面均为待接入模块。两项候选手语表达的规范动作仍待资料核验。

## 快速开始

需要 Python 3.12 和 uv，在 macOS 或 Ubuntu 执行。

```bash
git clone https://github.com/linguangsen637-crypto/gesture-sign-aid.git
cd gesture-sign-aid
uv sync --locked

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

每次命令启动一个独立的内存会话。输出中的 `mode` 为 `simulation`，完整交付示例中的结果也为模拟结果。

## 模块与分工

| 目录 | 工作 |
| --- | --- |
| `src/gesture_aid/perception/` | 连续画面输入、VLM 接入、国家通用手语识别 |
| `src/gesture_aid/workflow/` | 确认、取消、任务状态与请求去重 |
| `src/gesture_aid/robot/` | SO-101、ACT 模型加载、抓放与停止机制 |
| `src/gesture_aid/dashboard/` | 用户交互和操作员界面 |
| `configs/` | 手语词目来源和动作策略配置示例 |
| `docs/` | 架构、数据与模型、评估、任务清单和演示 |

建议按识别、设备、训练、界面与流程、产品与评估分工。队员在任务中认领负责人。

## 第一版范围

- 两项经核验的国家通用手语表达，分别对应水和纸巾相关请求。
- 每种物品先训练一个 ACT 策略。
- 识别后确认，机械臂将物品放入固定取物盘并退回。
- 运行结束后独立确认交付结果。
- 对其他表达和不完整动作输出 `unclear`。

## 协作入口

- [开发协作](CONTRIBUTING.md)
- [模块接口与状态](docs/architecture.md)
- [手语资料与核验](docs/sign-language-scope.md)
- [数据与模型](docs/data-and-models.md)
- [首批任务与里程碑](docs/backlog.md)
- [评估记录](docs/evaluation.md)
- [展示材料](docs/demo.md)

## 开发环境

本项目的 `.venv` 用于共享业务代码与模拟流程。真实机器人适配需要在已验证的 MakerMods Lab / LeRobot 环境中完成并记录版本。配置通过 `configs/skills.example.json` 和 `.env.example` 约定，当前模拟程序使用内置映射。真实接口负责人接入时应实现配置读取和校验。

当前已经验证的设备环境为 Apple M5、Python 3.12.16、MakerMods Lab 0.1.0、LeRobot 0.6.2、PyTorch 2.11.0。Ubuntu GPU 环境和真实设备流程待联调。

## 资料

- [国家通用手语常用词表说明](https://www.moe.gov.cn/jyb_xwfb/s271/201805/t20180521_336624.html)
- [LeRobot](https://github.com/huggingface/lerobot)
- [MakerMods Lab](https://github.com/makermods-robotics/makermodslab)
- [ACT](https://huggingface.co/docs/lerobot/act)
