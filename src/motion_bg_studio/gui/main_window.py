"""Main desktop window."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIntValidator, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..generators import GENERATORS, list_generators
from ..palettes import list_palettes
from ..renderer import RenderJob
from .preview_widget import PreviewWidget
from .render_worker import RenderWorker

RES_PRESETS: list[tuple[str, int, int]] = [
    ("4K UHD (3840x2160)", 3840, 2160),
    ("DCI 4K (4096x2160)", 4096, 2160),
    ("QHD (2560x1440)", 2560, 1440),
    ("Full HD (1920x1080)", 1920, 1080),
    ("Square 4K (2160x2160)", 2160, 2160),
    ("Vertical 4K (2160x3840)", 2160, 3840),
]

DURATION_PRESETS = [5, 10, 15, 20, 30]
FPS_PRESETS = [24, 25, 30, 50, 60]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Motion Background Studio  v{__version__}")
        self.resize(1280, 760)
        self._worker: RenderWorker | None = None
        self._output_dir = Path.home() / "MotionBackgrounds"

        self._build_ui()
        self._refresh_preview()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        # Menu
        file_menu = self.menuBar().addMenu("&File")
        choose_dir = QAction("Choose &output folder…", self)
        choose_dir.triggered.connect(self._pick_output_dir)
        file_menu.addAction(choose_dir)
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        help_menu = self.menuBar().addMenu("&Help")
        about = QAction("About", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

        # Central layout: [params | preview | queue]
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_params_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.addWidget(self._build_queue_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([320, 700, 280])
        self.setCentralWidget(splitter)

        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(220)
        sb.addPermanentWidget(self.progress)
        self.status_label = QLabel("Ready")
        sb.addWidget(self.status_label)

    def _build_params_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        gb_style = QGroupBox("Style")
        sl = QFormLayout(gb_style)
        self.style_cb = QComboBox()
        for name in list_generators():
            cls = GENERATORS[name]
            self.style_cb.addItem(cls.display_name, name)
        self.style_cb.currentIndexChanged.connect(self._refresh_preview)
        sl.addRow("Motion type:", self.style_cb)

        self.palette_cb = QComboBox()
        for name in list_palettes():
            self.palette_cb.addItem(name.replace("_", " ").title(), name)
        self.palette_cb.currentIndexChanged.connect(self._refresh_preview)
        sl.addRow("Color palette:", self.palette_cb)
        layout.addWidget(gb_style)

        gb_out = QGroupBox("Output")
        of = QFormLayout(gb_out)
        self.res_cb = QComboBox()
        for label, w_, h_ in RES_PRESETS:
            self.res_cb.addItem(label, (w_, h_))
        of.addRow("Resolution:", self.res_cb)

        self.duration_cb = QComboBox()
        for d in DURATION_PRESETS:
            self.duration_cb.addItem(f"{d} s", d)
        self.duration_cb.setCurrentIndex(DURATION_PRESETS.index(15))
        self.duration_cb.currentIndexChanged.connect(self._refresh_preview)
        of.addRow("Duration:", self.duration_cb)

        self.fps_cb = QComboBox()
        self.fps_cb.setEditable(True)
        self.fps_cb.setInsertPolicy(QComboBox.NoInsert)
        self.fps_cb.lineEdit().setValidator(QIntValidator(1, 999, self))
        self.fps_cb.setToolTip(
            "Pick a preset or type any integer (1\u2013999). Common picks: "
            "24 cinematic, 30 web, 60 smooth, 120 slow-mo source."
        )
        for f in FPS_PRESETS:
            self.fps_cb.addItem(f"{f}", f)
        self.fps_cb.setCurrentIndex(FPS_PRESETS.index(30))
        of.addRow("FPS:", self.fps_cb)

        self.crf_sb = QSpinBox()
        self.crf_sb.setRange(0, 51)
        self.crf_sb.setValue(18)
        self.crf_sb.setToolTip("Lower = higher quality. 18 is visually lossless.")
        of.addRow("Quality (CRF):", self.crf_sb)

        self.preset_cb = QComboBox()
        for p in ("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower"):
            self.preset_cb.addItem(p)
        self.preset_cb.setCurrentText("medium")
        of.addRow("Encoding preset:", self.preset_cb)

        # Hardware encoder + multiprocessing — the two biggest perf wins on
        # consumer hardware. Probe NVENC / QSV / AMF lazily on first paint so
        # the launch is not blocked by a 5–15s ffmpeg subprocess.
        self.encoder_cb = QComboBox()
        self.encoder_cb.addItem("Auto (GPU if available)", "auto")
        self.encoder_cb.addItem("GPU — NVENC / QSV / AMF", "gpu")
        self.encoder_cb.addItem("CPU — libx264", "cpu")
        self.encoder_cb.setCurrentIndex(0)
        self.encoder_cb.setToolTip(
            "GPU encoding via your graphics card (NVIDIA NVENC, Intel QSV, AMD AMF) is\n"
            "typically 3\u20136\u00d7 faster than CPU and frees the CPU for frame generation.\n"
            "'Auto' falls back to CPU when no GPU encoder is detected."
        )
        of.addRow("Encoder:", self.encoder_cb)

        self.workers_cb = QComboBox()
        self.workers_cb.addItem("Auto (use most CPU cores)", 0)
        for w_count in (1, 2, 3, 4, 6, 8):
            label = "1 (serial, no multiprocessing)" if w_count == 1 else f"{w_count} workers"
            self.workers_cb.addItem(label, w_count)
        self.workers_cb.setCurrentIndex(0)
        self.workers_cb.setToolTip(
            "Render frames in parallel across CPU cores. 'Auto' picks (cores - 1).\n"
            "Use 1 if multiprocessing fights with another heavy process or your machine has only 1\u20132 cores."
        )
        of.addRow("Workers:", self.workers_cb)
        layout.addWidget(gb_out)

        gb_seed = QGroupBox("Seed")
        sf = QFormLayout(gb_seed)
        self.seed_sb = QSpinBox()
        self.seed_sb.setRange(0, 2**31 - 1)
        self.seed_sb.setValue(42)
        self.seed_sb.valueChanged.connect(self._refresh_preview)

        seed_row = QWidget()
        srl = QHBoxLayout(seed_row)
        srl.setContentsMargins(0, 0, 0, 0)
        srl.addWidget(self.seed_sb, 1)
        rand_btn = QToolButton()
        rand_btn.setText("Random")
        rand_btn.clicked.connect(self._random_seed)
        srl.addWidget(rand_btn)
        sf.addRow("Seed:", seed_row)
        layout.addWidget(gb_seed)

        gb_actions = QGroupBox("Render")
        af = QVBoxLayout(gb_actions)
        self.queue_btn = QPushButton("Add to queue")
        self.queue_btn.clicked.connect(self._add_to_queue)
        af.addWidget(self.queue_btn)
        self.queue_variations_cb = QCheckBox("Add 5 random-seed variations")
        af.addWidget(self.queue_variations_cb)
        self.render_btn = QPushButton("Render queue \u25B6")
        self.render_btn.setStyleSheet("font-weight: 600; padding: 8px;")
        self.render_btn.clicked.connect(self._start_render)
        af.addWidget(self.render_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_render)
        af.addWidget(self.cancel_btn)
        layout.addWidget(gb_actions)

        layout.addStretch()
        return w

    def _build_preview_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        title = QLabel("Live preview (low-res)")
        title.setStyleSheet("font-weight: 600; padding: 4px 0;")
        layout.addWidget(title)
        self.preview = PreviewWidget()
        layout.addWidget(self.preview, 1)
        hint = QLabel(
            "Tip: the live preview runs at 480x270/24fps. The final render will be at the resolution & FPS you've selected."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)
        return w

    def _build_queue_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        title = QLabel("Render queue")
        title.setStyleSheet("font-weight: 600; padding: 4px 0;")
        layout.addWidget(title)
        self.queue_list = QListWidget()
        layout.addWidget(self.queue_list, 1)
        rmv_btn = QPushButton("Remove selected")
        rmv_btn.clicked.connect(self._remove_selected)
        layout.addWidget(rmv_btn)
        clr_btn = QPushButton("Clear queue")
        clr_btn.clicked.connect(self.queue_list.clear)
        layout.addWidget(clr_btn)
        layout.addWidget(QLabel("Output folder:"))
        self.out_dir_label = QLabel(str(self._output_dir))
        self.out_dir_label.setWordWrap(True)
        self.out_dir_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.out_dir_label)
        change_btn = QPushButton("Change…")
        change_btn.clicked.connect(self._pick_output_dir)
        layout.addWidget(change_btn)
        return w

    # ------------------------------------------------------------------ Actions

    def _current_job(self) -> RenderJob:
        w_, h_ = self.res_cb.currentData()
        return RenderJob(
            style=self.style_cb.currentData(),
            palette=self.palette_cb.currentData(),
            width=w_,
            height=h_,
            duration=float(self.duration_cb.currentData()),
            fps=self._current_fps(),
            seed=int(self.seed_sb.value()),
            crf=int(self.crf_sb.value()),
            preset=self.preset_cb.currentText(),
            encoder=self.encoder_cb.currentData() or "auto",
            workers=int(self.workers_cb.currentData() or 0),
        )

    def _current_fps(self) -> int:
        """Return current FPS from the editable combo.

        For editable combos the source of truth is the line edit text, since
        ``currentData()`` keeps pointing at the last-selected preset even when
        the user typed something different. Falls back to the preset data,
        then to 30, on invalid input.
        """
        text = self.fps_cb.currentText().strip()
        try:
            value = int(text)
        except (TypeError, ValueError):
            value = 0
        if value <= 0:
            data = self.fps_cb.currentData()
            return data if isinstance(data, int) and data > 0 else 30
        return value

    def _refresh_preview(self) -> None:
        self.preview.set_job(self._current_job())

    def _random_seed(self) -> None:
        import secrets
        self.seed_sb.setValue(secrets.randbelow(2**31 - 1))

    def _pick_output_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Pick output folder", str(self._output_dir))
        if d:
            self._output_dir = Path(d)
            self.out_dir_label.setText(str(self._output_dir))

    def _add_to_queue(self) -> None:
        base = self._current_job()
        self._enqueue(base)
        if self.queue_variations_cb.isChecked():
            import secrets
            for _ in range(5):
                v = self._current_job()
                v.seed = secrets.randbelow(2**31 - 1)
                self._enqueue(v)

    def _enqueue(self, job: RenderJob) -> None:
        job.output = self._output_dir / (job.filename_stem() + ".mp4")
        item = QListWidgetItem(f"{job.style} | {job.palette} | {job.width}x{job.height} | seed={job.seed}")
        item.setData(Qt.UserRole, job)
        self.queue_list.addItem(item)

    def _remove_selected(self) -> None:
        for item in self.queue_list.selectedItems():
            self.queue_list.takeItem(self.queue_list.row(item))

    def _start_render(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if self.queue_list.count() == 0:
            # If queue empty, render the currently configured job.
            base = self._current_job()
            base.output = self._output_dir / (base.filename_stem() + ".mp4")
            self._enqueue(base)
        jobs = [self.queue_list.item(i).data(Qt.UserRole) for i in range(self.queue_list.count())]
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._worker = RenderWorker(jobs)
        self._worker.progress.connect(self._on_progress)
        self._worker.job_started.connect(self._on_job_started)
        self._worker.job_finished.connect(self._on_job_finished)
        self._worker.error.connect(self._on_error)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()
        self.render_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("Rendering…")

    def _cancel_render(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.status_label.setText("Cancelling after current frame…")

    def _on_progress(self, job_idx, total, frame, total_frames) -> None:
        pct = int(100 * (job_idx + frame / max(1, total_frames)) / max(1, total))
        self.progress.setValue(pct)
        self.status_label.setText(f"Job {job_idx + 1}/{total}: frame {frame}/{total_frames}")

    def _on_job_started(self, idx, total, output) -> None:
        self.status_label.setText(f"Starting job {idx + 1}/{total}: {Path(output).name}")

    def _on_job_finished(self, idx, total, output) -> None:
        item = self.queue_list.item(idx)
        if item is not None:
            item.setForeground(Qt.gray)
            item.setText("\u2713  " + item.text())

    def _on_error(self, idx, msg) -> None:
        QMessageBox.critical(self, "Render failed", f"Job {idx + 1} failed:\n{msg}")

    def _on_all_done(self, total) -> None:
        self.progress.setValue(100)
        self.status_label.setText(f"Done. {total} render(s) written to {self._output_dir}")
        self.render_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._worker = None

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Motion Background Studio",
            f"<h3>Motion Background Studio</h3>"
            f"<p>Version {__version__}</p>"
            f"<p>Generate seamless looping motion backgrounds for microstock.</p>"
            f"<p>Powered by ffmpeg.</p>",
        )
