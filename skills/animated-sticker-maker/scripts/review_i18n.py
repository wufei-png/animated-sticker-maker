#!/usr/bin/env python3
"""Built-in English and Chinese copy for the offline Review Page."""

from __future__ import annotations


SUPPORTED_LANGUAGES = {"en", "zh"}

LANGUAGE_TEXT: dict[str, dict[str, object]] = {
    "en": {
        "html_lang": "en",
        "document_title": "Animated sticker exposure review",
        "brand_name": "Animation inspection light table",
        "report": "Report",
        "artifact_fingerprint": "Artifact fingerprint",
        "generated": "Generated",
        "exposure_rail": "Exposure rail",
        "review_evidence": "Review evidence",
        "review_evidence_note": (
            "Actual-size and inspection-zoom views follow the current report "
            "target and playhead."
        ),
        "frame_exposure_sheet": "Frame exposure sheet",
        "visual_review_prompts": "Visual review prompts",
        "visual_review_prompts_note": (
            "Read-only. Give feedback in the agent conversation; the agent "
            "records the result through the validation command."
        ),
        "technical_details": "Technical details",
        "footer_note": (
            "Instantaneous derived view · regenerate before sharing · "
            "not validation evidence"
        ),
        "no_reviewable_media": (
            "No reviewable media is available for this technically failed "
            "artifact."
        ),
        "reference": "Reference",
        "verified_reference_image": "Verified reference image",
        "checker": "Checker",
        "light": "Light",
        "dark": "Dark",
        "unavailable": "Unavailable",
        "render_sequence_note": (
            "Pre-encode render evidence. All three exposures share the "
            "declared render timing and playhead."
        ),
        "encoded_sequence_note": (
            "Post-encode artifact authority. All three exposures share the "
            "decoded artifact timing and playhead."
        ),
        "previous_frame": "Previous frame",
        "pause_primary": "Pause primary review target",
        "play_primary": "Play primary review target",
        "next_frame": "Next frame",
        "frame_timeline": "Frame timeline",
        "jump_hold": "Jump to semantic hold",
        "jump_declared_hold": "Jump to declared semantic hold",
        "jump_fallback_hold": "Jump to longest authored hold",
        "speed": "Speed",
        "playback_speed": "Playback speed",
        "hold_badge": "HOLD",
        "hold_title": "Semantic hold",
        "hold_explanation": (
            "Marks the clearest semantic moment for judging meaning, contact, "
            "expression, and small-size readability. It is an inspection "
            "anchor, not an automatic playback pause."
        ),
        "hold_declared_source": (
            "Declared by motion.semantic_hold_frame; positioned at the "
            "midpoint of that authored frame's time span, then mapped onto "
            "the current review track."
        ),
        "hold_fallback_source": (
            "No semantic_hold_frame was declared; using the midpoint of the "
            "longest authored frame as a fallback, then mapping it onto the "
            "current review track."
        ),
        "frames": "frames",
        "current_primary_frame": "Current primary review frame",
        "duration": "Duration",
        "timeline": "Timeline",
        "source_path": "Source path",
        "ordered_frame": "Ordered frame",
        "render_frame_description": (
            "Ordered pre-encode render evidence at the current playhead "
            "position."
        ),
        "encoded_frame_description": (
            "Decoded post-encode evidence from the current artifact. Use it "
            "to inspect motion, identity, and Alpha."
        ),
        "actual_size_label": "Actual size · 50 × 50",
        "zoom_label": "Inspection zoom · 5×",
        "actual_size_alt": "Actual 50 by 50 stress view",
        "zoom_alt": "Magnified 50 by 50 inspection view",
        "stress_title": "50 × 50 stress",
        "stress_copy": (
            "Use actual size to judge readability and the 5× view to inspect "
            "silhouette, expression, and Alpha edges."
        ),
        "platform_preview_alt": "Platform preview PNG",
        "preview_frame": "Exported preview frame {frame}.",
        "show_frame": "Show {label}",
        "semantic_hold_suffix": "semantic hold",
        "thumbnail_alt": "{label} thumbnail",
        "pending_observation": (
            "Pending visual observation. Give the agent a concise finding in "
            "the conversation."
        ),
        "boundary_summary": "Boundary summary",
        "technical_checks": "Technical checks",
        "pass": "PASS",
        "fail": "FAIL",
        "primary_files_hashes": "Primary files and hashes",
        "specification_provenance": "Specification provenance",
        "sampled_thumbnails": (
            "{shown} evenly sampled thumbnails; transport controls still "
            "access all {total} frames."
        ),
        "all_frames_shown": "All {total} frames are shown.",
        "scope_labels": {
            "package_source": "Encoded artifact",
            "render_track": "Pre-encode render track",
            "export_files": "Encoded platform derivative",
        },
        "scope_descriptions": {
            "package_source": (
                "Post-encode authority: inspect the actual packaged WebP; "
                "authored frames are comparison evidence."
            ),
            "render_track": (
                "Pre-encode evidence: inspect the ordered render PNG sequence "
                "before packaging or platform encoding."
            ),
            "export_files": (
                "Post-export authority: inspect the actual platform GIF; its "
                "selected source track is comparison evidence."
            ),
        },
        "hero": {
            "package_title": "Encoded package",
            "package_subtitle": (
                "Decoded frames from the actual sticker.webp artifact. The "
                "transport controls this post-encode result."
            ),
            "package_missing_title": "Encoded package unavailable",
            "package_missing_subtitle": (
                "Technical validation failed before a usable sticker.webp "
                "was produced."
            ),
            "render_title": "Render track preview",
            "render_subtitle": (
                "Exact ordered render PNG frames and declared timing. This is "
                "pre-encode evidence, not an encoded deliverable."
            ),
            "export_title": "{platform} export",
            "export_subtitle": (
                "Decoded frames from the actual exported GIF. The transport "
                "controls this platform derivative."
            ),
        },
        "reference_labels": {
            "included": "Included package reference",
            "external": "Verified external reference",
        },
        "inspector_labels": {
            "encoded": "Decoded encoded-artifact inspector",
            "render": "Render track inspector",
            "authored": "Authored keyframe inspector",
        },
        "auxiliary_labels": {
            "export": "Selected source-track comparison",
            "authored": "Authored keyframe comparison",
        },
        "prompt_labels": {
            "identity": "Identity",
            "meaning": "Meaning",
            "loop": "Loop",
            "alpha": "Alpha",
            "small_size": "Small Size",
        },
        "technical_labels": {
            "artifact_scope": "Artifact scope",
            "aggregate_status": "Aggregate status",
            "technical": "Technical",
            "visual": "Visual",
            "deliverable_ready": "Deliverable ready",
            "canvas": "Canvas",
            "frame_count": "Frame count",
            "total_duration": "Total duration",
            "loop": "Loop",
            "resampling": "Resampling",
            "target_fps": "Target FPS",
            "platform": "Platform",
            "frame_track": "Frame track",
            "gif_bytes": "GIF bytes",
            "gif_max_bytes": "GIF max bytes",
            "palette_colors": "Palette colors",
            "selected_fps": "Selected FPS",
            "verified_on": "Verified on",
        },
        "file_roles": {
            "validation_report": "Validation report",
            "packaged_motion": "Packaged motion",
            "primary_media": "Primary media",
            "platform_preview": "Platform preview",
            "reference_image": "Reference image",
        },
        "status_labels": {
            "pass": "pass",
            "fail": "fail",
            "pending": "pending",
            "technical_validation_failed": "technical validation failed",
            "visual_validation_failed": "visual validation failed",
            "diagnostic_unvalidated": "diagnostic unvalidated",
            "pending_visual_validation": "pending visual validation",
        },
        "boolean_labels": {"true": "true", "false": "false"},
        "formats": {
            "webp": "Animated WebP",
            "render": "Ordered render PNG sequence",
            "gif": "Animated GIF",
            "preview": "Platform preview PNG",
        },
        "decoded_frame_description": (
            "Decoded frame from the actual {format_label} artifact"
        ),
    },
    "zh": {
        "html_lang": "zh-CN",
        "document_title": "动态贴纸曝光审核",
        "brand_name": "动画检查灯箱",
        "report": "报告",
        "artifact_fingerprint": "产物指纹",
        "generated": "生成时间",
        "exposure_rail": "曝光检查",
        "review_evidence": "审核证据",
        "review_evidence_note": "真实尺寸与放大视图跟随当前审核对象和播放位置。",
        "frame_exposure_sheet": "帧曝光表",
        "visual_review_prompts": "视觉审核项",
        "visual_review_prompts_note": (
            "只读页面。请在与 agent 的会话中反馈，agent 通过验证命令记录结果。"
        ),
        "technical_details": "技术详情",
        "footer_note": "即时派生视图 · 分享前重新生成 · 不属于验证证据",
        "no_reviewable_media": "该产物技术验证失败，没有可审核的媒体。",
        "reference": "参考图",
        "verified_reference_image": "已校验的参考图",
        "checker": "透明棋盘",
        "light": "亮色背景",
        "dark": "暗色背景",
        "unavailable": "不可用",
        "render_sequence_note": (
            "编码前的渲染证据。三个曝光视图共享声明的渲染时序与播放位置。"
        ),
        "encoded_sequence_note": (
            "编码后产物是最终依据。三个曝光视图共享解码后的产物时序与播放位置。"
        ),
        "previous_frame": "上一帧",
        "pause_primary": "暂停主要审核对象",
        "play_primary": "播放主要审核对象",
        "next_frame": "下一帧",
        "frame_timeline": "帧时间轴",
        "jump_hold": "跳转到语义停留点",
        "jump_declared_hold": "跳转到已声明的语义停留点",
        "jump_fallback_hold": "跳转到最长关键帧的停留点",
        "speed": "速度",
        "playback_speed": "播放速度",
        "hold_badge": "语义帧",
        "hold_title": "语义停留点（HOLD）",
        "hold_explanation": (
            "标记动画语义最清楚的审核时刻，用于检查含义、接触关系、表情和"
            "小尺寸可读性。它是审核锚点，不会让动画在此自动暂停。"
        ),
        "hold_declared_source": (
            "位置来自 motion.semantic_hold_frame，取该关键帧时间区间的中点，"
            "再映射到当前审核轨道。"
        ),
        "hold_fallback_source": (
            "未声明 semantic_hold_frame，因此回退为持续时间最长关键帧的中点，"
            "再映射到当前审核轨道。"
        ),
        "frames": "帧",
        "current_primary_frame": "当前主要审核帧",
        "duration": "持续时间",
        "timeline": "时间区间",
        "source_path": "来源路径",
        "ordered_frame": "有序帧",
        "render_frame_description": "当前播放位置对应的编码前有序渲染证据。",
        "encoded_frame_description": (
            "当前产物解码后的编码证据，用于检查动作、形象一致性和 Alpha。"
        ),
        "actual_size_label": "真实尺寸 · 50 × 50",
        "zoom_label": "检查放大 · 5×",
        "actual_size_alt": "真实 50 × 50 小尺寸压力测试视图",
        "zoom_alt": "放大后的 50 × 50 检查视图",
        "stress_title": "50 × 50 压力测试",
        "stress_copy": (
            "真实尺寸用于判断可读性，5× 视图用于检查轮廓、表情和 Alpha 边缘。"
        ),
        "platform_preview_alt": "平台预览 PNG",
        "preview_frame": "导出的预览帧：第 {frame} 帧。",
        "show_frame": "查看 {label}",
        "semantic_hold_suffix": "语义停留点",
        "thumbnail_alt": "{label} 缩略图",
        "pending_observation": "等待视觉观察。请在会话中向 agent 提供简洁结论。",
        "boundary_summary": "边界摘要",
        "technical_checks": "技术检查",
        "pass": "通过",
        "fail": "失败",
        "primary_files_hashes": "主要文件与哈希",
        "specification_provenance": "规范来源",
        "sampled_thumbnails": (
            "均匀展示 {shown} 张缩略图；播放器仍可访问全部 {total} 帧。"
        ),
        "all_frames_shown": "已展示全部 {total} 帧。",
        "scope_labels": {
            "package_source": "编码后产物",
            "render_track": "编码前渲染轨道",
            "export_files": "编码后平台衍生物",
        },
        "scope_descriptions": {
            "package_source": (
                "编码后产物是审核依据：检查实际打包的 WebP；关键帧仅用于对照。"
            ),
            "render_track": (
                "编码前证据：检查打包或平台编码之前的有序 PNG 渲染序列。"
            ),
            "export_files": (
                "平台导出物是审核依据：检查实际 GIF；所选来源轨道仅用于对照。"
            ),
        },
        "hero": {
            "package_title": "编码后贴纸包",
            "package_subtitle": (
                "从实际 sticker.webp 产物解码的帧；播放器控制编码后的真实结果。"
            ),
            "package_missing_title": "编码后贴纸包不可用",
            "package_missing_subtitle": (
                "技术验证在生成可用 sticker.webp 之前失败。"
            ),
            "render_title": "渲染轨道预览",
            "render_subtitle": (
                "按声明顺序和时序展示渲染 PNG；这是编码前证据，不是编码交付物。"
            ),
            "export_title": "{platform} 导出物",
            "export_subtitle": (
                "从实际导出 GIF 解码的帧；播放器控制该平台衍生物。"
            ),
        },
        "reference_labels": {
            "included": "包内参考图",
            "external": "已校验的外部参考图",
        },
        "inspector_labels": {
            "encoded": "编码产物解码帧检查器",
            "render": "渲染轨道检查器",
            "authored": "关键帧检查器",
        },
        "auxiliary_labels": {
            "export": "所选来源轨道对照",
            "authored": "关键帧对照",
        },
        "prompt_labels": {
            "identity": "形象一致性",
            "meaning": "语义表达",
            "loop": "循环衔接",
            "alpha": "透明边缘",
            "small_size": "小尺寸表现",
        },
        "technical_labels": {
            "artifact_scope": "产物范围",
            "aggregate_status": "汇总状态",
            "technical": "技术验证",
            "visual": "视觉验证",
            "deliverable_ready": "可交付",
            "canvas": "画布",
            "frame_count": "帧数",
            "total_duration": "总时长",
            "loop": "循环",
            "resampling": "重采样",
            "target_fps": "目标帧率",
            "platform": "平台",
            "frame_track": "帧轨道",
            "gif_bytes": "GIF 字节数",
            "gif_max_bytes": "GIF 字节上限",
            "palette_colors": "调色板颜色数",
            "selected_fps": "选用帧率",
            "verified_on": "规范核对日期",
        },
        "file_roles": {
            "validation_report": "验证报告",
            "packaged_motion": "打包后的动作方案",
            "primary_media": "主要媒体",
            "platform_preview": "平台预览",
            "reference_image": "参考图",
        },
        "status_labels": {
            "pass": "通过",
            "fail": "失败",
            "pending": "待审核",
            "technical_validation_failed": "技术验证失败",
            "visual_validation_failed": "视觉验证失败",
            "diagnostic_unvalidated": "诊断产物未验证",
            "pending_visual_validation": "等待视觉验证",
        },
        "boolean_labels": {"true": "是", "false": "否"},
        "formats": {
            "webp": "动态 WebP",
            "render": "有序渲染 PNG 序列",
            "gif": "动态 GIF",
            "preview": "平台预览 PNG",
        },
        "decoded_frame_description": "从实际的{format_label}产物中解码的帧",
    },
}


def translation_key_paths(
    value: dict[str, object],
    prefix: tuple[str, ...] = (),
) -> set[tuple[str, ...]]:
    paths: set[tuple[str, ...]] = set()
    for key, child in value.items():
        path = (*prefix, key)
        paths.add(path)
        if isinstance(child, dict):
            paths.update(translation_key_paths(child, path))
    return paths


if translation_key_paths(LANGUAGE_TEXT["en"]) != translation_key_paths(
    LANGUAGE_TEXT["zh"]
):
    raise RuntimeError("English and Chinese review translations must have identical keys")


def language_text(language: str) -> dict[str, object]:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("review language must be 'en' or 'zh'")
    return LANGUAGE_TEXT[language]
