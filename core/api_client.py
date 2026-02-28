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

    def __init__(self, base_url, api_key, model, timeout=60, max_retries=3):
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

        # 规范化 base_url：去除尾部多余斜杠，拼接完整端点
        self.api_url = base_url.rstrip("/") + "/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        logger.info(f"LLMClient 已初始化: url={self.api_url}, model={model}")

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

        for attempt in range(1, self.max_retries + 1):
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
                logger.warning(
                    f"API调用失败 (第{attempt}次): HTTP {status}: {body}"
                )
                # 4xx 客户端错误（如 401 认证失败）不需要重试
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

    def _parse_response(self, content):
        """解析 LLM 返回的 JSON 内容。"""
        # 尝试提取 JSON 块（有些模型会用 ```json 包裹）
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            content = content[start:end].strip()

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

    def test_connection(self):
        """测试 API 连接是否正常。

        Returns:
            tuple: (成功: bool, 消息: str)
        """
        try:
            messages = [{"role": "user", "content": "Hi, respond with 'OK'"}]
            self._request(messages, max_tokens=10)
            return True, f"连接成功，模型: {self.model}"
        except requests.exceptions.ConnectionError as e:
            logger.error(f"连接错误 (网络/代理/DNS): {e}")
            return False, f"连接失败 (网络/代理/DNS错误): {e}"
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "N/A"
            logger.error(f"HTTP状态错误: {status} - {e}")
            return False, f"连接失败 (HTTP {status}): {e}"
        except requests.exceptions.Timeout as e:
            logger.error(f"连接超时: {e}")
            return False, f"连接失败 (超时): {e}"
        except Exception as e:
            logger.error(f"连接失败: {type(e).__name__}: {e}")
            return False, f"连接失败: {type(e).__name__}: {e}"
