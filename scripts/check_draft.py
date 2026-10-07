#!/usr/bin/env python3
"""Read-only v2 draft checks; no network, file changes, or external dependencies."""
import argparse
import json
import sys
import unicodedata
from pathlib import Path

ROLE = "sales"
VERSION = "2.0.0"

def count_chars(value):
    return sum(not char.isspace() for char in value)

def canonical(value):
    return unicodedata.normalize("NFKC", value).strip().casefold()

def validate(draft):
    if not isinstance(draft, dict):
        raise ValueError("稿件必须是JSON对象")
    errors, counts = [], {}
    for field in ("cover", "title", "body"):
        value = draft.get(field)
        if not isinstance(value, str):
            raise ValueError(field + " 必须是字符串")
        counts[field] = len(value.strip()) if field == "title" else count_chars(value)
        if counts[field] == 0:
            errors.append(field + " 不能为空")
    for field, limit in (("cover", 24), ("title", 20)):
        if counts[field] > limit:
            errors.append(f"{field} 为{counts[field]}字，超过{limit}字")
    minimum, maximum = 1, 1000
    if ROLE == "sales":
        complexity = draft.get("complexity")
        if complexity not in ("simple", "analysis"):
            raise ValueError("销售稿必须指定 complexity: simple 或 analysis")
        minimum, maximum = (500, 800) if complexity == "simple" else (800, 1000)
    if not minimum <= counts["body"] <= maximum:
        errors.append(f"正文主体为{counts['body']}字，要求{minimum}—{maximum}字（不含话题）")
    topics = draft.get("topics")
    if not isinstance(topics, list) or not all(isinstance(t, str) for t in topics):
        raise ValueError("topics 必须是话题字符串数组")
    topic_keys = [canonical(t) for t in topics]
    if len(topics) != 10:
        errors.append(f"需要10个话题，当前{len(topics)}个")
    if len(set(topic_keys)) != len(topic_keys):
        errors.append("话题不能重复")
    for topic in topics:
        if not topic.startswith("#") or len(topic) <= 1 or "#" in topic[1:] or any(c.isspace() for c in topic):
            errors.append("话题应为无空格的单个#话题名：" + topic)
    if any(t and t in draft["body"] for t in topics):
        errors.append("body只放正文主体；话题独立放topics，避免重复和凑字")
    counts["topic_count"] = len(topics)
    counts["topic_chars"] = sum(count_chars(t) for t in topics)
    counts["publish_total"] = counts["body"] + counts["topic_chars"]
    if counts["publish_total"] > 1000:
        errors.append(f"主体＋话题为{counts['publish_total']}字，超过1000字")
    mode = draft.get("location_mode")
    if mode not in ("project", "area", "general"):
        raise ValueError("必须指定 location_mode: project、area 或 general")
    if mode != "general":
        region = draft.get("region")
        if not isinstance(region, str) or not region.strip():
            errors.append("有地域指向，必须先确认region区域／板块")
            region = ""
        geo = draft.get("geo_topics")
        if not isinstance(geo, list) or not all(isinstance(t, str) for t in geo):
            errors.append("有地域指向，geo_topics需列出至少2个已使用的地域话题")
            geo = []
        geo_keys = {canonical(t) for t in geo}
        if len(geo_keys) < 2 or not geo_keys.issubset(set(topic_keys)):
            errors.append("至少2个不重复地域话题，且必须出现在topics中")
        visible = canonical(draft["cover"] + draft["title"] + draft["body"])
        if region:
            if canonical(region) not in visible:
                errors.append("区域不能只放话题里，应在封面、标题或正文中点明")
            if not any(canonical(region) in t for t in geo_keys):
                errors.append("缺少包含已确认区域／板块名称的地域话题")
        if mode == "project":
            project = draft.get("project")
            if not isinstance(project, str) or not project.strip():
                errors.append("具体房源／服务／活动必须先确认project楼盘／小区名称")
                project = ""
            if project:
                if canonical(project) not in visible:
                    errors.append("小区不能只放话题里，应在封面、标题或正文中点明")
                if not any(canonical(project) in t for t in geo_keys):
                    errors.append("缺少包含已确认楼盘／小区名称的地域话题")
    return {"valid": not errors, "role": ROLE, "version": VERSION, "counts": counts,
            "limits": {"body_min": minimum, "body_max": maximum, "publish_total_max":1000,
                       "cover_max":24, "title_max":20, "topics":10},
            "counting":"正文去空白计Unicode码点；标题内部空格也计数；组合emoji保守计多字",
            "errors": errors,
            "manual_review":"仍需人工核对事实、地名真伪、话题相关性及文章是否有新判断；脚本无法证明这些"}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", default="-", help="JSON文件；省略或-从标准输入读取")
    args = parser.parse_args()
    try:
        raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8-sig")
        result = validate(json.loads(raw))
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"valid": False, "input_error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1

if __name__ == "__main__":
    sys.exit(main())
