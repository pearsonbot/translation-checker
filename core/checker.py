"""翻译校验核心调度器，支持断点续传、暂停/停止。"""

import json
import os
import time
import logging
import threading
from datetime import datetime

from core.api_client import LLMClient
from core.prompts import get_prompt, format_prompt

logger = logging.getLogger(__name__)


class CheckerState:
    """校验状态枚举。"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    ERROR = "error"


class TranslationChecker:
    """翻译校验调度器。"""

    def __init__(self, checkpoint_dir):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)

        self.state = CheckerState.IDLE
        self.results = []
        self._thread = None
        self._lock = threading.Lock()

        # 回调函数
        self.on_progress = None      # (current, total, result_dict)
        self.on_complete = None      # (results)
        self.on_error = None         # (error_message)
        self.on_state_change = None  # (new_state)
        self.on_log = None           # (message)

    def _set_state(self, state):
        self.state = state
        if self.on_state_change:
            self.on_state_change(state)

    def _log(self, msg):
        logger.info(msg)
        if self.on_log:
            self.on_log(msg)

    def get_checkpoint_path(self, excel_path):
        """根据 Excel 文件名生成 checkpoint 路径。"""
        base = os.path.splitext(os.path.basename(excel_path))[0]
        return os.path.join(self.checkpoint_dir, f"{base}_checkpoint.json")

    def load_checkpoint(self, excel_path):
        """加载断点数据。

        Returns:
            dict or None: {"completed_rows": [...], "results": [...]} 或 None
        """
        cp_path = self.get_checkpoint_path(excel_path)
        if not os.path.exists(cp_path):
            return None
        try:
            with open(cp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.warning(f"加载checkpoint失败: {e}")
            return None

    def save_checkpoint(self, excel_path, completed_rows, results):
        """保存断点数据。"""
        cp_path = self.get_checkpoint_path(excel_path)
        data = {
            "excel_path": excel_path,
            "timestamp": datetime.now().isoformat(),
            "completed_rows": completed_rows,
            "results": results,
        }
        with open(cp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def delete_checkpoint(self, excel_path):
        """删除断点文件。"""
        cp_path = self.get_checkpoint_path(excel_path)
        if os.path.exists(cp_path):
            os.remove(cp_path)

    def start(self, data, excel_path, prompt_name, custom_prompt, api_config,
              resume=False, request_interval=1.0):
        """启动校验任务。

        Args:
            data: Excel 数据列表
            excel_path: Excel 文件路径（用于 checkpoint 命名）
            prompt_name: 提示词模板名称，如果是自定义则为 None
            custom_prompt: 自定义提示词 dict {"system": ..., "user": ...}，非自定义时为 None
            api_config: API 配置 {"base_url", "api_key", "model"}
            resume: 是否从断点续传
            request_interval: 每次 API 调用之间的等待秒数（防止触发频率限制）
        """
        if self.state == CheckerState.RUNNING:
            return

        self._set_state(CheckerState.RUNNING)

        self._thread = threading.Thread(
            target=self._run,
            args=(data, excel_path, prompt_name, custom_prompt, api_config,
                  resume, request_interval),
            daemon=True,
        )
        self._thread.start()

    def pause(self):
        """暂停校验。"""
        if self.state == CheckerState.RUNNING:
            self._set_state(CheckerState.PAUSED)
            self._log("校验已暂停")

    def resume_running(self):
        """恢复校验。"""
        if self.state == CheckerState.PAUSED:
            self._set_state(CheckerState.RUNNING)
            self._log("校验已恢复")

    def stop(self):
        """停止校验。"""
        if self.state in (CheckerState.RUNNING, CheckerState.PAUSED):
            self._set_state(CheckerState.STOPPING)
            self._log("正在停止校验...")

    def _run(self, data, excel_path, prompt_name, custom_prompt, api_config,
             resume, request_interval):
        """校验主循环（在子线程中运行）。"""
        try:
            client = LLMClient(
                base_url=api_config["base_url"],
                api_key=api_config["api_key"],
                model=api_config["model"],
            )

            # 获取提示词模板
            if custom_prompt:
                system_prompt = custom_prompt["system"]
                user_template = custom_prompt["user"]
            else:
                prompt = get_prompt(prompt_name)
                if prompt is None:
                    raise ValueError(f"未找到提示词模板: {prompt_name}")
                system_prompt = prompt["system"]
                user_template = prompt["user"]

            # 加载断点
            completed_rows = set()
            self.results = []
            if resume:
                cp = self.load_checkpoint(excel_path)
                if cp:
                    completed_rows = set(cp["completed_rows"])
                    self.results = cp["results"]
                    self._log(f"从断点恢复，已完成 {len(completed_rows)} 行")

            total = len(data)
            processed = len(completed_rows)

            for item in data:
                # 检查停止信号
                if self.state == CheckerState.STOPPING:
                    self._log(f"校验已停止，已完成 {processed}/{total}")
                    self.save_checkpoint(excel_path,
                                         list(completed_rows), self.results)
                    self._set_state(CheckerState.IDLE)
                    return

                # 等待暂停恢复
                while self.state == CheckerState.PAUSED:
                    time.sleep(0.5)

                if self.state == CheckerState.STOPPING:
                    self._log(f"校验已停止，已完成 {processed}/{total}")
                    self.save_checkpoint(excel_path,
                                         list(completed_rows), self.results)
                    self._set_state(CheckerState.IDLE)
                    return

                # 跳过已完成行
                if item["row"] in completed_rows:
                    continue

                # 构造用户提示词
                user_prompt = format_prompt(
                    user_template, item["source"], item["target"]
                )

                # 请求间隔（第一行不等待）
                if processed > len(completed_rows) and request_interval > 0:
                    time.sleep(request_interval)

                # 调用 API
                self._log(f"正在校验第 {item['row']} 行 ({processed + 1}/{total})...")
                try:
                    result = client.call(system_prompt, user_prompt)
                except Exception as e:
                    result = {
                        "score": 0,
                        "issues": [f"API调用失败: {e}"],
                        "suggestion": "",
                        "summary": "API调用失败",
                    }
                    self._log(f"第 {item['row']} 行校验失败: {e}")

                # 记录结果
                item_result = {
                    "row": item["row"],
                    "source": item["source"],
                    "target": item["target"],
                    "result": result,
                }
                self.results.append(item_result)
                completed_rows.add(item["row"])
                processed += 1

                # 保存断点
                self.save_checkpoint(excel_path,
                                     list(completed_rows), self.results)

                # 回调进度
                if self.on_progress:
                    self.on_progress(processed, total, item_result)

            # 全部完成
            self._log(f"校验完成，共处理 {total} 行")
            self.delete_checkpoint(excel_path)
            self._set_state(CheckerState.COMPLETED)

            if self.on_complete:
                self.on_complete(self.results)

        except Exception as e:
            logger.exception("校验过程发生异常")
            self._log(f"校验异常: {e}")
            self._set_state(CheckerState.ERROR)
            if self.on_error:
                self.on_error(str(e))
