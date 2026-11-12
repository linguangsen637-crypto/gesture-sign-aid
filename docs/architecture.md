# 架构与接口

## 数据流

```text
动作片段 → VLM → 手语条目 → 需求 → 确认 → ACT 技能 → 取物盘 → 结果验收
```

共享类型定义在 `src/gesture_aid/contracts.py`。

| 类型 | 字段或取值 |
| --- | --- |
| `RetrievalRequest` | `request_id`、`intent`、`recognized_sign_id` |
| `Intent` | `request_water`、`request_tissue`、`unclear` |
| `Status` | `idle`、`waiting_confirmation`、`executing`、`waiting_result`、`completed`、`cancelled`、`failed` |

## 生命周期

`submit` 接受清晰请求后进入 `waiting_confirmation`。`confirm` 必须携带当前请求 ID，执行结束进入 `waiting_result`。`record_result` 根据独立验收进入 `completed` 或 `failed`。`cancel` 用于执行前撤销。终止状态可 `reset`，同一控制器保留已处理 ID，防止重放。

`unclear` 保持 `idle`。执行器异常会使请求进入 `failed`，并继续向调用方抛出异常。当前流程为单线程同步原型，调用方需串行使用。

## 真实模块接入

- VLM 负责人选择现场允许的模型与接口，观察完整动作过程，并按 WLASL 词汇输出标签，并调用 request_from_gloss 转为请求。
- 机器人负责人实现 `RobotExecutor.execute`，把需求映射到对应 ACT 策略。
- 实机适配器负责校验相机输入、机器人标定和模型配置，拥有电机生命周期、停止与故障处理。
- 后端负责人为真实长任务增加独立执行线程和状态接口。当前模拟命令每次启动一个新控制器。
- 结果验收可先由操作员报告，再实现物品入盘的视觉检查。

当前入口只创建 `MockRobot`，真实硬件能力由后续适配器接入。
