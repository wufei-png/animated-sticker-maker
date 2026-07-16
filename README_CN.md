[English](README.md) | 简体中文

# Animated Sticker Maker

[![Tests](https://github.com/wufei-png/animated-sticker-maker/actions/workflows/test.yml/badge.svg)](https://github.com/wufei-png/animated-sticker-maker/actions/workflows/test.yml)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-111827)](https://agentskills.io/specification)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

一个可安装的 Agent Skill：输入一张静态参考图和一句自然语言动作描述，制作一张透明、可循环的动态表情。

它把创意判断和确定性生产串在同一条工作流中：推导角色一致性约束与动作计划，生成最少但够用的关键姿态，构建干净的 RGBA 帧，打包动态 WebP，并在交付前记录技术校验和视觉校验。

## 能做什么

- 锁定主体的标志性轮廓、配色、比例和固定特征。
- 围绕一个清晰语义设计 4–8 个关键帧，并显式记录每帧时长。
- 只在新姿态、遮挡或有机形变确有需要时使用图像生成。
- 用确定性脚本完成文字、变换、透明处理、时序、打包和平台导出。
- 分别处理连续色调插画和原生像素画，不强制使用同一种重采样方案。
- 输出带规范化源帧、参考图元数据、动作计划、接触表和校验报告的可追溯包。
- 在目标平台需要时，从已校验的 RGBA 源帧导出受尺寸和体积约束的 GIF。

## 环境要求

- 支持 [Agent Skills 规范](https://agentskills.io/specification)的 agent host。
- host 提供可结合参考图、保持主体一致性的栅格图像生成或编辑能力。
- Python 3.10 或更高版本，用于确定性脚本。
- [`skills/animated-sticker-maker/requirements.txt`](skills/animated-sticker-maker/requirements.txt) 中列出的 Python 依赖。

仓库只维护一份可移植的 [`SKILL.md`](skills/animated-sticker-maker/SKILL.md)。[`agents/openai.yaml`](skills/animated-sticker-maker/agents/openai.yaml) 只是可选的 OpenAI 界面元数据，不会复制或改写工作流。

## 安装

通过跨 agent 的 `skills` CLI 从 GitHub 交互式安装：

```bash
npx skills add wufei-png/animated-sticker-maker
```

非交互式全局安装到 Codex：

```bash
npx skills add wufei-png/animated-sticker-maker -g -y --agent codex
```

安装前查看仓库识别出的 Skill：

```bash
npx skills add wufei-png/animated-sticker-maker --list
```

可安装的 Skill 包位于 `skills/animated-sticker-maker/`；不需要发布 npm 包，也不需要维护第二份 host 专用格式。

`npx skills add` 只复制 Skill，不会创建 Python 环境。请在 agent host 实际使用的环境中安装确定性脚本依赖：

```bash
python -m pip install "Pillow>=10,<13" "numpy>=1.24"
```

## 调用

这个 Skill 被设计为仅手动调用。请明确点名，不要期望普通图片或动画请求自动触发。支持 `agents/openai.yaml` 的 host 会通过 `allow_implicit_invocation: false` 执行这一约束；其他 host 会读取通用 Skill 描述中的同一意图，但最终是否强制执行取决于 host。

```text
使用 $animated-sticker-maker 处理 ./character.png。
让角色点头一次，并从对话框中显示“收到！”，然后自然循环。
```

不同 host 的调用语法可能不同。如果 host 不支持美元符号语法，明确要求它使用 `animated-sticker-maker` Skill 即可。

## 输出结构

默认的平台无关产物为：

```text
output/<name>/
├── sticker.webp
├── source/
│   ├── frames/
│   ├── rendered-frames/      # 可选、已单独校验的高帧率轨道
│   ├── reference.json
│   └── motion.json
├── validation/
│   ├── contact-sheet.png
│   └── report.json
└── exports/                  # 仅在明确请求平台导出时创建
    └── <platform>/
```

只有 `technical_validation` 与 `visual_validation` 都通过，并且报告中 `deliverable_ready: true` 时，产物才可以交付。

动作计划使用严格的 `schema_version: 2` 契约。可选渲染轨通过显式有序帧数组记录时序，不依赖目录文件名排序；旧版动作 schema 会被直接拒绝。

## 确定性工具

Skill 会基于自身 `SKILL.md` 所在目录解析以下脚本：

- `scripts/chroma_key.py`：移除纯色工作背景，同时保留干净的 Alpha 边缘。
- `scripts/package_sticker.py`：规范化源帧，以事务方式构建 WebP 包和报告。
- `scripts/record_visual_validation.py`：把制作方视觉校验绑定到精确的产物指纹。
- `scripts/export_platform_gif.py`：生成受体积约束的 GIF 和可选静态预览。
- `scripts/doctor.py`：只读地重新执行 schema、媒体、状态、路径和绑定检查。

可针对一个明确边界运行 doctor：

```bash
python skills/animated-sticker-maker/scripts/doctor.py package output/name
python skills/animated-sticker-maker/scripts/doctor.py --json export \
  output/name/exports/<platform>/<name>.export-report.json
```

不传子命令时，doctor 只会在当前目录能唯一识别为 motion、package、report 或 export 边界时诊断 `.`。结果分为 `healthy`（退出码 `0`）、`incomplete`（`2`）和 `invalid`（`1`）。详见 [`references/doctor.md`](skills/animated-sticker-maker/references/doctor.md)。

平台限制会变化。指定平台时，应核对当前官方规范，并在导出报告里记录来源 URL 和核对日期。

## 本地开发

```bash
python -m pip install -r skills/animated-sticker-maker/requirements.txt
python -m py_compile skills/animated-sticker-maker/scripts/*.py
python -m unittest discover -s tests -v
```

测试覆盖打包、动作 schema、Alpha、产物指纹、视觉校验失效、GIF 自适应导出、doctor 输出，以及两个通过真实 CLI 运行的 golden workflow 场景。

## 范围边界

这个仓库只负责通用的单张动态表情制作流程。角色身份、整包排序、发布命名、平台账号配置和一次性生产逻辑应留在素材所属项目中，不应塞进通用 Skill。

完整 agent 契约见 [`SKILL.md`](skills/animated-sticker-maker/SKILL.md)，贡献说明见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 许可证

Apache License 2.0，详见 [`LICENSE`](LICENSE)。
