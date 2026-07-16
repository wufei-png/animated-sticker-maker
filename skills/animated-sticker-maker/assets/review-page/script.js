    "use strict";
    const REVIEW_DATA = __REVIEW_DATA__;
    const t = REVIEW_DATA.text;
    const $ = (selector, root = document) => root.querySelector(selector);
    const create = (tag, className, text) => {
      const element = document.createElement(tag);
      if (className) element.className = className;
      if (text !== undefined && text !== null) element.textContent = String(text);
      return element;
    };
    const interpolate = (template, values) =>
      template.replace(/\{(\w+)\}/g, (_, key) => String(values[key]));
    const statusLabel = (status) => t.status_labels[status] || status.replaceAll("_", " ");
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
        stage.append(create("p", "stage-empty", t.no_reviewable_media));
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
      $("#brand-name").textContent = t.brand_name;
      $("#report-label").textContent = t.report;
      $("#fingerprint-label").textContent = t.artifact_fingerprint;
      $("#generated-label").textContent = t.generated;
      $("#exposure-heading").textContent = t.exposure_rail;
      $("#evidence-heading").textContent = t.review_evidence;
      $("#evidence-note").textContent = t.review_evidence_note;
      $("#frames-heading").textContent = t.frame_exposure_sheet;
      $("#prompts-heading").textContent = t.visual_review_prompts;
      $("#prompts-note").textContent = t.visual_review_prompts_note;
      $("#technical-summary").textContent = t.technical_details;
      $("#technical-section").setAttribute("aria-label", t.technical_details);
      $("#footer-note").textContent = t.footer_note;
      $("#scope-label").textContent = REVIEW_DATA.scope_label;
      $("#hero-title").textContent = REVIEW_DATA.hero.title;
      $("#scope-description").textContent = REVIEW_DATA.scope_description;
      $("#report-name").textContent = REVIEW_DATA.report_name;
      $("#fingerprint").textContent = REVIEW_DATA.artifact_fingerprint;
      const generated = new Date(REVIEW_DATA.generated_at);
      $("#generated-at").textContent = Number.isNaN(generated.getTime())
        ? REVIEW_DATA.generated_at
        : new Intl.DateTimeFormat(
            REVIEW_DATA.language === "zh" ? "zh-CN" : "en",
            { dateStyle: "medium", timeStyle: "medium" }
          ).format(generated);
      $("#hero-subtitle").textContent = REVIEW_DATA.hero.subtitle;
      $("#footer-path").textContent = REVIEW_DATA.report_name;
      const chip = $("#status-chip");
      const fullStatus = statusLabel(REVIEW_DATA.report_status);
      const shortStatus = statusLabel(REVIEW_DATA.visual_status);
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
          t.reference,
          REVIEW_DATA.reference.label,
          "reference",
          REVIEW_DATA.reference.src,
          t.verified_reference_image
        )
      );
      const sequenceRole = REVIEW_DATA.hero.mode === "sequence" ? "sequence-target" : null;
      const mainSrc = REVIEW_DATA.hero.mode === "sequence"
        ? REVIEW_DATA.inspector.frames[0].src
        : REVIEW_DATA.hero.src;
      for (const [label, stageClass] of [
        [t.checker, "checker"],
        [t.light, "light"],
        [t.dark, "dark"],
      ]) {
        rail.append(
          makeSlot(
            label,
            REVIEW_DATA.hero.format || t.unavailable,
            stageClass,
            mainSrc,
            `${REVIEW_DATA.hero.title} · ${label}`,
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
              ? t.render_sequence_note
              : t.encoded_sequence_note
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
      previous.setAttribute("aria-label", t.previous_frame);
      const play = create("button", "icon-button play-button", playing ? "❚❚" : "▶");
      play.type = "button";
      play.setAttribute("aria-label", playing ? t.pause_primary : t.play_primary);
      const next = create("button", "icon-button", "▶");
      next.type = "button";
      next.setAttribute("aria-label", t.next_frame);
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
      range.setAttribute("aria-label", t.frame_timeline);
      const holdMarker = create("button", "hold-marker");
      holdMarker.type = "button";
      holdMarker.dataset.label = t.hold_badge;
      holdMarker.style.setProperty(
        "--hold-position",
        `${Math.max(0, Math.min(100, REVIEW_DATA.semantic_hold.midpoint_ms / total * 100))}%`
      );
      holdMarker.setAttribute("aria-label", t.jump_hold);
      holdMarker.title = REVIEW_DATA.semantic_hold.declared
        ? t.jump_declared_hold
        : t.jump_fallback_hold;
      timelineTrack.append(range, holdMarker);
      const holdExplainer = create("div", "hold-explainer");
      holdExplainer.append(
        create("strong", "", t.hold_title),
        create("p", "", t.hold_explanation),
        create(
          "p",
          "hold-source",
          REVIEW_DATA.semantic_hold.declared
            ? t.hold_declared_source
            : t.hold_fallback_source
        )
      );
      timeline.append(timelineMeta, timelineTrack, holdExplainer);

      const speedWrap = create("label", "speed-control");
      speedWrap.append(create("span", "", t.speed));
      const select = create("select");
      select.setAttribute("aria-label", t.playback_speed);
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
        create("span", "", `${frames.length} ${t.frames}`)
      );
      const loupeStage = create("div", "stage checker");
      addImage(loupeStage, frames[0].src, t.current_primary_frame, "sequence-target");
      loupe.append(loupeHeading, loupeStage);

      const readout = create("article", "frame-readout");
      const number = create("div", "readout-number");
      const title = create("div", "readout-title");
      const description = create("p", "readout-description");
      const readoutGrid = create("div", "readout-grid");
      const durationCell = create("div", "readout-cell");
      durationCell.append(create("span", "", t.duration), create("strong"));
      const timelineCell = create("div", "readout-cell");
      timelineCell.append(create("span", "", t.timeline), create("strong"));
      const pathCell = create("div", "readout-cell");
      pathCell.append(create("span", "", t.source_path), create("strong"));
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
        title.textContent = frame.description || t.ordered_frame;
        description.textContent = REVIEW_DATA.scope === "render_track"
          ? t.render_frame_description
          : t.encoded_frame_description;
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
        play.setAttribute("aria-label", playing ? t.pause_primary : t.play_primary);
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
        [t.actual_size_label, "actual", t.actual_size_alt],
        [t.zoom_label, "zoom", t.zoom_alt],
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
        create("h3", "", t.stress_title),
        create("p", "", t.stress_copy)
      );
      small.append(smallGrid, smallCopy);
      grid.append(small);

      if (REVIEW_DATA.preview) {
        const preview = create("article", "evidence-card");
        const previewStage = create("div", "stage checker");
        addImage(previewStage, REVIEW_DATA.preview.src, t.platform_preview_alt);
        const previewCopy = create("div", "evidence-copy");
        previewCopy.append(
          create("h3", "", REVIEW_DATA.preview.label),
          create(
            "p",
            "",
            interpolate(
              REVIEW_DATA.preview.frame_source === "authored"
                ? t.preview_frame_authored
                : t.preview_frame_exported,
              { frame: REVIEW_DATA.preview.frame }
            )
          )
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
          element.setAttribute(
            "aria-label",
            interpolate(t.show_frame, { label: frame.label })
          );
        }
        if (markHold && index === REVIEW_DATA.semantic_hold.primary_index) {
          element.dataset.hold = "true";
          element.dataset.holdLabel = t.hold_badge;
          element.setAttribute(
            "aria-label",
            `${element.getAttribute("aria-label")} · ${t.semantic_hold_suffix}`
          );
        }
        const stage = create("div", "thumb-stage");
        addImage(
          stage,
          frame.src,
          interpolate(t.thumbnail_alt, { label: frame.label })
        );
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
            prompt.note || t.pending_observation
          )
        );
        root.append(item);
      }
    }

    function renderTechnical() {
      const data = REVIEW_DATA.technical_details;
      const root = $("#technical-content");

      const summaryGroup = create("section", "technical-group");
      summaryGroup.append(create("h3", "", t.boundary_summary));
      const summaryGrid = create("div", "technical-grid");
      for (const item of data.summary) {
        const cell = create("div", "technical-item");
        cell.append(create("span", "", item.label), create("strong", "", item.value));
        summaryGrid.append(cell);
      }
      summaryGroup.append(summaryGrid);
      root.append(summaryGroup);

      const checksGroup = create("section", "technical-group");
      checksGroup.append(create("h3", "", t.technical_checks));
      const checks = create("div", "check-list");
      for (const check of data.checks) {
        const row = create("div", "check-row");
        let statusText = t.fail;
        let statusTone = "false";
        if (check.passed) {
          statusText = t.pass;
          statusTone = "true";
        } else if (check.override) {
          statusText = t.allowed_deviation;
          statusTone = "override";
        }
        const status = create("strong", "", statusText);
        status.dataset.passed = statusTone;
        row.append(status, create("span", "", check.id));
        checks.append(row);
      }
      checksGroup.append(checks);
      root.append(checksGroup);

      if (data.policy_overrides.length) {
        const overridesGroup = create("section", "technical-group");
        overridesGroup.append(create("h3", "", t.policy_overrides));
        const overrides = create("div", "file-list");
        for (const override of data.policy_overrides) {
          const row = create("div", "override-row");
          row.append(
            create("strong", "", override.check_id),
            create(
              "span",
              "",
              interpolate(t.policy_override_detail, {
                source: override.source,
                actual: override.actual,
                minimum: override.default_range[0],
                maximum: override.default_range[1],
              })
            )
          );
          overrides.append(row);
        }
        overridesGroup.append(overrides);
        root.append(overridesGroup);
      }

      const filesGroup = create("section", "technical-group");
      filesGroup.append(create("h3", "", t.primary_files_hashes));
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
        provenance.append(create("h3", "", t.specification_provenance));
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
        ? interpolate(t.sampled_thumbnails, {
            shown: REVIEW_DATA.inspector.overview_indices.length,
            total: REVIEW_DATA.inspector.frames.length,
          })
        : interpolate(t.all_frames_shown, {
            total: REVIEW_DATA.inspector.frames.length,
          });
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
