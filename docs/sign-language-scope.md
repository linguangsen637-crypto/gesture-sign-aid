# 国家通用手语支持范围

本项目先覆盖与水、纸巾有关的两项取物表达。具体规范词目、动作与语用表达待核验，当前配置中均标记 `pending`。

## 核验步骤

1. 依据《国家通用手语常用词表》及相应词典或教学资料确定表达。
2. 在 `configs/sign_lexicon.json` 填写词目、准确资料定位、参考视频位置和核验人。
3. 记录手形、位置、朝向、运动及必要的非手部特征。
4. 请熟悉国家通用手语的人复核示范，再更新核验状态。
5. 用不同人员、速度和背景的独立片段测试识别效果。

参考示范与评估样本分别记录。参与者授权和资料来源随数据索引保存。公开参考素材保留来源及使用条件，上传前确认许可。

## 官方资料

- [国家通用手语常用词表说明](https://www.moe.gov.cn/jyb_xwfb/s271/201805/t20180521_336624.html)

## 识别输入

实际识别应覆盖动作过程。构图保留手、上肢以及表达所需的身体部位。模型接入后记录采样帧数、时间范围、提示词版本及支持的词目。

## WLASL 识别语料

识别侧准备使用 [WLASL](https://github.com/dxli94/WLASL) v0.3。这是美国手语词级数据集，许可为 C-UDA-1.0，仅限学术和计算用途，不能商用。它不是国家通用手语，不能代替上面的词目核验。当前只把其中两个 gloss 接到取物意图：

| WLASL gloss | 意图 | `recognized_sign_id` | v0.3 样本数 |
| --- | --- | --- | --- |
| `water` | `request_water` | `wlasl_water` | 18（train 13 / val 3 / test 2） |
| `tissue` | `request_tissue` | `wlasl_tissue` | 8（train 5 / val 2 / test 1） |

其余 gloss，包括 `book` 以及相近的 `napkin`、`paper`、`towel`，都输出 `unclear`。

把官方 `WLASL_v0.3.json` 和预处理后的视频放到仓库工作区，不要提交：

```text
datasets/wlasl/WLASL_v0.3.json
datasets/wlasl/videos/<video_id>.mp4
```

`datasets/`、`*.mp4` 已在 `.gitignore` 中。完整语料约 2.1 万条视频，超过 GitHub 单文件限制，视频也来自第三方站点，不能重新发布到本仓库。获取方式以 WLASL 官方仓库为准，使用前阅读其中的 C-UDA 文本。

在仓库根目录检查本机文件是否到位：

```bash
uv run signaid wlasl-status
```

映射写在 `configs/wlasl_gloss_map.json`。这个命令只统计目录和缺失视频，不下载、不训练。
