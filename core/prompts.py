"""内置提示词模板，用于中英文翻译校验。"""

SYSTEM_PROMPT = """你是一位专业的中英文翻译质量审核专家。你需要对给定的中文原文和英文译文进行翻译质量校验。
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

BUILTIN_PROMPTS = {
    "翻译准确性检查": {
        "name": "翻译准确性检查",
        "description": "重点检查语义是否准确传达、有无漏译/错译",
        "system": SYSTEM_PROMPT,
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
        "system": SYSTEM_PROMPT,
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
        "system": SYSTEM_PROMPT,
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
        "system": SYSTEM_PROMPT,
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
}


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
