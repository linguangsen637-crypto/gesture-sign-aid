# 架构与接口

## 数据流

```text
完整动作片段 → 识别与触发判断 → cup → request_cup → 自动执行 pick_cup → 取物盘 → 结果检测
```

共享类型定义在 `src/gesture_aid/contracts.py`。

| 类型 | 字段或取值 |
| --- | --- |
| `RetrievalRequest` | `request_id`、`intent`、`recognized_sign_id` |
| `Intent` | `request_cup`、`request_water`、`request_tissue`、`unclear` |
| `Status` | `idle`、`executing`、`waiting_result`、`completed`、`failed` |

## 生命周期

`submit` 接受清晰请求后立即进入 `executing` 并调用执行器。执行器返回后进入 `waiting_result`，独立结果检测通过 `record_result` 报告交付状态，流程进入 `completed` 或 `failed`。调用方随后可 `reset` 回到 `idle`。同一控制器保留已处理请求 ID，防止重试造成重复执行。

`unclear` 保持 `idle`。执行器异常会使请求进入 `failed`，并继续向调用方抛出异常。执行接口为同步调用，状态转换使用锁保护；执行中或等待结果时提交新请求会被拒绝。锁在机器人执行期间释放，以便其他调用及时读取状态或得到忙碌错误。

## 真实模块接入

当前 `camera` 入口采用 MediaPipe 双手与肩膀关键点、DTW 正负模板比较，并以锁存状态抑制重复触发。`/frame` 返回 `event_id`、`intent` 和诊断信息，`robot_connected` 始终为 false。仅新事件对应 `request_cup`，保持动作期间不会重复输出请求。`/templates` 保存本地关键点模板或独立测试样本。它没有创建或调用机器人执行器，详见 [关键点指南](cup-landmarks.md)。

- VLM 负责人选择现场允许的模型与接口，观察完整动作过程，并按 WLASL 词汇输出标签，并调用 `request_from_gloss(gloss, request_id=clip_id)` 转为请求。识别器需先完成完整动作判断与置信度过滤，只有有效结果才提交。一次动作片段及其重试使用相同 `clip_id`，新动作使用新 ID。连续画面的动作结束检测仍待识别模块实现。
- 机器人负责人实现 `RobotExecutor.execute`，把需求映射到对应 ACT 策略。
- 实机适配器负责校验相机输入、机器人标定和模型配置，拥有电机生命周期、停止与故障处理。
- 后端负责人为真实长任务增加独立执行线程和状态接口。当前模拟命令每次启动一个新控制器。
- 结果验收可先由操作员报告，再实现物品入盘的视觉检查。

`demo` 入口只创建 `MockRobot`；`camera` 不创建机器人。真实硬件能力由后续适配器接入。
