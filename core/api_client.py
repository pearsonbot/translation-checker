"""LLM API 客户端，使用 requests 直接调用 OpenAI 兼容接口。"""

import json
import time
import logging

import requests

logger = logging.getLogger(__name__)

# 预置服务商配置
PRESET_PROVIDERS = {
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "通义千问": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "Moonshot (Kimi)": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
    },
    "智谱 (GLM)": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4",
    },
    "自定义": {
        "base_url": "",
        "default_model": "",
    },
}


class LLMClient:
    """LLM API 客户端，支持 OpenAI 兼容接口。"""

    def __init__(self, base_url, api_key, model, timeout=60, max_retries=3,
                 on_log=None):
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.on_log = on_log

        # 智能拼接 URL：兼容用户填写各种格式的 base_url
        self.api_url = self._build_url(base_url)
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        logger.info(f"LLMClient 已初始化: url={self.api_url}, model={model}")

    def _log(self, msg):
        """同时写入 logging 和 UI 回调。"""
        logger.info(msg)
        if self.on_log:
            self.on_log(msg)

    @staticmethod
    def _build_url(base_url):
        """根据用户输入的 base_url 构建完整的 chat/completions 端点。

        兼容以下输入格式：
          - https://api.deepseek.com/v1
          - https://api.deepseek.com/v1/
          - https://api.deepseek.com/v1/chat/completions
          - https://api.deepseek.com/v1/chat/completions/
        """
        url = base_url.strip().rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/chat"):
            return url + "/completions"
        return url + "/chat/completions"

    def _request(self, messages, max_tokens=None):
        """发送请求到 API 并返回原始响应 JSON。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        response = requests.post(
            url=self.api_url,
            headers=self.headers,
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def call(self, system_prompt, user_prompt):
        """调用 LLM API，返回解析后的 JSON 结果。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词

        Returns:
            dict: 解析后的结果，包含 score, issues, suggestion, summary
            如果解析失败则返回原始文本的包装结果

        Raises:
            Exception: API 调用失败且重试耗尽时抛出
        """
        last_error = None
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        rate_limit_retries = 0
        max_rate_limit_retries = 5
        attempt = 0

        while attempt < self.max_retries:
            attempt += 1
            try:
                logger.info(f"API调用 (第{attempt}次尝试)")
                result = self._request(messages)
                content = result["choices"][0]["message"]["content"].strip()
                return self._parse_response(content)

            except requests.exceptions.HTTPError as e:
                last_error = e
                status = e.response.status_code if e.response is not None else "N/A"
                body = ""
                try:
                    body = e.response.text[:200]
                except Exception:
                    pass

                # 429 频率限制：读取 Retry-After，不消耗普通重试次数
                if e.response is not None and e.response.status_code == 429:
                    rate_limit_retries += 1
                    if rate_limit_retries > max_rate_limit_retries:
                        self._log("触发频率限制次数过多，放弃重试")
                        break
                    retry_after = e.response.headers.get("Retry-After")
                    wait = int(retry_after) if retry_after and retry_after.isdigit() else 10
                    wait = min(wait, 60)  # 上限 60 秒
                    self._log(
                        f"触发频率限制 (429)，等待 {wait} 秒后重试 "
                        f"({rate_limit_retries}/{max_rate_limit_retries})"
                    )
                    time.sleep(wait)
                    attempt -= 1  # 429 不消耗普通重试次数
                    continue

                logger.warning(
                    f"API调用失败 (第{attempt}次): HTTP {status} "
                    f"URL={self.api_url} 响应={body}"
                )
                # 其他 4xx 客户端错误（如 401 认证失败、404 路径错误）不重试
                if e.response is not None and 400 <= e.response.status_code < 500:
                    break
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.info(f"等待 {wait} 秒后重试...")
                    time.sleep(wait)

            except Exception as e:
                last_error = e
                logger.warning(
                    f"API调用失败 (第{attempt}次): {type(e).__name__}: {e}"
                )
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.info(f"等待 {wait} 秒后重试...")
                    time.sleep(wait)

        raise Exception(
            f"API调用失败，已重试{self.max_retries}次: "
            f"{type(last_error).__name__}: {last_error}"
        )

    @staticmethod
    def _extract_json(content):
        """提取内容中的 JSON 文本（去除 markdown 代码块包裹）。"""
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            return content[start:end].strip()
        if "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            return content[start:end].strip()
        return content

    def _parse_response(self, content):
        """解析 LLM 返回的 JSON 内容。"""
        content = self._extract_json(content)

        try:
            result = json.loads(content)
            # 验证必需字段
            required = {"score", "issues", "suggestion", "summary"}
            if required.issubset(result.keys()):
                result["score"] = int(result["score"])
                if not isinstance(result["issues"], list):
                    result["issues"] = [str(result["issues"])]
                return result
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        # 解析失败，返回包装结果
        logger.warning("JSON解析失败，返回原始文本")
        return {
            "score": 0,
            "issues": ["返回格式异常，无法解析"],
            "suggestion": content,
            "summary": "模型返回格式异常，请查看建议列中的原始输出",
        }

    def _parse_batch_response(self, content, expected_count):
        """解析 LLM 返回的批量 JSON 数组。

        Args:
            content: LLM 返回的原始文本
            expected_count: 期望的结果数量

        Returns:
            list[dict] or None: 成功时返回结果列表（按 id 排序），失败返回 None
        """
        content = self._extract_json(content)

        try:
            results = json.loads(content)
            if not isinstance(results, list):
                logger.warning("批量解析: 返回不是数组")
                return None
            if len(results) != expected_count:
                logger.warning(
                    f"批量解析: 期望 {expected_count} 条，实际 {len(results)} 条"
                )
                return None

            required = {"id", "score", "issues", "suggestion", "summary"}
            parsed = []
            for item in results:
                if not required.issubset(item.keys()):
                    logger.warning(f"批量解析: 缺少必需字段, keys={list(item.keys())}")
                    return None
                item["score"] = int(item["score"])
                if not isinstance(item["issues"], list):
                    item["issues"] = [str(item["issues"])]
                parsed.append(item)

            parsed.sort(key=lambda x: x["id"])
            return parsed
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"批量JSON解析失败: {e}")
            return None

    def call_batch(self, system_prompt, user_prompt, expected_count):
        """批量调用 LLM API，返回解析后的 JSON 数组。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            expected_count: 期望返回的结果数量

        Returns:
            list[dict] or None: 成功时返回结果列表，解析失败返回 None

        Raises:
            Exception: API 调用失败且重试耗尽时抛出
        """
        last_error = None
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        rate_limit_retries = 0
        max_rate_limit_retries = 5
        attempt = 0

        while attempt < self.max_retries:
            attempt += 1
            try:
                self._log(f"批量API调用 (第{attempt}次尝试, {expected_count}条)")
                result = self._request(messages)
                content = result["choices"][0]["message"]["content"].strip()
                parsed = self._parse_batch_response(content, expected_count)
                if parsed is not None:
                    return parsed
                # 解析失败但 API 本身成功，返回 None 让调用方回退
                logger.warning("批量返回解析失败，将回退为逐行处理")
                return None

            except requests.exceptions.HTTPError as e:
                last_error = e
                status = e.response.status_code if e.response is not None else "N/A"
                body = ""
                try:
                    body = e.response.text[:200]
                except Exception:
                    pass

                if e.response is not None and e.response.status_code == 429:
                    rate_limit_retries += 1
                    if rate_limit_retries > max_rate_limit_retries:
                        self._log("触发频率限制次数过多，放弃重试")
                        break
                    retry_after = e.response.headers.get("Retry-After")
                    wait = int(retry_after) if retry_after and retry_after.isdigit() else 10
                    wait = min(wait, 60)
                    self._log(
                        f"触发频率限制 (429)，等待 {wait} 秒后重试 "
                        f"({rate_limit_retries}/{max_rate_limit_retries})"
                    )
                    time.sleep(wait)
                    attempt -= 1
                    continue

                logger.warning(
                    f"批量API调用失败 (第{attempt}次): HTTP {status} "
                    f"URL={self.api_url} 响应={body}"
                )
                if e.response is not None and 400 <= e.response.status_code < 500:
                    break
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.info(f"等待 {wait} 秒后重试...")
                    time.sleep(wait)

            except Exception as e:
                last_error = e
                logger.warning(
                    f"批量API调用失败 (第{attempt}次): {type(e).__name__}: {e}"
                )
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.info(f"等待 {wait} 秒后重试...")
                    time.sleep(wait)

        raise Exception(
            f"批量API调用失败，已重试{self.max_retries}次: "
            f"{type(last_error).__name__}: {last_error}"
        )

    def test_connection(self):
        """测试 API 连接是否正常。

        Returns:
            tuple: (成功: bool, 消息: str)
        """
        try:
            messages = [{"role": "user", "content": "Hi, respond with 'OK'"}]
            self._request(messages, max_tokens=10)
            return True, f"连接成功，模型: {self.model}\n请求地址: {self.api_url}"
        except requests.exceptions.ConnectionError as e:
            logger.error(f"连接错误 (网络/代理/DNS): URL={self.api_url} {e}")
            return False, f"连接失败 (网络错误)\n请求地址: {self.api_url}"
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "N/A"
            body = ""
            try:
                body = e.response.text[:200]
            except Exception:
                pass
            logger.error(f"HTTP错误: {status} URL={self.api_url} 响应={body}")
            return False, (
                f"连接失败 (HTTP {status})\n"
                f"请求地址: {self.api_url}\n"
                f"服务器响应: {body[:100] if body else '无'}"
            )
        except requests.exceptions.Timeout as e:
            logger.error(f"连接超时: URL={self.api_url}")
            return False, f"连接失败 (超时)\n请求地址: {self.api_url}"
        except Exception as e:
            logger.error(f"连接失败: {type(e).__name__}: {e}")
            return False, f"连接失败: {type(e).__name__}: {e}\n请求地址: {self.api_url}"
