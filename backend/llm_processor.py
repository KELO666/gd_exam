import os
import re
import json
import asyncio
import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
)

from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from backend.core.major_mapping import map_majors_to_disciplines

log = logging.getLogger(__name__)

# ─── 并发控制 ──────────────────────────────────────────────
_api_semaphore = None


def _get_semaphore():
    global _api_semaphore
    if _api_semaphore is None:
        _api_semaphore = asyncio.Semaphore(5)
    return _api_semaphore


# ─── Prompt（简化版：LLM 只做傻瓜式提取）──────────────────

EXTRACT_PROMPT = """你是一个严谨的数据提取接口。只需返回严格的 JSON，包含以下字段：

- deadline: 报名截止日期，格式为 YYYY-MM-DD；若无明确截止日期或长期有效则为 null
- is_unlimited: 布尔值，若公告明确写"不限专业"、"专业不限"或类似表述则为 true，否则为 false
- majors: 数组，包含正文中出现的具体专业名称（如：计算机科学与技术、临床医学、会计学等）；若未提及具体专业则为空数组 []

注意：只提取正文中明确提到的专业名称，不要猜测，不要推断学科门类。

绝不要输出任何解释性文字或 Markdown 代码块标记。只输出纯 JSON。"""


# ─── 工具函数 ──────────────────────────────────────────────

def _truncate_text(core_text, title="", head=1000, tail=1000):
    """
    掐头去尾截断法：保留前 head 字 + 后 tail 字拼接，
    防止 Token 超载同时保留关键信息（标题、截止日期通常在首尾）。
    """
    if not core_text:
        return ""
    total = head + tail
    if len(core_text) <= total:
        body = core_text
    else:
        body = core_text[:head] + "\n...(中间省略)...\n" + core_text[-tail:]
    prefix = f"标题：{title}\n\n" if title else ""
    return f"{prefix}正文：\n{body}"


def _parse_json_response(raw):
    """
    从 LLM 响应中解析 JSON。
    强力清洗：彻底去除 markdown 代码块围栏。
    """
    raw = raw.strip()
    raw = re.sub(r'```json\s*\n?', '', raw)
    raw = re.sub(r'\n?\s*```', '', raw)
    raw = raw.strip()
    return json.loads(raw)


def _validate_and_map(result):
    """
    校验 LLM 返回结果，并通过本地字典将 majors 映射为 disciplines。
    """
    deadline = result.get("deadline")
    is_unlimited = bool(result.get("is_unlimited", False))
    majors = result.get("majors", [])

    # deadline 格式校验
    if deadline and not re.match(r'^\d{4}-\d{2}-\d{2}$', str(deadline)):
        deadline = None

    # majors 校验
    if not isinstance(majors, list):
        majors = []
    majors = [m for m in majors if isinstance(m, str) and m.strip()]

    # 三不限时清空专业
    if is_unlimited:
        majors = []

    # 本地字典映射：majors → disciplines
    disciplines = map_majors_to_disciplines(majors)

    return {
        "deadline": deadline,
        "is_unlimited": is_unlimited,
        "disciplines": disciplines,
        "major_names": majors,
    }


# ─── 同步调用（供 scraper 使用）────────────────────────────

_RETRY_ARGS = dict(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    reraise=True,
)


@retry(**_RETRY_ARGS)
def _call_api_sync(client, messages):
    """同步调用 DeepSeek API（带 tenacity Jitter 重试）"""
    return client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=200,
        response_format={"type": "json_object"},
    )


def extract_info(core_text, title=""):
    """
    同步入口：调用大模型提取 deadline/is_unlimited/majors，
    然后通过本地字典映射出 disciplines。
    输出：{"deadline", "is_unlimited", "disciplines", "major_names"} 或 None。
    """
    if not DEEPSEEK_API_KEY:
        log.debug("DEEPSEEK_API_KEY 未设置，跳过 AI 提取")
        return None

    user_content = _truncate_text(core_text, title)
    messages = [
        {"role": "system", "content": EXTRACT_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        response = _call_api_sync(client, messages)
        raw = response.choices[0].message.content.strip()
        result = _parse_json_response(raw)
        return _validate_and_map(result)
    except Exception as e:
        log.warning("LLM 提取失败: %s", e)
        return None


# ─── 异步调用（供异步爬虫使用）────────────────────────────

@retry(**_RETRY_ARGS)
async def _call_api_async(client, messages, semaphore):
    """异步调用 DeepSeek API（带 tenacity Jitter 重试 + 信号量限流）"""
    async with semaphore:
        return await client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=200,
            response_format={"type": "json_object"},
        )


async def extract_info_async(core_text, title=""):
    """异步入口：同 extract_info，返回完整结果字典。"""
    if not DEEPSEEK_API_KEY:
        log.debug("DEEPSEEK_API_KEY 未设置，跳过 AI 提取")
        return None

    user_content = _truncate_text(core_text, title)
    messages = [
        {"role": "system", "content": EXTRACT_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        semaphore = _get_semaphore()
        response = await _call_api_async(client, messages, semaphore)
        raw = response.choices[0].message.content.strip()
        result = _parse_json_response(raw)
        return _validate_and_map(result)
    except Exception as e:
        log.warning("异步 LLM 提取失败: %s", e)
        return None
