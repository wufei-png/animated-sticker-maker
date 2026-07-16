#!/usr/bin/env python3
"""One offline HTML visual language for every review report scope."""

from __future__ import annotations

import json


def safe_json(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_review_html(model: dict[str, object]) -> str:
    payload = safe_json(model)
    return TEMPLATE.replace("__REVIEW_DATA__", payload)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self' data: file:; img-src 'self' data: file:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
  <title>Animated sticker exposure review</title>
  <style>
    :root {
      color-scheme: dark;
      --carbon-desk: #171a1d;
      --film-well: #22272b;
      --film-lift: #2a3035;
      --exposure-paper: #e7e2d8;
      --playhead-amber: #ffb84d;
      --valid-mint: #81c7b5;
      --fault-red: #e06c62;
      --pending-blue: #8eafc5;
      --ink: #f3f0e8;
      --ink-soft: #c2c8c8;
      --ink-muted: #899398;
      --line: rgba(255, 255, 255, 0.09);
      --line-strong: rgba(255, 255, 255, 0.16);
      --shadow: 0 18px 50px rgba(0, 0, 0, 0.22);
      --display: "Avenir Next Condensed", "DIN Condensed", "Arial Narrow", sans-serif;
      --body: "Avenir Next", "Segoe UI", sans-serif;
      --utility: "SFMono-Regular", "Roboto Mono", "Cascadia Mono", Consolas, monospace;
      --radius-sm: 5px;
      --radius-md: 9px;
      --radius-lg: 13px;
    }

    * {
      box-sizing: border-box;
    }

    html {
      background: var(--carbon-desk);
      font-family: var(--body);
      -webkit-font-smoothing: antialiased;
    }

    body {
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(var(--line), var(--line)) 0 76px / 100% 1px no-repeat,
        var(--carbon-desk);
      min-width: 280px;
      overflow-x: hidden;
    }

    button,
    select,
    input {
      font: inherit;
    }

    button,
    select {
      min-height: 44px;
      border: 1px solid var(--line-strong);
      border-radius: var(--radius-sm);
      color: var(--ink);
      background: #1d2124;
    }

    button {
      cursor: pointer;
      padding: 0 14px;
      transition: background-color 140ms cubic-bezier(0.23, 1, 0.32, 1),
        border-color 140ms cubic-bezier(0.23, 1, 0.32, 1),
        transform 110ms cubic-bezier(0.23, 1, 0.32, 1);
    }

    button:hover {
      background: var(--film-lift);
      border-color: rgba(255, 184, 77, 0.55);
    }

    button:active {
      transform: scale(0.97);
    }

    button:focus-visible,
    select:focus-visible,
    input:focus-visible,
    summary:focus-visible,
    a:focus-visible {
      outline: 2px solid var(--playhead-amber);
      outline-offset: 3px;
    }

    a {
      color: var(--valid-mint);
      text-underline-offset: 3px;
    }

    .shell {
      width: min(1480px, calc(100% - 32px));
      margin: 0 auto;
      padding: 0 0 64px;
    }

    .masthead {
      min-height: 76px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }

    .brand {
      display: flex;
      align-items: baseline;
      gap: 11px;
      min-width: 0;
    }

    .brand-mark {
      color: var(--playhead-amber);
      font: 700 13px/1 var(--utility);
      letter-spacing: 0.12em;
    }

    .brand-name {
      font: 650 18px/1 var(--display);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .status-chip {
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      padding: 0 11px;
      border: 1px solid currentColor;
      border-radius: 999px;
      font: 700 11px/1 var(--utility);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .status-short {
      display: none;
    }

    .status-chip[data-tone="pass"] {
      color: var(--valid-mint);
    }

    .status-chip[data-tone="pending"] {
      color: var(--pending-blue);
    }

    .status-chip[data-tone="fail"] {
      color: var(--fault-red);
    }

    .intro {
      padding: 46px 0 30px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, 0.42fr);
      gap: 48px;
      align-items: end;
    }

    .eyebrow {
      margin: 0 0 10px;
      color: var(--playhead-amber);
      font: 700 11px/1.2 var(--utility);
      letter-spacing: 0.15em;
      text-transform: uppercase;
    }

    h1,
    h2,
    h3,
    p {
      margin-top: 0;
    }

    h1 {
      max-width: 900px;
      margin-bottom: 12px;
      font: 650 clamp(38px, 6vw, 78px)/0.92 var(--display);
      letter-spacing: -0.035em;
      text-wrap: balance;
    }

    .intro-copy {
      max-width: 720px;
      margin-bottom: 0;
      color: var(--ink-soft);
      font-size: 16px;
      line-height: 1.55;
      overflow-wrap: anywhere;
      text-wrap: pretty;
    }

    .report-identity {
      border-left: 1px solid var(--line-strong);
      padding-left: 22px;
      min-width: 0;
    }

    .report-identity dt {
      margin-bottom: 5px;
      color: var(--ink-muted);
      font: 700 10px/1.2 var(--utility);
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }

    .report-identity dd {
      margin: 0 0 14px;
      color: var(--ink-soft);
      font: 12px/1.45 var(--utility);
      overflow-wrap: anywhere;
      word-break: break-word;
    }

    .section {
      margin-top: 28px;
      border-top: 1px solid var(--line);
      padding-top: 24px;
    }

    .section-heading {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 16px;
    }

    .section-heading h2 {
      margin-bottom: 0;
      font: 650 24px/1 var(--display);
      letter-spacing: 0.015em;
      text-transform: uppercase;
    }

    .section-note {
      max-width: 700px;
      margin: 0;
      color: var(--ink-muted);
      font-size: 13px;
      line-height: 1.45;
      text-align: right;
    }

    .exposure-rail {
      display: grid;
      grid-template-columns: minmax(180px, 0.62fr) repeat(3, minmax(0, 1fr));
      gap: 10px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      background: #111416;
      box-shadow: var(--shadow);
    }

    .exposure-slot {
      min-width: 0;
      border-radius: var(--radius-md);
      overflow: hidden;
      background: var(--film-well);
    }

    .slot-label {
      min-height: 42px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 0 12px;
      border-bottom: 1px solid var(--line);
      color: var(--ink-soft);
      font: 700 10px/1 var(--utility);
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }

    .slot-label span:last-child {
      color: var(--ink-muted);
      font-weight: 500;
      letter-spacing: 0;
      text-transform: none;
      max-width: 62%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .stage {
      position: relative;
      min-height: clamp(260px, 32vw, 460px);
      display: grid;
      place-items: center;
      padding: 22px;
      overflow: hidden;
    }

    .stage.reference {
      background: #cfcbc2;
    }

    .stage.checker {
      background-color: #c9ced0;
      background-image:
        linear-gradient(45deg, #aeb6b9 25%, transparent 25%),
        linear-gradient(-45deg, #aeb6b9 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, #aeb6b9 75%),
        linear-gradient(-45deg, transparent 75%, #aeb6b9 75%);
      background-size: 24px 24px;
      background-position: 0 0, 0 12px, 12px -12px, -12px 0;
    }

    .stage.light {
      background: var(--exposure-paper);
    }

    .stage.dark {
      background: #07090a;
    }

    .stage img {
      display: block;
      max-width: 100%;
      max-height: 100%;
      width: min(100%, 360px);
      height: min(100%, 360px);
      object-fit: contain;
      filter: drop-shadow(0 1px 0 rgba(0, 0, 0, 0.1));
    }

    .pixelated {
      image-rendering: pixelated;
    }

    .stage-empty {
      max-width: 230px;
      color: var(--ink-muted);
      font-size: 13px;
      line-height: 1.5;
      text-align: center;
    }

    .sequence-note {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 12px 0 0;
      color: var(--ink-muted);
      font-size: 12px;
      line-height: 1.45;
    }

    .format-tag {
      color: var(--ink-soft);
      font: 600 11px/1 var(--utility);
    }

    .transport {
      margin-top: 12px;
      display: grid;
      grid-template-columns: auto minmax(180px, 1fr) auto;
      gap: 14px;
      align-items: center;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      background: var(--film-well);
    }

    .transport-buttons {
      display: flex;
      gap: 8px;
    }

    .icon-button {
      width: 44px;
      padding: 0;
      font-family: var(--utility);
      font-weight: 700;
    }

    .play-button {
      color: #171a1d;
      border-color: var(--playhead-amber);
      background: var(--playhead-amber);
    }

    .play-button:hover {
      color: #171a1d;
      background: #ffc66d;
    }

    .timeline {
      min-width: 0;
    }

    .timeline-track {
      position: relative;
    }

    .timeline-meta {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 7px;
      color: var(--ink-muted);
      font: 11px/1.2 var(--utility);
      font-variant-numeric: tabular-nums;
    }

    input[type="range"] {
      width: 100%;
      height: 24px;
      margin: 0;
      accent-color: var(--playhead-amber);
      cursor: pointer;
    }

    .hold-marker {
      position: absolute;
      top: 2px;
      left: var(--hold-position);
      width: 10px;
      min-height: 20px;
      padding: 0;
      border: 0;
      border-radius: 2px;
      color: #171a1d;
      background: var(--valid-mint);
      box-shadow: 0 0 0 2px var(--film-well);
      transform: translateX(-50%);
    }

    .hold-marker:hover {
      background: #a3ddce;
    }

    .hold-marker::after {
      content: "HOLD";
      position: absolute;
      left: 50%;
      bottom: calc(100% + 5px);
      color: var(--valid-mint);
      font: 700 8px/1 var(--utility);
      letter-spacing: 0.08em;
      transform: translateX(-50%);
    }

    .speed-control {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--ink-muted);
      font: 10px/1 var(--utility);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .speed-control select {
      padding: 0 34px 0 12px;
      font-family: var(--utility);
    }

    .inspection-deck {
      margin-top: 12px;
      display: grid;
      grid-template-columns: minmax(220px, 0.42fr) 1fr;
      gap: 12px;
    }

    .loupe {
      min-height: 310px;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      overflow: hidden;
      background: var(--film-well);
    }

    .loupe .stage {
      min-height: 268px;
    }

    .frame-readout {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      padding: 18px;
      background: var(--film-well);
    }

    .readout-number {
      margin-bottom: 8px;
      color: var(--playhead-amber);
      font: 650 clamp(34px, 5vw, 58px)/0.95 var(--display);
      font-variant-numeric: tabular-nums;
    }

    .readout-title {
      margin-bottom: 8px;
      color: var(--ink);
      font: 650 19px/1.2 var(--display);
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }

    .readout-description {
      max-width: 640px;
      margin-bottom: 20px;
      color: var(--ink-soft);
      font-size: 14px;
      line-height: 1.55;
    }

    .readout-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }

    .readout-cell {
      padding-top: 12px;
      border-top: 1px solid var(--line);
    }

    .readout-cell span {
      display: block;
      margin-bottom: 5px;
      color: var(--ink-muted);
      font: 700 9px/1 var(--utility);
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }

    .readout-cell strong {
      color: var(--ink-soft);
      font: 600 12px/1.35 var(--utility);
      overflow-wrap: anywhere;
    }

    .evidence-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 12px;
    }

    .evidence-grid[data-count="2"] {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .evidence-card {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      overflow: hidden;
      background: var(--film-well);
    }

    .evidence-card .stage {
      min-height: 240px;
    }

    .evidence-copy {
      padding: 14px;
      border-top: 1px solid var(--line);
    }

    .evidence-copy h3 {
      margin-bottom: 6px;
      font: 650 17px/1.2 var(--display);
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }

    .evidence-copy p {
      margin-bottom: 0;
      color: var(--ink-muted);
      font-size: 12px;
      line-height: 1.45;
    }

    .small-size-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      min-height: 358px;
    }

    .small-size-pane {
      min-width: 0;
      display: grid;
      grid-template-rows: auto 1fr;
      border-right: 1px solid var(--line);
    }

    .small-size-pane:last-child {
      border-right: 0;
    }

    .small-size-label {
      min-height: 38px;
      display: flex;
      align-items: center;
      padding: 0 12px;
      border-bottom: 1px solid var(--line);
      color: var(--ink-muted);
      font: 700 9px/1 var(--utility);
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }

    .evidence-card .small-size-stage {
      min-height: 320px;
    }

    .small-size-stage.actual img {
      width: 50px;
      height: 50px;
      max-width: 50px;
      max-height: 50px;
    }

    .small-size-stage.zoom img {
      width: 250px;
      height: auto;
      max-width: calc(100% - 44px);
      max-height: 250px;
    }

    .frame-strip {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(126px, 1fr));
      gap: 8px;
    }

    .frame-thumb {
      min-height: 0;
      padding: 0;
      overflow: hidden;
      color: inherit;
      text-align: left;
      background: var(--film-well);
    }

    .frame-thumb:hover {
      background: var(--film-lift);
    }

    .frame-thumb[aria-current="true"] {
      border-color: var(--playhead-amber);
      box-shadow: inset 0 -3px var(--playhead-amber);
    }

    .frame-thumb[data-hold="true"] {
      position: relative;
    }

    .frame-thumb[data-hold="true"]::after {
      content: "HOLD";
      position: absolute;
      top: 8px;
      right: 8px;
      padding: 4px 6px;
      border-radius: 3px;
      color: #171a1d;
      background: var(--valid-mint);
      font: 700 8px/1 var(--utility);
      letter-spacing: 0.08em;
    }

    .thumb-stage {
      aspect-ratio: 1;
      display: grid;
      place-items: center;
      padding: 10px;
      background-color: #c9ced0;
      background-image:
        linear-gradient(45deg, #aeb6b9 25%, transparent 25%),
        linear-gradient(-45deg, #aeb6b9 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, #aeb6b9 75%),
        linear-gradient(-45deg, transparent 75%, #aeb6b9 75%);
      background-size: 18px 18px;
      background-position: 0 0, 0 9px, 9px -9px, -9px 0;
    }

    .thumb-stage img {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }

    .thumb-meta {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      padding: 9px 10px 11px;
      color: var(--ink-muted);
      font: 10px/1.25 var(--utility);
      font-variant-numeric: tabular-nums;
    }

    .auxiliary-wrap {
      margin-top: 18px;
    }

    .auxiliary-wrap h3 {
      color: var(--ink-soft);
      font: 650 15px/1 var(--display);
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    .review-prompts {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 8px;
    }

    .prompt {
      min-width: 0;
      min-height: 150px;
      padding: 16px;
      border-top: 2px solid var(--line-strong);
      background: rgba(34, 39, 43, 0.56);
    }

    .prompt[data-filled="true"] {
      border-top-color: var(--valid-mint);
    }

    .prompt h3 {
      margin-bottom: 10px;
      font: 650 16px/1.1 var(--display);
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }

    .prompt p {
      margin-bottom: 0;
      color: var(--ink-muted);
      font-size: 12px;
      line-height: 1.5;
      text-wrap: pretty;
    }

    details {
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      background: var(--film-well);
    }

    summary {
      min-height: 52px;
      display: flex;
      align-items: center;
      padding: 0 16px;
      cursor: pointer;
      color: var(--ink-soft);
      font: 650 15px/1 var(--display);
      letter-spacing: 0.035em;
      text-transform: uppercase;
    }

    .technical-content {
      padding: 0 16px 18px;
      border-top: 1px solid var(--line);
    }

    .technical-group {
      padding-top: 18px;
    }

    .technical-group h3 {
      margin-bottom: 12px;
      color: var(--ink-muted);
      font: 700 10px/1 var(--utility);
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }

    .technical-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      background: var(--line);
    }

    .technical-item {
      min-width: 0;
      padding: 12px;
      background: var(--film-well);
    }

    .technical-item span {
      display: block;
      margin-bottom: 5px;
      color: var(--ink-muted);
      font: 9px/1.2 var(--utility);
      letter-spacing: 0.07em;
      text-transform: uppercase;
    }

    .technical-item strong {
      color: var(--ink-soft);
      font: 600 11px/1.4 var(--utility);
      overflow-wrap: anywhere;
    }

    .check-list,
    .file-list {
      display: grid;
      gap: 1px;
      background: var(--line);
    }

    .check-row,
    .file-row {
      min-width: 0;
      display: grid;
      align-items: baseline;
      gap: 12px;
      padding: 10px 12px;
      background: var(--film-well);
      font: 11px/1.4 var(--utility);
    }

    .check-row {
      grid-template-columns: 74px minmax(0, 1fr);
    }

    .check-row strong[data-passed="true"] {
      color: var(--valid-mint);
    }

    .check-row strong[data-passed="false"] {
      color: var(--fault-red);
    }

    .file-row {
      grid-template-columns: minmax(120px, 0.3fr) minmax(150px, 0.7fr) minmax(240px, 1fr);
    }

    .file-row span {
      color: var(--ink-muted);
      overflow-wrap: anywhere;
    }

    .footer {
      margin-top: 34px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 20px;
      color: var(--ink-muted);
      font: 10px/1.5 var(--utility);
    }

    @media (max-width: 1100px) {
      .exposure-rail {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .review-prompts {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .technical-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 760px) {
      body {
        background-position-y: 64px;
      }

      .shell {
        width: calc(100% - 20px);
      }

      .masthead {
        min-height: 64px;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 12px;
      }

      .brand-name {
        display: none;
      }

      .status-chip {
        max-width: 100%;
      }

      .status-long {
        display: none;
      }

      .status-short {
        display: inline;
      }

      .intro {
        grid-template-columns: minmax(0, 1fr);
        gap: 24px;
        padding-top: 34px;
      }

      .intro > *,
      .report-identity {
        min-width: 0;
        max-width: 100%;
      }

      .report-identity {
        border-left: 0;
        border-top: 1px solid var(--line);
        padding: 18px 0 0;
      }

      .section-heading {
        align-items: start;
        flex-direction: column;
      }

      .section-note {
        text-align: left;
      }

      .exposure-rail,
      .evidence-grid,
      .inspection-deck {
        grid-template-columns: 1fr;
      }

      .small-size-grid {
        grid-template-columns: 1fr;
      }

      .small-size-pane {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }

      .small-size-pane:last-child {
        border-bottom: 0;
      }

      .stage {
        min-height: min(82vw, 390px);
      }

      .transport {
        grid-template-columns: 1fr;
      }

      .transport-buttons {
        justify-content: center;
      }

      .speed-control {
        justify-content: space-between;
      }

      .review-prompts,
      .technical-grid {
        grid-template-columns: 1fr;
      }

      .file-row {
        grid-template-columns: 1fr;
      }

      .footer {
        flex-direction: column;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="masthead">
      <div class="brand">
        <span class="brand-mark">ASM / QA</span>
        <span class="brand-name">Animation inspection light table</span>
      </div>
      <span class="status-chip" id="status-chip"></span>
    </header>

    <section class="intro">
      <div>
        <p class="eyebrow" id="scope-label"></p>
        <h1 id="hero-title"></h1>
        <p class="intro-copy" id="scope-description"></p>
      </div>
      <dl class="report-identity">
        <dt>Report</dt>
        <dd id="report-name"></dd>
        <dt>Artifact fingerprint</dt>
        <dd id="fingerprint"></dd>
        <dt>Generated</dt>
        <dd id="generated-at"></dd>
      </dl>
    </section>

    <section class="section" aria-labelledby="exposure-heading">
      <div class="section-heading">
        <h2 id="exposure-heading">Exposure rail</h2>
        <p class="section-note" id="hero-subtitle"></p>
      </div>
      <div class="exposure-rail" id="exposure-rail"></div>
      <div id="hero-mode-note"></div>
      <div id="transport-root"></div>
      <div id="inspection-root"></div>
    </section>

    <section class="section" aria-labelledby="evidence-heading">
      <div class="section-heading">
        <h2 id="evidence-heading">Review evidence</h2>
        <p class="section-note">Actual-size and inspection-zoom views follow the current report target and playhead.</p>
      </div>
      <div class="evidence-grid" id="evidence-grid"></div>
    </section>

    <section class="section" aria-labelledby="frames-heading">
      <div class="section-heading">
        <h2 id="frames-heading">Frame exposure sheet</h2>
        <p class="section-note" id="frame-strip-note"></p>
      </div>
      <div class="frame-strip" id="frame-strip"></div>
      <div class="auxiliary-wrap" id="auxiliary-wrap" hidden>
        <h3 id="auxiliary-label"></h3>
        <div class="frame-strip" id="auxiliary-strip"></div>
      </div>
    </section>

    <section class="section" aria-labelledby="prompts-heading">
      <div class="section-heading">
        <h2 id="prompts-heading">Visual review prompts</h2>
        <p class="section-note">Read-only. Give feedback in the agent conversation; the agent records the result through the validation command.</p>
      </div>
      <div class="review-prompts" id="review-prompts"></div>
    </section>

    <section class="section" aria-label="Technical details">
      <details>
        <summary>Technical details</summary>
        <div class="technical-content" id="technical-content"></div>
      </details>
    </section>

    <footer class="footer">
      <span>Instantaneous derived view · regenerate before sharing · not validation evidence</span>
      <span id="footer-path"></span>
    </footer>
  </main>

  <script>
    "use strict";
    const REVIEW_DATA = __REVIEW_DATA__;
    const $ = (selector, root = document) => root.querySelector(selector);
    const create = (tag, className, text) => {
      const element = document.createElement(tag);
      if (className) element.className = className;
      if (text !== undefined && text !== null) element.textContent = String(text);
      return element;
    };
    const imageClass = REVIEW_DATA.resampling === "nearest" ? "pixelated" : "";

    function toneForStatus() {
      if (REVIEW_DATA.technical_status === "fail" || REVIEW_DATA.visual_status === "fail") {
        return "fail";
      }
      if (REVIEW_DATA.deliverable_ready) return "pass";
      return "pending";
    }

    function addImage(stage, src, alt, role) {
      if (!src) {
        stage.append(create("p", "stage-empty", "No reviewable media is available for this technically failed artifact."));
        return null;
      }
      const image = create("img", imageClass);
      image.src = src;
      image.alt = alt;
      if (role) image.dataset.role = role;
      stage.append(image);
      return image;
    }

    function makeSlot(label, meta, stageClass, src, alt, role) {
      const slot = create("article", "exposure-slot");
      const heading = create("div", "slot-label");
      heading.append(create("span", "", label));
      heading.append(create("span", "", meta));
      const stage = create("div", `stage ${stageClass}`);
      addImage(stage, src, alt, role);
      slot.append(heading, stage);
      return slot;
    }

    function renderHeader() {
      $("#scope-label").textContent = REVIEW_DATA.scope_label;
      $("#hero-title").textContent = REVIEW_DATA.hero.title;
      $("#scope-description").textContent = REVIEW_DATA.scope_description;
      $("#report-name").textContent = REVIEW_DATA.report_name;
      $("#fingerprint").textContent = REVIEW_DATA.artifact_fingerprint;
      $("#generated-at").textContent = REVIEW_DATA.generated_at;
      $("#hero-subtitle").textContent = REVIEW_DATA.hero.subtitle;
      $("#footer-path").textContent = REVIEW_DATA.report_path;
      const chip = $("#status-chip");
      const fullStatus = REVIEW_DATA.report_status.replaceAll("_", " ");
      const shortStatus = REVIEW_DATA.visual_status.replaceAll("_", " ");
      chip.replaceChildren(
        create("span", "status-long", fullStatus),
        create("span", "status-short", shortStatus)
      );
      chip.setAttribute("aria-label", fullStatus);
      chip.dataset.tone = toneForStatus();
    }

    function renderExposureRail() {
      const rail = $("#exposure-rail");
      rail.append(
        makeSlot(
          "Reference",
          REVIEW_DATA.reference.label,
          "reference",
          REVIEW_DATA.reference.src,
          "Verified reference image"
        )
      );
      const sequenceRole = REVIEW_DATA.hero.mode === "sequence" ? "sequence-target" : null;
      const mainSrc = REVIEW_DATA.hero.mode === "sequence"
        ? REVIEW_DATA.inspector.frames[0].src
        : REVIEW_DATA.hero.src;
      for (const [label, stageClass] of [
        ["Checker", "checker"],
        ["Light", "light"],
        ["Dark", "dark"],
      ]) {
        rail.append(
          makeSlot(
            label,
            REVIEW_DATA.hero.format || "Unavailable",
            stageClass,
            mainSrc,
            `${REVIEW_DATA.hero.title} on ${label.toLowerCase()} background`,
            sequenceRole
          )
        );
      }

      const noteRoot = $("#hero-mode-note");
      if (REVIEW_DATA.hero.mode === "sequence") {
        const note = create("div", "sequence-note");
        note.append(
          create(
            "span",
            "",
            REVIEW_DATA.scope === "render_track"
              ? "Pre-encode render evidence. All three exposures share the declared render timing and playhead."
              : "Post-encode artifact authority. All three exposures share the decoded artifact timing and playhead."
          ),
          create("span", "format-tag", REVIEW_DATA.hero.format)
        );
        noteRoot.append(note);
      }
    }

    function formatTime(milliseconds) {
      const value = Math.max(0, Math.round(milliseconds));
      const seconds = Math.floor(value / 1000);
      const millis = String(value % 1000).padStart(3, "0");
      return `${String(seconds).padStart(2, "0")}:${millis}`;
    }

    function createPlayer() {
      const frames = REVIEW_DATA.inspector.frames;
      const total = REVIEW_DATA.inspector.total_duration_ms;
      const cumulative = [];
      let cursor = 0;
      for (const frame of frames) {
        cumulative.push(cursor);
        cursor += frame.duration_ms;
      }
      let elapsed = 0;
      let frameIndex = 0;
      let playing = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      let speed = 1;
      let previousTimestamp = performance.now();
      let raf = 0;

      const transport = create("div", "transport");
      const buttons = create("div", "transport-buttons");
      const previous = create("button", "icon-button", "◀");
      previous.type = "button";
      previous.setAttribute("aria-label", "Previous frame");
      const play = create("button", "icon-button play-button", playing ? "❚❚" : "▶");
      play.type = "button";
      play.setAttribute("aria-label", playing ? "Pause primary review target" : "Play primary review target");
      const next = create("button", "icon-button", "▶");
      next.type = "button";
      next.setAttribute("aria-label", "Next frame");
      buttons.append(previous, play, next);

      const timeline = create("div", "timeline");
      const timelineMeta = create("div", "timeline-meta");
      const currentTime = create("span", "", "00:000");
      const totalTime = create("span", "", formatTime(total));
      timelineMeta.append(currentTime, totalTime);
      const timelineTrack = create("div", "timeline-track");
      const range = create("input");
      range.type = "range";
      range.min = "0";
      range.max = String(Math.max(0, total - 1));
      range.step = "1";
      range.value = "0";
      range.setAttribute("aria-label", "Frame timeline");
      const holdMarker = create("button", "hold-marker");
      holdMarker.type = "button";
      holdMarker.style.setProperty(
        "--hold-position",
        `${Math.max(0, Math.min(100, REVIEW_DATA.semantic_hold.midpoint_ms / total * 100))}%`
      );
      holdMarker.setAttribute("aria-label", "Jump to semantic hold");
      holdMarker.title = REVIEW_DATA.semantic_hold.declared
        ? "Jump to declared semantic hold"
        : "Jump to longest authored hold";
      timelineTrack.append(range, holdMarker);
      timeline.append(timelineMeta, timelineTrack);

      const speedWrap = create("label", "speed-control");
      speedWrap.append(create("span", "", "Speed"));
      const select = create("select");
      select.setAttribute("aria-label", "Playback speed");
      for (const value of [0.5, 0.8, 1, 1.5, 2]) {
        const option = create("option", "", `${value}×`);
        option.value = String(value);
        option.selected = value === 1;
        select.append(option);
      }
      speedWrap.append(select);
      transport.append(buttons, timeline, speedWrap);

      const inspection = create("div", "inspection-deck");
      const loupe = create("article", "loupe");
      const loupeHeading = create("div", "slot-label");
      loupeHeading.append(
        create("span", "", REVIEW_DATA.inspector.label),
        create("span", "", `${frames.length} frames`)
      );
      const loupeStage = create("div", "stage checker");
      addImage(loupeStage, frames[0].src, "Current primary review frame", "sequence-target");
      loupe.append(loupeHeading, loupeStage);

      const readout = create("article", "frame-readout");
      const number = create("div", "readout-number");
      const title = create("div", "readout-title");
      const description = create("p", "readout-description");
      const readoutGrid = create("div", "readout-grid");
      const durationCell = create("div", "readout-cell");
      durationCell.append(create("span", "", "Duration"), create("strong"));
      const timelineCell = create("div", "readout-cell");
      timelineCell.append(create("span", "", "Timeline"), create("strong"));
      const pathCell = create("div", "readout-cell");
      pathCell.append(create("span", "", "Source path"), create("strong"));
      readoutGrid.append(durationCell, timelineCell, pathCell);
      readout.append(number, title, description, readoutGrid);
      inspection.append(loupe, readout);

      function findFrame(milliseconds) {
        for (let index = frames.length - 1; index >= 0; index -= 1) {
          if (milliseconds >= cumulative[index]) return index;
        }
        return 0;
      }

      function updateTargets() {
        frameIndex = findFrame(elapsed);
        const frame = frames[frameIndex];
        document.querySelectorAll('[data-role="sequence-target"]').forEach((image) => {
          if (image.src !== new URL(frame.src, document.baseURI).href) image.src = frame.src;
        });
        range.value = String(Math.min(elapsed, total - 1));
        currentTime.textContent = formatTime(elapsed);
        number.textContent = frame.label;
        title.textContent = frame.description || "Ordered frame";
        description.textContent = REVIEW_DATA.scope === "render_track"
          ? "Ordered pre-encode render evidence at the current playhead position."
          : "Decoded post-encode evidence from the current artifact. Use it to inspect motion, identity, and Alpha.";
        durationCell.querySelector("strong").textContent = `${frame.duration_ms} ms`;
        timelineCell.querySelector("strong").textContent = `${formatTime(cumulative[frameIndex])} – ${formatTime(cumulative[frameIndex] + frame.duration_ms)}`;
        pathCell.querySelector("strong").textContent = frame.path;
        document.querySelectorAll(".frame-thumb[data-index]").forEach((thumb) => {
          thumb.setAttribute("aria-current", String(Number(thumb.dataset.index) === frameIndex));
        });
      }

      function setPlaying(value) {
        playing = value;
        play.textContent = playing ? "❚❚" : "▶";
        play.setAttribute("aria-label", playing ? "Pause primary review target" : "Play primary review target");
        previousTimestamp = performance.now();
        if (playing && !raf) raf = requestAnimationFrame(tick);
      }

      function seekFrame(index) {
        elapsed = cumulative[Math.max(0, Math.min(frames.length - 1, index))];
        updateTargets();
      }

      function tick(timestamp) {
        raf = 0;
        if (!playing) return;
        elapsed += (timestamp - previousTimestamp) * speed;
        previousTimestamp = timestamp;
        if (elapsed >= total) {
          if (REVIEW_DATA.inspector.loop) {
            elapsed %= total;
          } else {
            elapsed = Math.max(0, total - 1);
            setPlaying(false);
          }
        }
        updateTargets();
        if (playing) raf = requestAnimationFrame(tick);
      }

      previous.addEventListener("click", () => {
        setPlaying(false);
        seekFrame(frameIndex - 1);
      });
      next.addEventListener("click", () => {
        setPlaying(false);
        seekFrame(frameIndex + 1);
      });
      play.addEventListener("click", () => setPlaying(!playing));
      range.addEventListener("input", () => {
        setPlaying(false);
        elapsed = Number(range.value);
        updateTargets();
      });
      holdMarker.addEventListener("click", () => {
        setPlaying(false);
        elapsed = Math.max(
          0,
          Math.min(total - 1, REVIEW_DATA.semantic_hold.midpoint_ms)
        );
        updateTargets();
      });
      select.addEventListener("change", () => {
        speed = Number(select.value);
        previousTimestamp = performance.now();
      });

      updateTargets();
      if (playing) raf = requestAnimationFrame(tick);
      return { transport, inspection, seekFrame };
    }

    function renderEvidence() {
      const grid = $("#evidence-grid");
      const small = create("article", "evidence-card");
      const smallGrid = create("div", "small-size-grid");
      const smallSrc = REVIEW_DATA.inspector.frames[0].src;
      for (const [label, mode, alt] of [
        ["Actual size · 50 × 50", "actual", "Actual 50 by 50 stress view"],
        ["Inspection zoom · 5×", "zoom", "Magnified 50 by 50 inspection view"],
      ]) {
        const pane = create("div", "small-size-pane");
        pane.append(create("div", "small-size-label", label));
        const stage = create("div", `stage checker small-size-stage ${mode}`);
        addImage(stage, smallSrc, alt, "sequence-target");
        pane.append(stage);
        smallGrid.append(pane);
      }
      const smallCopy = create("div", "evidence-copy");
      smallCopy.append(
        create("h3", "", "50 × 50 stress"),
        create(
          "p",
          "",
          "Use actual size to judge readability and the 5× view to inspect silhouette, expression, and Alpha edges."
        )
      );
      small.append(smallGrid, smallCopy);
      grid.append(small);

      if (REVIEW_DATA.preview) {
        const preview = create("article", "evidence-card");
        const previewStage = create("div", "stage checker");
        addImage(previewStage, REVIEW_DATA.preview.src, "Platform preview PNG");
        const previewCopy = create("div", "evidence-copy");
        previewCopy.append(
          create("h3", "", REVIEW_DATA.preview.label),
          create("p", "", `Exported preview frame ${REVIEW_DATA.preview.frame}.`)
        );
        preview.append(previewStage, previewCopy);
        grid.append(preview);
      }
      grid.dataset.count = String(grid.children.length);
    }

    function renderStrip(root, frames, indices, interactive, markHold = false) {
      for (const index of indices) {
        const frame = frames[index];
        const element = create(interactive ? "button" : "article", "frame-thumb");
        if (interactive) {
          element.type = "button";
          element.dataset.index = String(index);
          element.setAttribute("aria-label", `Show ${frame.label}`);
        }
        if (markHold && index === REVIEW_DATA.semantic_hold.primary_index) {
          element.dataset.hold = "true";
          element.setAttribute(
            "aria-label",
            `${element.getAttribute("aria-label")} · semantic hold`
          );
        }
        const stage = create("div", "thumb-stage");
        addImage(stage, frame.src, `${frame.label} thumbnail`);
        const meta = create("div", "thumb-meta");
        meta.append(
          create("span", "", frame.label),
          create("span", "", `${frame.duration_ms} ms`)
        );
        element.append(stage, meta);
        root.append(element);
      }
    }

    function renderPrompts() {
      const root = $("#review-prompts");
      for (const prompt of REVIEW_DATA.review_prompts) {
        const item = create("article", "prompt");
        item.dataset.filled = String(Boolean(prompt.note));
        item.append(
          create("h3", "", prompt.label),
          create(
            "p",
            "",
            prompt.note || "Pending visual observation. Give the agent a concise finding in the conversation."
          )
        );
        root.append(item);
      }
    }

    function renderTechnical() {
      const data = REVIEW_DATA.technical_details;
      const root = $("#technical-content");

      const summaryGroup = create("section", "technical-group");
      summaryGroup.append(create("h3", "", "Boundary summary"));
      const summaryGrid = create("div", "technical-grid");
      for (const item of data.summary) {
        const cell = create("div", "technical-item");
        cell.append(create("span", "", item.label), create("strong", "", item.value));
        summaryGrid.append(cell);
      }
      summaryGroup.append(summaryGrid);
      root.append(summaryGroup);

      const checksGroup = create("section", "technical-group");
      checksGroup.append(create("h3", "", "Technical checks"));
      const checks = create("div", "check-list");
      for (const check of data.checks) {
        const row = create("div", "check-row");
        const status = create("strong", "", check.passed ? "PASS" : "FAIL");
        status.dataset.passed = String(check.passed);
        row.append(status, create("span", "", check.id));
        checks.append(row);
      }
      checksGroup.append(checks);
      root.append(checksGroup);

      const filesGroup = create("section", "technical-group");
      filesGroup.append(create("h3", "", "Primary files and hashes"));
      const files = create("div", "file-list");
      for (const file of data.files) {
        const row = create("div", "file-row");
        row.append(
          create("strong", "", file.role),
          create("span", "", file.path),
          create("span", "", file.sha256)
        );
        files.append(row);
      }
      filesGroup.append(files);
      root.append(filesGroup);

      if (data.spec_url) {
        const provenance = create("section", "technical-group");
        provenance.append(create("h3", "", "Specification provenance"));
        const link = create("a", "", data.spec_url);
        link.href = data.spec_url;
        link.rel = "noopener";
        provenance.append(link);
        root.append(provenance);
      }
    }

    renderHeader();
    renderExposureRail();
    const player = createPlayer();
    $("#transport-root").append(player.transport);
    $("#inspection-root").append(player.inspection);
    renderEvidence();
    renderStrip(
      $("#frame-strip"),
      REVIEW_DATA.inspector.frames,
      REVIEW_DATA.inspector.overview_indices,
      true,
      true
    );
    $("#frame-strip-note").textContent =
      REVIEW_DATA.inspector.frames.length > REVIEW_DATA.inspector.overview_indices.length
        ? `${REVIEW_DATA.inspector.overview_indices.length} evenly sampled thumbnails; transport controls still access all ${REVIEW_DATA.inspector.frames.length} frames.`
        : `All ${REVIEW_DATA.inspector.frames.length} frames are shown.`;
    document.querySelectorAll(".frame-thumb[data-index]").forEach((thumb) => {
      thumb.addEventListener("click", () => player.seekFrame(Number(thumb.dataset.index)));
    });

    if (REVIEW_DATA.auxiliary_frames.frames.length) {
      $("#auxiliary-wrap").hidden = false;
      $("#auxiliary-label").textContent = REVIEW_DATA.auxiliary_frames.label;
      renderStrip(
        $("#auxiliary-strip"),
        REVIEW_DATA.auxiliary_frames.frames,
        REVIEW_DATA.auxiliary_frames.overview_indices,
        false
      );
    }
    renderPrompts();
    renderTechnical();
  </script>
</body>
</html>
"""
