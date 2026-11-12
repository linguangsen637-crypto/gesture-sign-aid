# CUP 关键点与模板匹配

## 范围

浏览器摄像头 → 本机 MediaPipe → 双手和肩膀特征 → DTW → CUP 事件。没有机器人执行器，没有电机连接。`robot_connected` 始终为 false。

使用 Python 3.12，`uv sync --locked --extra landmarks` 安装依赖。所有视觉可选依赖统一使用 opencv-contrib-python，避免多个 OpenCV 发行包覆盖同一个 cv2 模块。`templates setup` 从 Google 官方存储下载固定版本的手部和 lite 姿态模型，记录来源及 SHA256。正常运行不访问外部推理服务。

## 页面

`uv run --extra landmarks signaid camera` 默认在 `127.0.0.1:8765` 启动。点击开启后优先选内置 MacBook/FaceTime 相机，也可停止后手动选择。请求按完成情况背压，目标约 8 帧/秒，保持原比例、最长宽度 640 像素。实际帧率受设备影响，长时间断流清空序列。

画面需有一位表达者、清楚的双手及肩膀，不镜像、不拉伸。骨架颜色区分模型的两只手槽位；左右手标签只是同一条预处理管线中的一致标识。模板与现场都采用原始未镜像图像，不独立翻转手掌。

选择 CUP/负样本、匹配模板/独立测试、备注；点击录制后倒计时 3 秒，再记录 3 秒关键点。请记录人员与场次。录制期间暂停匹配触发，停止或隐藏页面取消未完成录制。

姿态提取使用 IMAGE 模式，确保不同视频与浏览器会话不会相互污染追踪状态。服务端串行处理模型调用；多页面竞争会明确报忙，建议只开一个识别页面。

## 特征与匹配

- 每只手 21 个三维点，减手腕坐标，以手腕到中指掌指关节的二维长度归一化。
- 先将 x/z 换算到与 y 一致的图像尺度；手部深度为模型估计，不是测量距离。
- 保留手掌朝向；不做独立旋转或镜像对齐。
- 两个手腕以肩膀中点为原点、肩宽为尺度，保留相对身体和双手间的二维位置。
- 存储双手检测与肩膀有效标记。缺失不会用全零手形冒充正常检测，也不填补动作内部的长缺失。
- 移除首尾双手尚未有效检测的准备/退出段；动作内部保留缺失标记。CUP 模板至少 8 帧，双手与身体有效比例至少 65%，且需要动作变化。
- 按时间最近邻重采样至 24 帧，使用带约束 DTW。局部代价由手形（0.65）和身体相对位置（0.35）组成，缺手/身体另有惩罚；返回路径平均距离。
- 实时尝试最近 1.5、2.5、3.5 秒窗口；最近 CUP 距离需 ≤ 0.4，且小于最近负样本距离的 0.8 倍。默认阈值未校准。
- 至少一条正模板和一条负模板才能开始判定。匹配结果只有 cup / unclear。

连续两个通过的检查产生唯一事件；这些检查可能使用重叠窗口，只用于抖动抑制，不是独立证据。触发后锁存，直到连续至少 0.8 秒没有手且距触发至少 1.5 秒，清空旧缓冲再重新识别。摄像头断流不算已经观察到的无手时间。摄像头重启会建立新会话，本阶段不提供机器人层面的跨会话请求去重。

## 数据导入

```bash
# 获取当前词典中可用的直接 MP4，不承诺所有旧链接仍可用
uv run --extra landmarks signaid templates import-wlasl --gloss cup --label cup --download
uv run --extra landmarks signaid templates import-wlasl --gloss book --label negative --download

# 已由上游脚本完成动作截取的视频；不再按原始帧编号重复裁切
uv run --extra landmarks signaid templates import-wlasl --videos-dir data/wlasl/videos --gloss cup --label cup

# 其他已截取、未镜像、最长 12 秒的单次动作视频
uv run --extra landmarks signaid templates import-video /absolute/path/cup.mp4 --label cup --name person1-session1
uv run --extra landmarks signaid templates import-video /absolute/path/wave.mp4 --label negative --split test
```

导入器保留 WLASL video_id、signer_id、原始 split、URL 和文件校验值；原 train 加入模板，val/test 保存在 test，永不参与匹配。原划分并不保证表达者完全隔离，正式泛化评估应另建按表达者分组的测试集。重复导入同一 WLASL video_id 会跳过。下载/解码/质量失败记录在 `data/cup-templates/reports/`，不伪造模板。

本次已导入 CUP 14287、14288，负样本 book 69241、07068，均来自原 train。没有可用的独立测试样本，因此没有现场准确率结论。`book` 仅提供一种干扰，仍需录制挥手、挠头、拿杯、喝水和静止等现场样本。

模板 JSON 使用 version=1，包含 label、split、name、source 与带时间戳的 frames。自录样本的 `asl_reviewed` 默认 false，标签由操作员指定，系统不自动证明动作符合 ASL。数据仅存本地，未提交 Git。

## 验收

```bash
uv run --extra landmarks signaid templates stats
uv run --extra landmarks signaid templates evaluate
uv run --extra landmarks python -m unittest discover -s tests -v
```

评估仅对 test 条目计算 CUP 召回率和负样本误判率；无对应测试数据或模板不齐全时为 null。不要拿模板自匹配结果报告准确率，也不要用最终测试集反复调阈值。静止等无动作测试可保留无手帧，用于验证拒绝行为。

另行记录连续摄像头下每分钟误触发次数、一次动作的触发次数、响应延迟和不同表达者的效果。遮挡、手槽位切换、单手变体和相近动作仍可能导致漏识别或误识别；当前不是完整 ASL 翻译器。
