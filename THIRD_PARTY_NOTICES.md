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
