"""设置对话框：API 配置 + 提示词管理。"""

import json
import threading
import customtkinter as ctk
from core.api_client import PRESET_PROVIDERS, LLMClient
from core.prompts import BUILTIN_PROMPTS


class SettingsDialog(ctk.CTkToplevel):
    """设置对话框。"""

    def __init__(self, parent, config, config_path):
        super().__init__(parent)

        self.title("设置")
        self.geometry("650x580")
        self.resizable(False, False)
        self.grab_set()

        self.config = config
        self.config_path = config_path
        self.result = None  # 保存后返回给主窗口

        # 选项卡
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(15, 5))

        self._build_api_tab(self.tabview.add("API 配置"))
        self._build_prompt_tab(self.tabview.add("提示词管理"))

        # 底部按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(5, 15))

        ctk.CTkButton(btn_frame, text="保存", width=100, command=self._save).pack(
            side="right", padx=(5, 0)
        )
        ctk.CTkButton(
            btn_frame, text="取消", width=100, fg_color="gray",
            command=self.destroy,
        ).pack(side="right")

    # ── API 配置 ──

    def _build_api_tab(self, tab):
        # 服务商选择
        ctk.CTkLabel(tab, text="服务商:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.provider_var = ctk.StringVar(value=self.config.get("provider", "自定义"))
        provider_menu = ctk.CTkOptionMenu(
            tab, variable=self.provider_var,
            values=list(PRESET_PROVIDERS.keys()),
            command=self._on_provider_change,
        )
        provider_menu.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        # Base URL
        ctk.CTkLabel(tab, text="Base URL:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.base_url_var = ctk.StringVar(value=self.config.get("base_url", ""))
        ctk.CTkEntry(tab, textvariable=self.base_url_var, width=400).grid(
            row=1, column=1, sticky="ew", pady=5, padx=5
        )

        # API Key
        ctk.CTkLabel(tab, text="API Key:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
        self.api_key_var = ctk.StringVar(value=self.config.get("api_key", ""))
        ctk.CTkEntry(tab, textvariable=self.api_key_var, show="*", width=400).grid(
            row=2, column=1, sticky="ew", pady=5, padx=5
        )

        # 模型名称
        ctk.CTkLabel(tab, text="模型:").grid(row=3, column=0, sticky="w", pady=5, padx=5)
        self.model_var = ctk.StringVar(value=self.config.get("model", ""))
        ctk.CTkEntry(tab, textvariable=self.model_var, width=400).grid(
            row=3, column=1, sticky="ew", pady=5, padx=5
        )

        # 请求间隔
        ctk.CTkLabel(tab, text="请求间隔(秒):").grid(row=4, column=0, sticky="w", pady=5, padx=5)
        interval_frame = ctk.CTkFrame(tab, fg_color="transparent")
        interval_frame.grid(row=4, column=1, sticky="w", pady=5, padx=5)
        self.interval_var = ctk.StringVar(
            value=str(self.config.get("request_interval", 1.0))
        )
        ctk.CTkEntry(interval_frame, textvariable=self.interval_var, width=80).pack(
            side="left"
        )
        ctk.CTkLabel(
            interval_frame, text="  每次API调用后等待的秒数，防止触发频率限制",
            text_color="gray",
        ).pack(side="left")

        # 测试连接按钮
        self.test_btn = ctk.CTkButton(tab, text="测试连接", command=self._test_connection)
        self.test_btn.grid(row=5, column=1, sticky="w", pady=10, padx=5)

        self.test_label = ctk.CTkLabel(tab, text="", text_color="gray")
        self.test_label.grid(row=6, column=0, columnspan=2, sticky="w", padx=5)

        tab.grid_columnconfigure(1, weight=1)

    def _on_provider_change(self, provider_name):
        preset = PRESET_PROVIDERS.get(provider_name, {})
        if preset.get("base_url"):
            self.base_url_var.set(preset["base_url"])
        if preset.get("default_model"):
            self.model_var.set(preset["default_model"])

    def _test_connection(self):
        self.test_label.configure(text="正在测试...", text_color="gray")
        self.test_btn.configure(state="disabled")

        def _do_test():
            try:
                client = LLMClient(
                    base_url=self.base_url_var.get(),
                    api_key=self.api_key_var.get(),
                    model=self.model_var.get(),
                )
                ok, msg = client.test_connection()
                color = "#2ecc71" if ok else "#e74c3c"
                self.after(0, lambda: self.test_label.configure(text=msg, text_color=color))
            except Exception as e:
                self.after(0, lambda: self.test_label.configure(
                    text=f"连接失败: {e}", text_color="#e74c3c"))
            finally:
                self.after(0, lambda: self.test_btn.configure(state="normal"))

        threading.Thread(target=_do_test, daemon=True).start()

    # ── 提示词管理 ──

    def _build_prompt_tab(self, tab):
        # 左侧：提示词列表
        left_frame = ctk.CTkFrame(tab)
        left_frame.pack(side="left", fill="y", padx=(0, 5), pady=5)

        ctk.CTkLabel(left_frame, text="提示词模板", font=("", 13, "bold")).pack(pady=5)

        self.prompt_listbox = ctk.CTkScrollableFrame(left_frame, width=150, height=350)
        self.prompt_listbox.pack(fill="both", expand=True, padx=5, pady=5)

        # 加载所有提示词（内置 + 自定义）
        self.all_prompts = {}
        for name, prompt in BUILTIN_PROMPTS.items():
            self.all_prompts[name] = {
                "system": prompt["system"],
                "user": prompt["user"],
                "builtin": True,
            }
        for name, prompt in self.config.get("custom_prompts", {}).items():
            is_modified_builtin = prompt.get("modified_builtin", False)
            if is_modified_builtin and name in self.all_prompts:
                # 内置模板被用户修改过，保留 builtin 标记但使用修改后的内容
                self.all_prompts[name]["system"] = prompt.get("system", "")
                self.all_prompts[name]["user"] = prompt.get("user", "")
            elif name not in self.all_prompts:
                # 纯自定义模板
                self.all_prompts[name] = {
                    "system": prompt.get("system", ""),
                    "user": prompt.get("user", ""),
                    "builtin": False,
                }

        self.prompt_buttons = {}
        self.selected_prompt_name = None
        for name in self.all_prompts:
            btn = ctk.CTkButton(
                self.prompt_listbox, text=name, width=140, height=30,
                fg_color="transparent", text_color=("gray10", "gray90"),
                anchor="w",
                command=lambda n=name: self._select_prompt(n),
            )
            btn.pack(fill="x", pady=1)
            self.prompt_buttons[name] = btn

        # 添加/删除按钮
        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(
            btn_frame, text="+", width=30, command=self._add_prompt
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            btn_frame, text="-", width=30, fg_color="#e74c3c",
            command=self._delete_prompt,
        ).pack(side="left", padx=2)

        # 右侧：编辑区域
        right_frame = ctk.CTkFrame(tab)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0), pady=5)

        ctk.CTkLabel(right_frame, text="系统提示词:", anchor="w").pack(fill="x", padx=5, pady=(5, 2))
        self.system_textbox = ctk.CTkTextbox(right_frame, height=120, wrap="word")
        self.system_textbox.pack(fill="x", padx=5, pady=(0, 5))

        ctk.CTkLabel(right_frame, text="用户提示词 (用 {source_text} 和 {target_text} 作为占位符):",
                      anchor="w").pack(fill="x", padx=5, pady=(5, 2))
        self.user_textbox = ctk.CTkTextbox(right_frame, height=180, wrap="word")
        self.user_textbox.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # 默认选中第一个
        if self.all_prompts:
            first = list(self.all_prompts.keys())[0]
            self._select_prompt(first)

    def _select_prompt(self, name):
        # 保存当前编辑
        if self.selected_prompt_name and self.selected_prompt_name in self.all_prompts:
            self._save_current_prompt_edits()

        self.selected_prompt_name = name
        prompt = self.all_prompts[name]

        # 更新高亮
        for n, btn in self.prompt_buttons.items():
            if n == name:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")

        # 加载内容
        self.system_textbox.configure(state="normal")
        self.system_textbox.delete("1.0", "end")
        self.system_textbox.insert("1.0", prompt["system"])

        self.user_textbox.configure(state="normal")
        self.user_textbox.delete("1.0", "end")
        self.user_textbox.insert("1.0", prompt["user"])

    def _save_current_prompt_edits(self):
        """将当前编辑器内容保存回 all_prompts。"""
        if not self.selected_prompt_name:
            return
        self.all_prompts[self.selected_prompt_name]["system"] = \
            self.system_textbox.get("1.0", "end").strip()
        self.all_prompts[self.selected_prompt_name]["user"] = \
            self.user_textbox.get("1.0", "end").strip()

    def _add_prompt(self):
        dialog = ctk.CTkInputDialog(text="请输入提示词名称:", title="新增提示词")
        name = dialog.get_input()
        if not name or name in self.all_prompts:
            return
        self.all_prompts[name] = {"system": "", "user": "", "builtin": False}
        btn = ctk.CTkButton(
            self.prompt_listbox, text=name, width=140, height=30,
            fg_color="transparent", text_color=("gray10", "gray90"),
            anchor="w",
            command=lambda n=name: self._select_prompt(n),
        )
        btn.pack(fill="x", pady=1)
        self.prompt_buttons[name] = btn
        self._select_prompt(name)

    def _delete_prompt(self):
        if not self.selected_prompt_name:
            return
        if self.all_prompts[self.selected_prompt_name].get("builtin"):
            return  # 不删除内置
        name = self.selected_prompt_name
        self.prompt_buttons[name].destroy()
        del self.prompt_buttons[name]
        del self.all_prompts[name]
        self.selected_prompt_name = None
        if self.all_prompts:
            self._select_prompt(list(self.all_prompts.keys())[0])

    # ── 保存 ──

    def _save(self):
        self._save_current_prompt_edits()

        self.config["provider"] = self.provider_var.get()
        self.config["base_url"] = self.base_url_var.get()
        self.config["api_key"] = self.api_key_var.get()
        self.config["model"] = self.model_var.get()
        try:
            self.config["request_interval"] = max(0, float(self.interval_var.get()))
        except ValueError:
            self.config["request_interval"] = 1.0

        # 保存自定义提示词 (包含对内置提示词的修改)
        custom_prompts = {}
        for name, prompt in self.all_prompts.items():
            if not prompt.get("builtin"):
                custom_prompts[name] = {
                    "system": prompt["system"],
                    "user": prompt["user"],
                }
            else:
                # 检查内置模板是否被修改过
                builtin = BUILTIN_PROMPTS.get(name)
                if builtin and (prompt["system"] != builtin["system"]
                                or prompt["user"] != builtin["user"]):
                    custom_prompts[name] = {
                        "system": prompt["system"],
                        "user": prompt["user"],
                        "modified_builtin": True,
                    }
        self.config["custom_prompts"] = custom_prompts

        # 写入配置文件
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showwarning("警告", f"配置保存到文件失败: {e}\n当前会话配置仍然有效。")

        self.result = self.config
        self.destroy()
