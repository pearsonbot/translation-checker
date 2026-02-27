"""详细结果查看弹窗。"""

import customtkinter as ctk


class ResultViewerDialog(ctk.CTkToplevel):
    """双击表格行时弹出的详细结果查看窗口。"""

    def __init__(self, parent, item_result):
        super().__init__(parent)

        self.title("校验结果详情")
        self.geometry("700x550")
        self.resizable(True, True)
        self.grab_set()

        result = item_result.get("result", {})
        source = item_result.get("source", "")
        target = item_result.get("target", "")
        row = item_result.get("row", "")

        # 主容器
        container = ctk.CTkScrollableFrame(self)
        container.pack(fill="both", expand=True, padx=15, pady=15)

        # 行号与评分
        header_frame = ctk.CTkFrame(container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header_frame, text=f"第 {row} 行", font=("", 16, "bold")
        ).pack(side="left")

        score = result.get("score", "N/A")
        score_color = self._score_color(score)
        ctk.CTkLabel(
            header_frame, text=f"评分: {score}/10",
            font=("", 16, "bold"), text_color=score_color,
        ).pack(side="right")

        # 中文原文
        self._add_section(container, "中文原文", source)

        # 英文译文
        self._add_section(container, "英文译文", target)

        # 总结
        self._add_section(container, "总结", result.get("summary", ""))

        # 问题列表
        issues = result.get("issues", [])
        issues_text = "\n".join(f"  {i+1}. {issue}" for i, issue in enumerate(issues)) if issues else "  无"
        self._add_section(container, "发现的问题", issues_text)

        # 修改建议
        self._add_section(container, "修改建议", result.get("suggestion", ""))

        # 关闭按钮
        ctk.CTkButton(
            self, text="关闭", width=100, command=self.destroy
        ).pack(pady=(0, 15))

    def _add_section(self, parent, title, content):
        """添加一个标题+内容区块。"""
        ctk.CTkLabel(
            parent, text=title, font=("", 13, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(10, 2))

        textbox = ctk.CTkTextbox(parent, height=70, wrap="word")
        textbox.pack(fill="x", pady=(0, 5))
        textbox.insert("1.0", content)
        textbox.configure(state="disabled")

    def _score_color(self, score):
        if not isinstance(score, (int, float)):
            return "gray"
        if score >= 8:
            return "#2ecc71"
        if score >= 6:
            return "#f39c12"
        return "#e74c3c"
