# 团队协作

## 开始工作

1. 从 `docs/backlog.md` 选择任务，在 GitHub 新建任务 Issue，填写负责人和验收标准。
2. 同步 `main`，创建短分支，例如 `feat/sign-recognition` 或 `feat/water-policy`。
3. 执行 `uv sync --locked`，在项目环境中开发。
4. 提交 Pull Request，说明改动、验证结果、接口影响以及剩余工作。
5. 由相关模块队友审阅，再合并到 `main`。

`main` 保留当前可演示版本。修改 `contracts.py` 前，先与识别、流程和机器人负责人确认影响。

## 模块交付

- 识别模块输出 `RetrievalRequest`。真实识别使用 WLASL 对应的 ASL 词汇标签，模糊输入使用 `Intent.UNCLEAR`。
- 流程模块负责确认与执行状态。`request_id` 在一次会话中唯一，并随确认和结果验收传递。
- 机器人模块接入 `RobotExecutor`。执行结束后返回，交付结果由独立步骤报告。
- 界面模块根据 `Status` 显示状态。真实执行器接入时，需要工作线程、超时、停止和故障处理。

## 本地验证

```bash
uv run python -m unittest discover -s tests -v
uv run signaid demo --intent request_water --confirm --delivered
```

## 提交内容

提交业务代码、配置示例、文档和小型测试样例。示教视频、模型权重、数据集、日志和机器专属配置保存在约定存储位置，在 `docs/data-and-models.md` 中记录链接和版本。

`.env` 保存个人配置，API 密钥通过本地环境传入。`.env.example` 仅保留字段名。

提交使用本人 Git 身份，PR 记录实际参与成员。按活动要求保留开源来源与开发记录。
