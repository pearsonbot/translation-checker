"""主窗口界面。"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import threading

import customtkinter as ctk

from core.checker import TranslationChecker, CheckerState
from core.excel_handler import read_excel, write_results_to_excel, write_independent_report
from core.prompts import get_prompt_names, BUILTIN_PROMPTS
from gui.settings_dialog import SettingsDialog
from gui.result_viewer import ResultViewerDialog


class MainApp(ctk.CTk):
    """翻译校验工具主窗口。"""

    def __init__(self, config, config_path, base_dir):
        super().__init__()

        self.config = config
        self.config_path = config_path
        self.base_dir = base_dir

        self.title("翻译校验工具")
        self.geometry("1000x750")
        self.minsize(800, 600)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # 校验器
        checkpoint_dir = os.path.join(base_dir, "checkpoints")
        self.checker = TranslationChecker(checkpoint_dir)
        self.checker.on_progress = self._on_progress
        self.checker.on_complete = self._on_complete
        self.checker.on_error = self._on_error
        self.checker.on_state_change = self._on_state_change
        self.checker.on_log = self._on_log

        # 数据
        self.excel_data = []
        self.all_results = []  # 用于结果展示和导出

        self._build_ui()

    def _build_ui(self):
        # ── 顶部标题栏 ──
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(
            title_frame, text="翻译校验工具",
            font=("", 20, "bold"),
        ).pack(side="left")

        ctk.CTkButton(
            title_frame, text="设置", width=70,
            command=self._open_settings,
        ).pack(side="right")

        # ── 文件选择区 ──
        file_frame = ctk.CTkFrame(self)
        file_frame.pack(fill="x", padx=15, pady=5)

        # Excel 文件
        row1 = ctk.CTkFrame(file_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row1, text="Excel文件:", width=80, anchor="e").pack(side="left")
        self.file_path_var = ctk.StringVar()
        ctk.CTkEntry(row1, textvariable=self.file_path_var, state="readonly").pack(
            side="left", fill="x", expand=True, padx=5
        )
        ctk.CTkButton(row1, text="选择文件", width=80, command=self._select_file).pack(side="right")

        # 提示词选择
        row2 = ctk.CTkFrame(file_frame, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row2, text="提示词:", width=80, anchor="e").pack(side="left")

        prompt_names = self._get_all_prompt_names()
        self.prompt_var = ctk.StringVar(value=prompt_names[0] if prompt_names else "")
        self.prompt_menu = ctk.CTkOptionMenu(
            row2, variable=self.prompt_var, values=prompt_names, width=250,
        )
        self.prompt_menu.pack(side="left", padx=5)

        # 输出目录
        row3 = ctk.CTkFrame(file_frame, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row3, text="输出目录:", width=80, anchor="e").pack(side="left")
        self.output_dir_var = ctk.StringVar()
        ctk.CTkEntry(row3, textvariable=self.output_dir_var, state="readonly").pack(
            side="left", fill="x", expand=True, padx=5
        )
        ctk.CTkButton(row3, text="选择目录", width=80, command=self._select_output_dir).pack(side="right")

        # ── 控制栏 ──
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=15, pady=5)

        self.start_btn = ctk.CTkButton(
            ctrl_frame, text="开始校验", width=100,
            fg_color="#2ecc71", hover_color="#27ae60",
            command=self._start_check,
        )
        self.start_btn.pack(side="left", padx=5)

        self.pause_btn = ctk.CTkButton(
            ctrl_frame, text="暂停", width=80,
            fg_color="#f39c12", hover_color="#e67e22",
            command=self._toggle_pause, state="disabled",
        )
        self.pause_btn.pack(side="left", padx=5)

        self.stop_btn = ctk.CTkButton(
            ctrl_frame, text="停止", width=80,
            fg_color="#e74c3c", hover_color="#c0392b",
            command=self._stop_check, state="disabled",
        )
        self.stop_btn.pack(side="left", padx=5)

        # 进度
        progress_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        progress_frame.pack(side="right", fill="x", expand=True, padx=10)

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", pady=(0, 2))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            progress_frame, text="就绪", anchor="w", font=("", 12),
        )
        self.status_label.pack(fill="x")

        # ── 结果表格 ──
        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=15, pady=5)

        ctk.CTkLabel(
            table_frame, text="结果预览 (双击查看详情)",
            font=("", 13, "bold"), anchor="w",
        ).pack(fill="x", padx=10, pady=(5, 2))

        # 使用 tkinter Treeview（CustomTkinter 没有原生表格）
        tree_container = ctk.CTkFrame(table_frame)
        tree_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("row", "source", "target", "score", "summary")
        self.tree = ttk.Treeview(
            tree_container, columns=columns, show="headings", height=12,
        )
        self.tree.heading("row", text="行号")
        self.tree.heading("source", text="中文原文")
        self.tree.heading("target", text="英文译文")
        self.tree.heading("score", text="评分")
        self.tree.heading("summary", text="问题摘要")

        self.tree.column("row", width=50, minwidth=40, anchor="center")
        self.tree.column("source", width=250, minwidth=100)
        self.tree.column("target", width=250, minwidth=100)
        self.tree.column("score", width=50, minwidth=40, anchor="center")
        self.tree.column("summary", width=250, minwidth=100)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # 配置 Treeview 的标签样式
        self.tree.tag_configure("low_score", foreground="red")
        self.tree.tag_configure("mid_score", foreground="orange")
        self.tree.tag_configure("high_score", foreground="green")

        # ── 日志区域 ──
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(
            log_frame, text="日志", font=("", 12, "bold"), anchor="w",
        ).pack(fill="x", padx=10, pady=(5, 2))

        self.log_textbox = ctk.CTkTextbox(log_frame, height=100, wrap="word")
        self.log_textbox.pack(fill="x", padx=10, pady=(0, 10))
        self.log_textbox.configure(state="disabled")

    # ── 提示词列表 ──

    def _get_all_prompt_names(self):
        names = list(get_prompt_names())
        for name in self.config.get("custom_prompts", {}):
            if name not in names:
                names.append(name)
        return names

    def _refresh_prompt_menu(self):
        names = self._get_all_prompt_names()
        self.prompt_menu.configure(values=names)
        if self.prompt_var.get() not in names and names:
            self.prompt_var.set(names[0])

    # ── 文件选择 ──

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="选择 Excel 文件",
            filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")],
        )
        if path:
            self.file_path_var.set(path)
            # 默认输出目录为文件所在目录
            if not self.output_dir_var.get():
                self.output_dir_var.set(os.path.dirname(path))
            self._log_message(f"已选择文件: {path}")

    def _select_output_dir(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir_var.set(path)

    # ── 设置 ──

    def _open_settings(self):
        dialog = SettingsDialog(self, self.config, self.config_path)
        self.wait_window(dialog)
        if dialog.result:
            self.config = dialog.result
            self._refresh_prompt_menu()
            self._log_message("设置已更新")

    # ── 校验控制 ──

    def _start_check(self):
        # 验证输入
        excel_path = self.file_path_var.get()
        if not excel_path or not os.path.exists(excel_path):
            messagebox.showerror("错误", "请先选择有效的 Excel 文件")
            return

        if not self.config.get("base_url") or not self.config.get("api_key") or not self.config.get("model"):
            messagebox.showerror("错误", "请先在设置中配置 API（Base URL、API Key、模型名称）")
            return

        output_dir = self.output_dir_var.get()
        if not output_dir:
            output_dir = os.path.dirname(excel_path)
            self.output_dir_var.set(output_dir)

        # 读取 Excel
        try:
            self.excel_data = read_excel(excel_path)
            if not self.excel_data:
                messagebox.showerror("错误", "Excel 文件中没有找到有效数据")
                return
            self._log_message(f"读取到 {len(self.excel_data)} 行数据")
        except Exception as e:
            messagebox.showerror("错误", f"读取 Excel 失败: {e}")
            return

        # 检查断点
        resume = False
        cp = self.checker.load_checkpoint(excel_path)
        if cp:
            completed = len(cp.get("completed_rows", []))
            total = len(self.excel_data)
            answer = messagebox.askyesnocancel(
                "检测到断点",
                f"检测到未完成的任务 ({completed}/{total})。\n\n"
                f"点击「是」继续上次任务\n"
                f"点击「否」重新开始\n"
                f"点击「取消」放弃操作",
            )
            if answer is None:
                return
            resume = answer
            if not resume:
                self.checker.delete_checkpoint(excel_path)

        # 获取提示词配置
        prompt_name = self.prompt_var.get()
        custom_prompt = None

        # 检查是否是自定义/修改过的提示词
        custom_prompts = self.config.get("custom_prompts", {})
        if prompt_name in custom_prompts:
            custom_prompt = custom_prompts[prompt_name]

        api_config = {
            "base_url": self.config["base_url"],
            "api_key": self.config["api_key"],
            "model": self.config["model"],
        }

        # 清空表格（如果不是续传）
        if not resume:
            self.tree.delete(*self.tree.get_children())
            self.all_results = []
        else:
            # 恢复已有结果到表格
            if cp and cp.get("results"):
                self.all_results = cp["results"]
                for r in self.all_results:
                    self._insert_tree_row(r)

        # 更新按钮状态
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")

        self.checker.start(
            self.excel_data, excel_path, prompt_name,
            custom_prompt, api_config, resume=resume,
        )

    def _toggle_pause(self):
        if self.checker.state == CheckerState.RUNNING:
            self.checker.pause()
            self.pause_btn.configure(text="继续")
        elif self.checker.state == CheckerState.PAUSED:
            self.checker.resume_running()
            self.pause_btn.configure(text="暂停")

    def _stop_check(self):
        self.checker.stop()

    # ── 回调（从子线程调用，需要 after 调度到主线程） ──

    def _on_progress(self, current, total, item_result):
        self.after(0, self._update_progress, current, total, item_result)

    def _on_complete(self, results):
        self.after(0, self._handle_complete, results)

    def _on_error(self, error_msg):
        self.after(0, lambda: messagebox.showerror("校验错误", error_msg))
        self.after(0, self._reset_buttons)

    def _on_state_change(self, new_state):
        self.after(0, self._handle_state_change, new_state)

    def _on_log(self, message):
        self.after(0, self._log_message, message)

    def _update_progress(self, current, total, item_result):
        progress = current / total if total > 0 else 0
        self.progress_bar.set(progress)
        self.status_label.configure(text=f"已完成 {current}/{total} ({progress*100:.0f}%)")

        # 添加到结果列表和表格
        self.all_results.append(item_result)
        self._insert_tree_row(item_result)

    def _insert_tree_row(self, item_result):
        result = item_result.get("result", {})
        score = result.get("score", "")
        summary = result.get("summary", "")
        source = item_result.get("source", "")[:50]
        target = item_result.get("target", "")[:50]

        tag = "high_score"
        if isinstance(score, int):
            if score <= 5:
                tag = "low_score"
            elif score <= 7:
                tag = "mid_score"

        self.tree.insert(
            "", "end",
            values=(item_result["row"], source, target, score, summary),
            tags=(tag,),
        )
        # 自动滚动到底部
        children = self.tree.get_children()
        if children:
            self.tree.see(children[-1])

    def _handle_complete(self, results):
        self._reset_buttons()
        self.progress_bar.set(1.0)
        self.status_label.configure(text="校验完成!")

        # 生成输出文件
        excel_path = self.file_path_var.get()
        output_dir = self.output_dir_var.get()
        base_name = os.path.splitext(os.path.basename(excel_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        checked_path = os.path.join(output_dir, f"{base_name}_checked_{timestamp}.xlsx")
        report_path = os.path.join(output_dir, f"{base_name}_report_{timestamp}.xlsx")

        try:
            write_results_to_excel(excel_path, results, checked_path)
            self._log_message(f"结果已写入: {checked_path}")
        except Exception as e:
            self._log_message(f"写入结果Excel失败: {e}")

        try:
            write_independent_report(self.excel_data, results, report_path)
            self._log_message(f"独立报告已生成: {report_path}")
        except Exception as e:
            self._log_message(f"生成报告失败: {e}")

        messagebox.showinfo(
            "校验完成",
            f"校验完成，共处理 {len(results)} 行。\n\n"
            f"结果文件:\n{checked_path}\n\n"
            f"独立报告:\n{report_path}",
        )

    def _handle_state_change(self, new_state):
        if new_state in (CheckerState.IDLE, CheckerState.ERROR):
            self._reset_buttons()

    def _reset_buttons(self):
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="暂停")
        self.stop_btn.configure(state="disabled")

    # ── 结果详情 ──

    def _on_tree_double_click(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        row_num = int(item["values"][0])  # Treeview 返回字符串，转为 int

        # 查找对应结果
        for r in self.all_results:
            if r["row"] == row_num:
                ResultViewerDialog(self, r)
                return

    # ── 日志 ──

    def _log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
