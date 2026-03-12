"""内置提示词模板，用于中英文翻译校验。

提示词模板从外部文件 presets/prompts.json 加载，支持程序外编辑。
若外部文件不存在或解析失败，则使用代码内的默认值兜底。
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

# ── 代码内兜底默认值 ──

_DEFAULT_SYSTEM_PROMPT = """你是一位专业的中英文翻译质量审核专家。你需要对给定的中文原文和英文译文进行翻译质量校验。
请严格按照以下JSON格式返回你的分析结果，不要返回任何其他内容：
{
  "score": <1-10的整数评分>,
  "issues": [<问题列表，每个问题是一个字符串>],
  "suggestion": "<修改建议，如果翻译质量好则写'无需修改'>",
  "summary": "<一句话总结评价>"
}

评分标准：
- 9-10分：翻译准确、流畅、自然，无明显问题
- 7-8分：翻译基本准确，有少量小问题
- 5-6分：翻译存在明显问题，但核心意思基本传达
- 3-4分：翻译有较多错误，影响理解
- 1-2分：翻译严重失误，意思完全偏离"""

_DEFAULT_BATCH_SYSTEM_PROMPT = """你是一位专业的中英文翻译质量审核专家。你需要对给定的多组中文原文和英文译文逐一进行翻译质量校验。
请严格按照以下JSON数组格式返回你的分析结果，不要返回任何其他内容。
数组中每个元素对应一组翻译，必须包含id字段来标识对应的编号：
[
  {
    "id": <编号>,
    "score": <1-10的整数评分>,
    "issues": [<问题列表，每个问题是一个字符串>],
    "suggestion": "<修改建议，如果翻译质量好则写'无需修改'>",
    "summary": "<一句话总结评价>"
  },
  ...
]

评分标准：
- 9-10分：翻译准确、流畅、自然，无明显问题
- 7-8分：翻译基本准确，有少量小问题
- 5-6分：翻译存在明显问题，但核心意思基本传达
- 3-4分：翻译有较多错误，影响理解
- 1-2分：翻译严重失误，意思完全偏离"""

_DEFAULT_BUILTIN_PROMPTS = {
    "翻译准确性检查": {
        "name": "翻译准确性检查",
        "description": "重点检查语义是否准确传达、有无漏译/错译",
        "system": "",
        "user": """请对以下中英文翻译进行【准确性检查】，重点关注：
1. 语义是否准确传达，有无理解偏差
2. 是否存在漏译（原文有但译文没有的内容）
3. 是否存在错译（译文与原文意思不符的内容）
4. 数字、日期、专有名词等是否翻译正确

中文原文：
{source_text}

英文译文：
{target_text}

请按JSON格式返回分析结果。"""
    },
    "术语一致性检查": {
        "name": "术语一致性检查",
        "description": "重点检查专业术语翻译是否准确、一致",
        "system": """请对以下中英文翻译进行【术语一致性检查】，重点关注：
1. 专业术语的翻译是否准确
2. 行业通用术语是否采用了标准译法
3. 专有名词（人名、地名、机构名等）翻译是否正确
4. 缩写和简称的使用是否恰当""",
        "user": """请对以下中英文翻译进行【术语一致性检查】，重点关注：
1. 专业术语的翻译是否准确
2. 行业通用术语是否采用了标准译法
3. 专有名词（人名、地名、机构名等）翻译是否正确
4. 缩写和简称的使用是否恰当

中文原文：
{source_text}

英文译文：
{target_text}

请按JSON格式返回分析结果。"""
    },
    "风格与流畅性检查": {
        "name": "风格与流畅性检查",
        "description": "重点检查译文是否自然流畅、符合目标语言表达习惯",
        "system": "",
        "user": """请对以下中英文翻译进行【风格与流畅性检查】，重点关注：
1. 英文译文是否自然流畅，符合英语表达习惯
2. 句式结构是否合理，有无中式英语（Chinglish）
3. 用词是否地道、恰当
4. 语法是否正确，标点符号使用是否规范
5. 语气和正式程度是否与原文匹配

中文原文：
{source_text}

英文译文：
{target_text}

请按JSON格式返回分析结果。"""
    },
    "综合翻译质量评估": {
        "name": "综合翻译质量评估",
        "description": "从准确性、术语、风格等多维度综合评估翻译质量",
        "system": "",
        "user": """请对以下中英文翻译进行【综合翻译质量评估】，从以下维度全面评估：
1. 准确性：语义是否准确传达，有无漏译/错译
2. 术语：专业术语和专有名词翻译是否准确
3. 流畅性：译文是否自然流畅，符合英语表达习惯
4. 风格：语气和正式程度是否与原文匹配
5. 语法：语法和标点是否正确

中文原文：
{source_text}

英文译文：
{target_text}

请按JSON格式返回分析结果，在issues中分维度列出发现的问题。"""
    },
    "拼写错误检查": {
        "name": "拼写错误检查",
        "description": "专注检查英文译文中的拼写错误",
        "system": "",
        "user": """请对以下英文译文进行【拼写错误检查】，只关注拼写问题：
