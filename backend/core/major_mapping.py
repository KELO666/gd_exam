"""
本地专业→学科门类特征词匹配模块。

LLM 只负责"傻瓜式"提取原文中的具体专业名称，
学科门类由此模块通过特征关键词子串匹配生成，与大模型完全解耦。

匹配算法：Substring Matching（特征词包含匹配）。
维护方式：向 KEYWORD_TO_DISCIPLINE 字典的 value 列表中添加特征词即可。
"""


# ─── 特征词 → 学科门类 映射字典 ───────────────────────────
# 格式：{ "学科门类": ["特征词1", "特征词2", ...] }
# 匹配逻辑：若专业名称中包含任意特征词，则归入该门类

KEYWORD_TO_DISCIPLINE = {
    "农学": ["农", "园艺", "植物", "动物", "林业", "水产"],
    "医学": ["医", "药", "护理", "卫生", "临床", "公共卫生"],
    "工学": ["计算机", "软件", "电子", "通信", "工程", "机械", "自动化", "材料", "建筑", "土木", "电气"],
    "理学": ["生物", "化学", "物理", "数学", "地理", "环境", "海洋", "统计"],
    "管理学": ["管理", "会计", "财务", "审计", "人力", "营销", "工商", "行政"],
    "法学": ["法学", "法律", "政治", "马克思", "社会", "公安", "警察"],
    "文学": ["汉语言", "中文", "外语", "翻译", "新闻", "传媒", "出版"],
    "教育学": ["教育", "师范", "心理", "体育"],
    "经济学": ["经济", "金融", "财政", "投资", "税务"],
}


def map_majors_to_disciplines(majors: list[str]) -> list[str]:
    """
    将具体专业列表映射为学科门类列表（去重、去空值）。

    匹配算法：遍历特征词字典，若专业名称中包含任意特征词，则归入该门类。
    未命中任何特征词的专业静默忽略，不返回"未分类"。

    参数:
        majors: LLM 提取的具体专业名称列表，如 ["计算机科学与技术", "软件工程"]

    返回:
        去重后的学科门类列表，如 ["工学"]
    """
    if not majors or not isinstance(majors, list):
        return []

    result_set = set()
    for major in majors:
        if not isinstance(major, str):
            continue
        major = major.strip()
        if not major:
            continue
        # 遍历特征字典进行子串匹配
        for discipline, keywords in KEYWORD_TO_DISCIPLINE.items():
            if any(keyword in major for keyword in keywords):
                result_set.add(discipline)

    return sorted(result_set)
