#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Lightweight native desktop UI for the polyglot translation workbench."""

from __future__ import annotations

import queue
import ctypes
import sys
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

import triple_translate as core


def enable_dpi_awareness() -> None:
    """Prevent Windows from bitmap-scaling the Tk window on 125%/150% displays."""
    if sys.platform != "win32":
        return

    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)  # PER_MONITOR_AWARE_V2
        return
    except Exception:
        pass

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


enable_dpi_awareness()


APP_TITLE = "多语翻译工作台"
RECOMMENDED_ENGINES = ["google", "youdao", "alibaba", "bing", "caiyun", "deepl", "yandex"]

COLORS = {
    "bg": "#edf3f0",
    "header": "#123f3a",
    "header_sub": "#cfe5df",
    "card": "#ffffff",
    "card_soft": "#f8fbf9",
    "text": "#17211d",
    "muted": "#63726b",
    "line": "#d8e4de",
    "accent": "#167c6b",
    "accent_dark": "#0f6256",
    "accent_soft": "#e4f2ee",
    "orange": "#e66e38",
    "orange_soft": "#fff1e8",
    "danger": "#b42318",
}


def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


class PolyglotTranslationApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self._apply_tk_scaling()
        self.title(APP_TITLE)
        self.geometry("1120x760")
        self.minsize(960, 640)
        self.configure(bg=COLORS["bg"])
        self._center_window()
        self._set_icon()

        self.mode_var = tk.StringVar(value="fallback")
        self.timeout_var = tk.IntVar(value=12)
        self.status_var = tk.StringVar(value="就绪")
        self.engine_vars: dict[str, tk.BooleanVar] = {}
        self.engine_buttons: dict[str, tk.Checkbutton] = {}
        self.result_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.font_title = ("Microsoft YaHei UI", 20, "bold")
        self.font_section = ("Microsoft YaHei UI", 11, "bold")
        self.font_body = ("Microsoft YaHei UI", 10)
        self.font_small = ("Microsoft YaHei UI", 9)

        self._build_style()
        self._build_ui()
        self.after(120, self._poll_queue)

    def _apply_tk_scaling(self) -> None:
        if sys.platform != "win32":
            return
        try:
            dpi = ctypes.windll.user32.GetDpiForWindow(self.winfo_id())
            self.tk.call("tk", "scaling", dpi / 72)
        except Exception:
            pass

    def _center_window(self) -> None:
        self.update_idletasks()
        width, height = 1120, 760
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _set_icon(self) -> None:
        icon_path = resource_path("assets/app.ico")
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except tk.TclError:
                pass

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Slim.Horizontal.TProgressbar",
            troughcolor=COLORS["accent_soft"],
            background=COLORS["accent"],
            bordercolor=COLORS["accent_soft"],
            lightcolor=COLORS["accent"],
            darkcolor=COLORS["accent"],
        )

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_header()
        self._build_main()
        self._build_footer()

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=COLORS["header"], padx=22, pady=16)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = tk.Label(header, text=APP_TITLE, bg=COLORS["header"], fg="white", font=self.font_title)
        title.grid(row=0, column=0, sticky="w")
        subtitle = tk.Label(
            header,
            text="中文 -> 英文 -> 日文 -> 中文。轻量原生窗口，翻译任务在后台运行。",
            bg=COLORS["header"],
            fg=COLORS["header_sub"],
            font=self.font_small,
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        actions = tk.Frame(header, bg=COLORS["header"])
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        self._button(actions, "示例", self._load_sample, kind="light").pack(side="left", padx=(0, 8))
        self._button(actions, "粘贴", self._paste_text, kind="light").pack(side="left")

    def _build_main(self) -> None:
        main = tk.Frame(self, bg=COLORS["bg"], padx=18, pady=18)
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=11)
        main.columnconfigure(1, weight=13)
        main.rowconfigure(0, weight=1)

        self._build_input_card(main).grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        self._build_result_card(main).grid(row=0, column=1, sticky="nsew", padx=(9, 0))

    def _build_footer(self) -> None:
        footer = tk.Frame(self, bg=COLORS["bg"], padx=18, pady=0)
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        tk.Label(footer, textvariable=self.status_var, bg=COLORS["bg"], fg=COLORS["muted"], font=self.font_small).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(
            footer,
            text="回译结果可能改变原意，提交前请人工核对。",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=self.font_small,
        ).grid(row=0, column=1, sticky="e")

    def _build_input_card(self, parent: tk.Widget) -> tk.Frame:
        card = self._card(parent)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)

        self._section_header(card, "原文输入", "粘贴或输入要处理的中文段落").grid(row=0, column=0, sticky="ew")
        self.source_text = self._text_box(card, height=13)
        self.source_text.grid(row=1, column=0, sticky="nsew", pady=(10, 14))
        self.source_text.focus_set()

        settings = tk.Frame(card, bg=COLORS["card"])
        settings.grid(row=2, column=0, sticky="ew")
        settings.columnconfigure(0, weight=1)
        settings.columnconfigure(1, weight=1)

        mode_card = self._soft_panel(settings)
        mode_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        tk.Label(mode_card, text="运行模式", bg=COLORS["card_soft"], fg=COLORS["text"], font=self.font_section).pack(anchor="w")
        self.fallback_button = self._segment(mode_card, "自动换引擎", "fallback")
        self.fallback_button.pack(fill="x", pady=(10, 6))
        self.compare_button = self._segment(mode_card, "多引擎对比", "compare")
        self.compare_button.pack(fill="x")
        tk.Label(
            mode_card,
            text="对比模式会慢一些，适合比较多个结果。",
            bg=COLORS["card_soft"],
            fg="#8b421d",
            font=self.font_small,
            wraplength=210,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

        timeout_card = self._soft_panel(settings)
        timeout_card.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        tk.Label(timeout_card, text="单次超时", bg=COLORS["card_soft"], fg=COLORS["text"], font=self.font_section).pack(anchor="w")
        spin_row = tk.Frame(timeout_card, bg=COLORS["card_soft"])
        spin_row.pack(anchor="w", pady=(12, 0))
        spin = tk.Spinbox(
            spin_row,
            from_=3,
            to=60,
            textvariable=self.timeout_var,
            width=6,
            font=self.font_body,
            relief="solid",
            bd=1,
            justify="center",
        )
        spin.pack(side="left")
        tk.Label(spin_row, text="秒", bg=COLORS["card_soft"], fg=COLORS["muted"], font=self.font_small).pack(
            side="left", padx=(8, 0)
        )
        tk.Label(
            timeout_card,
            text="公共接口偶尔会慢，默认 12 秒比较稳。",
            bg=COLORS["card_soft"],
            fg=COLORS["muted"],
            font=self.font_small,
            wraplength=210,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))

        engine_panel = self._soft_panel(card)
        engine_panel.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        engine_panel.columnconfigure(0, weight=1)
        tk.Label(engine_panel, text="推荐引擎", bg=COLORS["card_soft"], fg=COLORS["text"], font=self.font_section).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(
            engine_panel,
            text="默认选中常用项，失败时会自动换下一个。",
            bg=COLORS["card_soft"],
            fg=COLORS["muted"],
            font=self.font_small,
        ).grid(row=1, column=0, sticky="w", pady=(3, 10))

        chip_frame = tk.Frame(engine_panel, bg=COLORS["card_soft"])
        chip_frame.grid(row=2, column=0, sticky="ew")
        for index, engine in enumerate(RECOMMENDED_ENGINES):
            var = tk.BooleanVar(value=engine in {"google", "youdao", "alibaba", "caiyun"})
            self.engine_vars[engine] = var
            chip = tk.Checkbutton(
                chip_frame,
                text=engine,
                variable=var,
                indicatoron=False,
                command=lambda name=engine: self._sync_chip(name),
                font=("Segoe UI", 9, "bold"),
                relief="flat",
                bd=0,
                padx=12,
                pady=7,
                cursor="hand2",
            )
            chip.grid(row=index // 4, column=index % 4, sticky="ew", padx=4, pady=4)
            self.engine_buttons[engine] = chip
            self._sync_chip(engine)

        action_row = tk.Frame(card, bg=COLORS["card"])
        action_row.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        action_row.columnconfigure(0, weight=1)
        self.translate_button = self._button(action_row, "开始回译", self._start_translate, kind="primary")
        self.translate_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.clear_button = self._button(action_row, "清空", self._clear_text, kind="ghost")
        self.clear_button.grid(row=0, column=1)

        self._set_mode("fallback")
        return card

    def _build_result_card(self, parent: tk.Widget) -> tk.Frame:
        card = self._card(parent)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=5)
        card.rowconfigure(4, weight=4)

        result_head = tk.Frame(card, bg=COLORS["card"])
        result_head.grid(row=0, column=0, sticky="ew")
        result_head.columnconfigure(0, weight=1)
        self._section_header(result_head, "最终中文结果", "翻译完成后可一键复制").grid(row=0, column=0, sticky="ew")
        self.copy_button = self._button(result_head, "复制结果", self._copy_result, kind="ghost")
        self.copy_button.grid(row=0, column=1, sticky="e")

        self.result_text = self._text_box(card, height=10, bg="#fffefb")
        self.result_text.grid(row=1, column=0, sticky="nsew", pady=(10, 12))

        progress_row = tk.Frame(card, bg=COLORS["card"])
        progress_row.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        progress_row.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_row, mode="indeterminate", style="Slim.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress.grid_remove()

        self._section_header(card, "过程和对比", "查看三步中间结果或每个引擎的结果").grid(row=3, column=0, sticky="ew")
        self.detail_text = self._text_box(card, height=12, bg="#fbfcfb", font=self.font_small)
        self.detail_text.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        self._set_text(self.result_text, "翻译完成后，最终结果会显示在这里。")
        self._set_text(self.detail_text, "这里会显示中文到英文、英文到日文、日文回中文的过程。")
        return card

    def _card(self, parent: tk.Widget) -> tk.Frame:
        return tk.Frame(parent, bg=COLORS["card"], padx=16, pady=16, highlightthickness=1, highlightbackground=COLORS["line"])

    def _soft_panel(self, parent: tk.Widget) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=COLORS["card_soft"],
            padx=12,
            pady=12,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
        )

    def _section_header(self, parent: tk.Widget, title: str, subtitle: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=parent.cget("bg"))
        tk.Label(frame, text=title, bg=parent.cget("bg"), fg=COLORS["text"], font=self.font_section).pack(anchor="w")
        tk.Label(frame, text=subtitle, bg=parent.cget("bg"), fg=COLORS["muted"], font=self.font_small).pack(
            anchor="w", pady=(2, 0)
        )
        return frame

    def _text_box(
        self,
        parent: tk.Widget,
        height: int,
        bg: str = "#ffffff",
        font: tuple[str, int] | tuple[str, int, str] | None = None,
    ) -> tk.Frame:
        wrapper = tk.Frame(parent, bg=COLORS["line"], padx=1, pady=1)
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)
        text = tk.Text(
            wrapper,
            height=height,
            wrap="word",
            undo=True,
            font=font or self.font_body,
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            bg=bg,
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            selectbackground="#b9dbd3",
        )
        scrollbar = tk.Scrollbar(wrapper, command=text.yview, width=12)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        wrapper.text = text  # type: ignore[attr-defined]
        return wrapper

    def _button(self, parent: tk.Widget, text: str, command: Any, kind: str) -> tk.Button:
        styles = {
            "primary": (COLORS["accent"], "white", COLORS["accent_dark"]),
            "ghost": ("#f3f7f5", COLORS["text"], "#e3eee9"),
            "light": ("#ffffff", COLORS["accent_dark"], "#e6f1ed"),
        }
        bg, fg, active = styles[kind]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            font=("Microsoft YaHei UI", 10, "bold"),
            cursor="hand2",
        )

    def _segment(self, parent: tk.Widget, text: str, value: str) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=lambda: self._set_mode(value),
            relief="flat",
            bd=0,
            padx=12,
            pady=8,
            font=self.font_body,
            cursor="hand2",
        )

    def _text_widget(self, wrapper: tk.Frame) -> tk.Text:
        return wrapper.text  # type: ignore[attr-defined]

    def _selected_engines(self) -> list[str]:
        return [engine for engine, var in self.engine_vars.items() if var.get()]

    def _sync_chip(self, engine: str) -> None:
        button = self.engine_buttons[engine]
        if self.engine_vars[engine].get():
            button.configure(bg=COLORS["accent_soft"], fg=COLORS["accent_dark"], activebackground="#d2e9e3")
        else:
            button.configure(bg="#ffffff", fg=COLORS["muted"], activebackground="#edf3f0")

    def _set_mode(self, mode: str) -> None:
        self.mode_var.set(mode)
        selected = (COLORS["accent"], "white")
        normal = ("#ffffff", COLORS["muted"])
        for button, value in ((self.fallback_button, "fallback"), (self.compare_button, "compare")):
            bg, fg = selected if mode == value else normal
            button.configure(bg=bg, fg=fg, activebackground=bg, activeforeground=fg)

    def _set_text(self, wrapper: tk.Frame, text: str) -> None:
        widget = self._text_widget(wrapper)
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def _set_busy(self, busy: bool) -> None:
        self.translate_button.configure(state="disabled" if busy else "normal")
        self.clear_button.configure(state="disabled" if busy else "normal")
        if busy:
            self.status_var.set("正在翻译，请稍候...")
            self.progress.grid()
            self.progress.start(12)
        else:
            self.status_var.set("就绪")
            self.progress.stop()
            self.progress.grid_remove()

    def _load_sample(self) -> None:
        sample = "人工智能生成内容进入高校课程之后，学生写作方式发生了明显变化。它可以帮助学生整理材料和形成初步思路，但如果过度依赖，也会削弱学生对材料的判断和独立表达。"
        self._set_text(self.source_text, sample)
        self._text_widget(self.source_text).focus_set()

    def _paste_text(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo(APP_TITLE, "剪贴板里没有可读取的文本。")
            return
        self._set_text(self.source_text, text)

    def _clear_text(self) -> None:
        self._set_text(self.source_text, "")
        self._set_text(self.result_text, "翻译完成后，最终结果会显示在这里。")
        self._set_text(self.detail_text, "这里会显示中文到英文、英文到日文、日文回中文的过程。")
        self._text_widget(self.source_text).focus_set()

    def _copy_result(self) -> None:
        text = self._text_widget(self.result_text).get("1.0", "end").strip()
        if not text or text.startswith("翻译完成后"):
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("结果已复制到剪贴板")

    def _start_translate(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        text = self._text_widget(self.source_text).get("1.0", "end").strip()
        if not text:
            messagebox.showinfo(APP_TITLE, "请先输入或粘贴一段中文。")
            return

        engines = self._selected_engines()
        if not engines:
            messagebox.showinfo(APP_TITLE, "请至少选择一个翻译引擎。")
            return

        self._set_text(self.result_text, "")
        self._set_text(self.detail_text, "正在加载翻译库并请求公共翻译接口...\n第一次翻译可能会慢一些，但窗口可以继续响应。")
        self._set_busy(True)

        args = (text, engines, float(self.timeout_var.get()), self.mode_var.get())
        self.worker = threading.Thread(target=self._translate_worker, args=args, daemon=True)
        self.worker.start()

    def _translate_worker(self, text: str, engines: list[str], timeout: float, mode: str) -> None:
        started = time.perf_counter()
        try:
            if mode == "compare":
                payload = self._run_compare(text, engines, timeout)
                final = next((item["final"] for item in payload if item["ok"]), "")
                details = self._format_compare(payload)
            else:
                results = core.triple_translate(text, engines, timeout)
                final = results[-1].text
                details = self._format_steps(results)

            elapsed = time.perf_counter() - started
            self.result_queue.put(("success", {"final": final, "details": details, "elapsed": elapsed}))
        except Exception as exc:  # noqa: BLE001
            self.result_queue.put(("error", str(exc)))

    def _run_compare(self, text: str, engines: list[str], timeout: float) -> list[dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=min(3, len(engines))) as executor:
            futures = {executor.submit(core.triple_translate, text, [engine], timeout): engine for engine in engines}
            for future in as_completed(futures):
                engine = futures[future]
                try:
                    steps = future.result()
                    output[engine] = {"engine": engine, "ok": True, "final": steps[-1].text, "steps": steps}
                except Exception as exc:  # noqa: BLE001
                    output[engine] = {"engine": engine, "ok": False, "final": "", "error": str(exc)}
        return [output[engine] for engine in engines]

    def _format_steps(self, steps: list[core.StepResult]) -> str:
        lines: list[str] = []
        for step in steps:
            lines.append(f"[{step.label} / {step.engine}]")
            lines.append(step.text)
            lines.append("")
        return "\n".join(lines).strip()

    def _format_compare(self, items: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for item in items:
            lines.append(f"[{item['engine']}] {'成功' if item['ok'] else '失败'}")
            lines.append(item["final"] if item["ok"] else item.get("error", "不可用"))
            lines.append("")
        return "\n".join(lines).strip()

    def _poll_queue(self) -> None:
        try:
            kind, payload = self.result_queue.get_nowait()
        except queue.Empty:
            self.after(120, self._poll_queue)
            return

        self._set_busy(False)
        if kind == "success":
            self._set_text(self.result_text, payload["final"])
            self._set_text(self.detail_text, payload["details"])
            self.status_var.set(f"完成，用时 {payload['elapsed']:.1f} 秒")
        else:
            self._set_text(self.detail_text, str(payload))
            self.status_var.set("翻译失败")
            messagebox.showerror(APP_TITLE, str(payload))

        self.after(120, self._poll_queue)


def main() -> int:
    try:
        app = PolyglotTranslationApp()
        app.mainloop()
        return 0
    except Exception as exc:  # noqa: BLE001
        log_path = resource_path("native_tk_app_error.log")
        try:
            log_path.write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