1. 逐词检查英文译文中是否存在拼写错误（typo、多字母、少字母、字母顺序颠倒等）
2. 检查专有名词、缩写的拼写是否正确
3. 检查常见易混淆词是否拼写正确（如 their/there、its/it's、affect/effect 等）
4. 不需要检查语法、风格、流畅性等其他方面，只关注拼写

中文原文（供参考）：
{source_text}

英文译文：
{target_text}

请按JSON格式返回分析结果。如果没有拼写错误，评分为10分；每发现一处拼写错误扣1-2分。在issues中列出每一处拼写错误及其正确拼写。"""
    },
}


def _find_presets_dir():
    """查找 presets 目录，兼容打包后和源码运行。"""
    import sys
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        # 从 core/ 向上一级到项目根目录
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "presets")


def _load_prompts_from_file():
    """从 presets/prompts.json 加载提示词配置。

    Returns:
        tuple: (system_prompt, batch_system_prompt, builtin_prompts) 或 None（加载失败时）
    """
    presets_dir = _find_presets_dir()
    filepath = os.path.join(presets_dir, "prompts.json")

    if not os.path.exists(filepath):
        logger.info(f"预设提示词文件不存在: {filepath}，使用代码内默认值")
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        system_prompt = data.get("system_prompt", _DEFAULT_SYSTEM_PROMPT)
        batch_system_prompt = data.get("batch_system_prompt", _DEFAULT_BATCH_SYSTEM_PROMPT)

        templates = data.get("templates", {})
        builtin_prompts = {}
        for name, tpl in templates.items():
            # 如果模板未设置独立的 system，使用全局 system_prompt
            sys_prompt = tpl.get("system", "").strip()
            if not sys_prompt:
                sys_prompt = system_prompt
            builtin_prompts[name] = {
                "name": tpl.get("name", name),
                "description": tpl.get("description", ""),
                "system": sys_prompt,
                "user": tpl.get("user", ""),
            }

        logger.info(f"已从外部文件加载 {len(builtin_prompts)} 个提示词模板: {filepath}")
        return system_prompt, batch_system_prompt, builtin_prompts

    except Exception as e:
        logger.warning(f"加载预设提示词文件失败: {e}，使用代码内默认值")
        return None


# ── 初始化：优先从外部文件加载 ──

_loaded = _load_prompts_from_file()

if _loaded:
    SYSTEM_PROMPT, BATCH_SYSTEM_PROMPT, BUILTIN_PROMPTS = _loaded
else:
    SYSTEM_PROMPT = _DEFAULT_SYSTEM_PROMPT
    BATCH_SYSTEM_PROMPT = _DEFAULT_BATCH_SYSTEM_PROMPT
    # 兜底默认值中 system 为空的模板，填充全局 SYSTEM_PROMPT
    BUILTIN_PROMPTS = {}
    for name, tpl in _DEFAULT_BUILTIN_PROMPTS.items():
        sys_prompt = tpl["system"].strip() if tpl["system"] else SYSTEM_PROMPT
        BUILTIN_PROMPTS[name] = {
            "name": tpl["name"],
            "description": tpl["description"],
            "system": sys_prompt,
            "user": tpl["user"],
        }


def reload_prompts():
    """重新从外部文件加载提示词（供运行时刷新用）。"""
    global SYSTEM_PROMPT, BATCH_SYSTEM_PROMPT, BUILTIN_PROMPTS
    loaded = _load_prompts_from_file()
    if loaded:
        SYSTEM_PROMPT, BATCH_SYSTEM_PROMPT, BUILTIN_PROMPTS = loaded


def format_batch_prompt(items):
    """将多组翻译格式化为批量校验的用户提示词。

    Args:
        items: [{"id": 1, "source": "中文", "target": "English"}, ...]

    Returns:
        str: 格式化后的批量用户提示词
    """
    parts = [f"请对以下 {len(items)} 组中英文翻译逐一进行综合翻译质量校验。\n"]
    for item in items:
        parts.append(
            f"--- 第{item['id']}组 ---\n"
            f"中文原文：\n{item['source']}\n\n"
            f"英文译文：\n{item['target']}\n"
        )
    parts.append(f"\n请严格按照JSON数组格式返回全部 {len(items)} 组的分析结果，"
                 f"每组结果必须包含对应的id字段。")
    return "\n".join(parts)


def get_prompt_names():
    """返回所有内置提示词模板的名称列表。"""
    return list(BUILTIN_PROMPTS.keys())


def get_prompt(name):
    """根据名称获取提示词模板。"""
    return BUILTIN_PROMPTS.get(name)


def format_prompt(prompt_template, source_text, target_text):
    """将提示词模板中的占位符替换为实际文本。

    使用 str.replace 而非 str.format，避免原文/译文中含有 {} 时报错。
    """
    return (prompt_template
            .replace("{source_text}", source_text)
            .replace("{target_text}", target_text))
