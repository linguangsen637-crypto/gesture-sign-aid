# 上游来源与数据使用

## WLASL

- 仓库为 https://github.com/dxli94/WLASL
- 固定提交为 `ac00e6be631c1a2a486621b65f202219f3964d6b`。
- 上游作者为 Dongxu Li、Cristian Rodriguez、Xin Yu、Hongdong Li。
- 引入位置为 `third_party/WLASL`，通过 Git submodule 保留上游内容。
- 协议位于 `third_party/WLASL/start_kit/C-UDA-1.0.pdf`，使用前阅读上游 README 和完整协议。
- 上游 README 将数据用途标明为 academic and computational use only，并说明禁止商业使用。视频还涉及原始来源的权利和可用性。

准备数据目录时会保留上游协议。共享数据时保留收到的署名、归属信息和适用条款。团队应核对实际使用与展示安排。

```bibtex
@inproceedings{li2020word,
  title={Word-level Deep Sign Language Recognition from Video: A New Large-scale Dataset and Methods Comparison},
  author={Li, Dongxu and Rodriguez, Cristian and Yu, Xin and Li, Hongdong},
  booktitle={The IEEE Winter Conference on Applications of Computer Vision},
  pages={1459--1469},
  year={2020}
}
```

SignAid 的数据适配代码位于 `src/gesture_aid/datasets`。上游下载器、预处理器和识别模型代码保存在子模块中。

## 摄像头识别权重

摄像头模块加载固定版本子模块中的 I3D 代码。WLASL2000 权重及标签来自 [cedssama 的公开镜像](https://huggingface.co/spaces/cedssama/I3D_Sign_Language_Classification/tree/38f30b7a60a9e7336167b1c1eed5b3923a11da9d)，镜像版本为 `38f30b7a60a9e7336167b1c1eed5b3923a11da9d`。该镜像声明其演示使用 WLASL 预训练 I3D 模型。模型标签顺序已与项目中上游 `wlasl_class_list.txt` 核对一致。

- `model.pt` 原名为 `FINAL_nslt_2000_iters=5104_top1=32.48_top5=57.31_top10=66.31.pt`，SHA-256 为 `243a19e6deef3becffbfc5b7dd8adb32916c8bee482565ca243c082584732620`。
- `labels.txt` 原名为 `wlasl_class_list.txt`，SHA-256 为 `2c131fb7f052340aa7ae8579c8cae9746028740b8e62efeb957a7790dbefcf4a`。

权重采用 PyTorch `weights_only=True` 加载，使用 WLASL 对应的数据与模型条款。下载来源、大小与校验值同时保存在本机 `models/wlasl-i3d/provenance.json`。

## MediaPipe 关键点模型

- MediaPipe Python SDK 来自 PyPI 的 `mediapipe`，上游 https://github.com/google-ai-edge/mediapipe ，源码采用 Apache-2.0；模型使用条件请同时参照官方模型卡。
- 手部模型：https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
- 姿态 lite 模型：https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
- `signaid templates setup` 保存下载 URL 和 SHA256 至本机 `models/mediapipe/provenance.json`。模型二进制不提交 Git。
- WLASL 下载视频、派生关键点保留样本来源；仍适用原数据条件。初始 CUP 模板来自 WLASL 14287、14288；初始非 CUP 模板来自 book 69241、07068。它们不构成独立测试集，也没有经过 ASL 专业人员额外复核。
