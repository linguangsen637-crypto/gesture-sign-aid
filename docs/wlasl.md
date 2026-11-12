# WLASL 接入指南

## 获取固定版本

在项目根目录执行以下命令。

```bash
git submodule update --init --recursive
uv sync --locked
uv run signaid wlasl stats --gloss cup
```

项目引用 `dxli94/WLASL` 的 `ac00e6be631c1a2a486621b65f202219f3964d6b` 提交，标注位于 `third_party/WLASL/start_kit/WLASL_v0.3.json`。

## 标注与词汇映射

`gloss` 是 ASL 词汇标签，`instances` 保存视频编号、来源 URL、表达者、划分、帧率、动作起止帧和边界框。项目完整保留每条记录的字段。

| 词汇 | train | val | test | 总记录数 | 请求 |
| --- | --- | --- | --- | --- | --- |
| cup | 9 | 2 | 2 | 13 | request_cup |
| water | 13 | 3 | 2 | 18 | request_water |
| tissue | 5 | 2 | 1 | 8 | request_tissue |

通过 `configs/sign_lexicon.json` 映射需求。真实识别模型输出 gloss 后调用 `request_from_gloss`，随后提交到自动执行流程。同一动作片段的重试通过 `request_id` 参数沿用相同 ID。未知词汇返回 `Intent.UNCLEAR`。命令行 `demo --gloss` 用于模拟该接口。

## 导出子集

```bash
uv run signaid wlasl export --gloss cup --output data/wlasl/subset.json
uv run signaid wlasl export --gloss cup --split train --output data/wlasl/train.json
```

导出文件保持上游 JSON 格式和样本划分。WLASL 的词汇样本数量较少，训练或评估时记录真实可用样本数。

## 准备视频工作目录

```bash
uv run signaid wlasl prepare --gloss cup --output data/wlasl
```

生成目录包含筛选后的 `WLASL_v0.3.json`、来源记录、上游下载脚本、预处理脚本、辅助脚本和 C-UDA 协议。此命令准备工作文件，后续显式执行下载。

阅读上游 README 和协议后，安装可选依赖并执行以下步骤。

```bash
uv sync --locked --extra wlasl
cd data/wlasl
uv run --extra wlasl python video_downloader.py
uv run --extra wlasl python preprocess.py
cd ../..
```

预处理需要 FFmpeg。Mac 已配置独立 FFmpeg 时，在执行脚本的终端加入该路径。

```bash
export PATH="$HOME/hackathon-preflight/media-tools/bin:$PATH"
```

上游脚本会访问原视频来源，部分旧链接可能失效。下载和预处理会生成本地视频，实际处理结果需要逐个验证。原始脚本以工作目录查找标注和辅助文件，所以应在准备好的目录中执行。

## 本地视频索引

预处理片段应以 `<video_id>.mp4` 命名。

```bash
uv run signaid wlasl manifest --gloss cup \
  --videos-dir data/wlasl/videos --output data/wlasl/manifest.json
```

`video_present` 表示同名非空文件存在。视频可解码性、动作内容和截取范围另行检查。索引保留上游帧区间，该区间描述原视频中的动作范围。预处理片段已完成截取，读取时从片段起点开始，避免再次按原始区间裁剪。上游起始帧以 1 编号，`frame_end = -1` 表示到结尾，帧位置按标注帧率解释。

## 接入识别模型

上游 `code/I3D`、`code/TGCN` 提供识别方法及权重获取说明。它们来自较早的研究环境，安装和权重适配由识别负责人验证。也可使用允许的视频 VLM，按相同词汇标签协议接入。

本次集成验证标注读取、子集、工作目录、视频索引与请求映射。真实视频下载、模型权重和现场摄像头识别的结果由后续实验记录。
