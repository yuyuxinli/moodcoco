"""
archive_manager.py — 数据封存与删除管理器

处理告别仪式（S10）的数据操作：
- 封存：保留模式级洞察，清除具体事件内容
- 删除：彻底删除所有相关数据
- 时间胶囊：封存用户留言，到期后打开

设计参考：docs/technical-design.md §8
只用 Python 标准库。

用法（由 AI agent 通过 exec 调用）：
    python3 .../archive_manager.py archive <people_dir> <diary_dir> <memory_dir> <name>
    python3 .../archive_manager.py delete <people_dir> <diary_dir> <memory_dir> <name>
    python3 .../archive_manager.py capsule <memory_dir> create "<content>"
    python3 .../archive_manager.py capsule <memory_dir> check
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Pattern Insight Extraction
# ---------------------------------------------------------------------------

def extract_pattern_insights(people_file: str) -> list:
    """从 people/{name}.md 提取模式级洞察（去掉名字）。

    提取内容：
    - "我们之间的模式" 段落（去掉具体人名）
    - "退出信号" 段落的模式描述（去掉人名，保留时间和行为模式）
    - "跨关系匹配" 段落（去掉人名，保留模式描述）

    返回去名字后的洞察列表。
    """
    path = Path(people_file)
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    name = path.stem
    insights = []

    current_section = ""
    for line in text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("## 我们之间的模式"):
            current_section = "patterns"
            continue
        elif stripped.startswith("## 退出信号"):
            current_section = "exit_signals"
            continue
        elif stripped.startswith("## 跨关系匹配"):
            current_section = "cross_matches"
            continue
        elif stripped.startswith("## "):
            current_section = ""
            continue

        if stripped.startswith("<!--") or stripped == "":
            continue

        if current_section in ("patterns", "exit_signals", "cross_matches"):
            # Collect both list items (- ...) and plain paragraphs
            content_line = ""
            if stripped.startswith("- "):
                content_line = stripped[2:]
            elif stripped and not stripped.startswith("#"):
                content_line = stripped

            if content_line:
                anonymized = _anonymize(content_line, name)
                if anonymized.strip():
                    insights.append({
                        "source": current_section,
                        "content": anonymized,
                    })

    return insights


def _get_name_variants(name: str) -> list:
    """生成人名的所有可能变体（昵称、称呼等）。"""
    variants = [name]
    if len(name) >= 2:
        last_char = name[-1]
        first_char = name[0] if len(name) == 2 else name[1]
        variants.extend([
            f"阿{last_char}", f"{last_char}{last_char}",
            f"{last_char}哥", f"{last_char}姐",
            f"小{last_char}", f"老{last_char}",
        ])
        if len(name) == 2:
            variants.append(first_char + first_char)
    return list(set(variants))


def _text_contains_name(text: str, name: str) -> bool:
    """检查文本是否包含人名或其任何变体。"""
    for variant in _get_name_variants(name):
        if variant in text:
            return True
    return False


def _anonymize(text: str, name: str) -> str:
    """从文本中移除指定人名及所有变体，替换为泛化描述。"""
    result = text
    for variant in _get_name_variants(name):
        result = result.replace(variant, "对方")

    # Common reference patterns
    for prefix in ["和", "跟", "与", "给", "对", "找"]:
        for variant in _get_name_variants(name):
            result = result.replace(f"{prefix}{variant}", f"{prefix}对方")

    return result


def _remove_sections_mentioning(text: str, name: str) -> str:
    """从 markdown 文件中移除包含指定人名的 ## 段落。

    检查整个 section 内容（不仅限于标题行）。
    """
    # Split into sections
    sections = []
    current_header = ""
    current_lines = []

    for line in text.split("\n"):
        if line.strip().startswith("## "):
            if current_header or current_lines:
                sections.append((current_header, current_lines))
            current_header = line
            current_lines = []
        elif line.strip() == "---":
            sections.append((current_header, current_lines))
            sections.append(("---", []))
            current_header = ""
            current_lines = []
        else:
            current_lines.append(line)

    if current_header or current_lines:
        sections.append((current_header, current_lines))

    # Filter out sections containing the name
    result_lines = []
    for header, lines in sections:
        if header == "---":
            result_lines.append("---")
            continue

        section_text = header + "\n" + "\n".join(lines)
        if _text_contains_name(section_text, name):
            continue  # Remove entire section

        if header:
            result_lines.append(header)
        result_lines.extend(lines)

    return "\n".join(result_lines)


# ---------------------------------------------------------------------------
# Archive (封存)
# ---------------------------------------------------------------------------

def archive_person(people_dir: str, diary_dir: str, memory_dir: str, name: str) -> dict:
    """封存一个人的所有数据。

    操作：
    1. people/{name}.md → 保留头部（标记 archived），清空具体事件内容
    2. diary/ → 扫描所有条目，标记含该人的条目为 archived
    3. memory/ → 删除含该人名字的记忆文件
    4. 返回保留的模式级洞察（供写入 USER.md）

    返回 {"insights": [...], "archived_files": [...], "errors": [...]}
    """
    result = {"insights": [], "archived_files": [], "errors": []}

    people_path = Path(people_dir) / f"{name}.md"

    # 1. Extract insights before archiving
    if people_path.exists():
        result["insights"] = extract_pattern_insights(str(people_path))

        # Rewrite people file: keep header, clear body
        text = people_path.read_text(encoding="utf-8")
        archived_text = _archive_people_file(text, name)
        people_path.write_text(archived_text, encoding="utf-8")
        result["archived_files"].append(str(people_path))
    else:
        result["errors"].append(f"people/{name}.md not found")

    # 2. Archive diary entries mentioning this person
    diary_path = Path(diary_dir)
    if diary_path.exists():
        for md_file in diary_path.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            if _text_contains_name(text, name):
                archived = _archive_diary_entry(text, name)
                md_file.write_text(archived, encoding="utf-8")
                result["archived_files"].append(str(md_file))

    # 3. Clean memory files mentioning this person
    memory_path = Path(memory_dir)
    if memory_path.exists():
        for md_file in memory_path.glob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            if not _text_contains_name(text, name):
                continue

            if md_file.name in ("pending_followup.md", "time_capsules.md"):
                # For these files, remove only sections mentioning the person
                cleaned = _remove_sections_mentioning(text, name)
                md_file.write_text(cleaned, encoding="utf-8")
                result["archived_files"].append(f"cleaned: {md_file}")
            else:
                md_file.unlink()
                result["archived_files"].append(f"deleted: {md_file}")

    return result


def _archive_people_file(text: str, name: str) -> str:
    """重写 people file：保留头部信息，清空正文，标记为封存。"""
    lines = text.split("\n")
    archived_lines = []
    in_header = True

    for line in lines:
        stripped = line.strip()

        # Keep the title and header fields
        if stripped.startswith(f"# {name}"):
            archived_lines.append(line)
            continue

        if in_header and (
            stripped.startswith("关系类型") or
            stripped.startswith("认识时间") or
            stripped.startswith("首次提及")
        ):
            archived_lines.append(line)
            continue

        if stripped.startswith("当前状态"):
            archived_lines.append("当前状态：封存")
            in_header = False
            continue

        if stripped.startswith("## "):
            in_header = False
            # Keep section headers but clear content
            archived_lines.append("")
            archived_lines.append(line)
            archived_lines.append("<!-- 已封存 -->")
            continue

    # Add archive marker at top
    archived_lines.insert(1, "")
    archived_lines.insert(2, "> **已封存** — 具体内容已清除，模式级洞察已保留到 USER.md")
    archived_lines.insert(3, "")

    return "\n".join(archived_lines)


def _archive_diary_entry(text: str, name: str) -> str:
    """在 diary 条目中标记含该人的段落为已封存，保留情绪标签。

    检查整个 section 的内容（不仅限于标题行），
    任何 section 中出现人名都会被封存。
    """
    lines = text.split("\n")
    result_lines = []
    current_section_lines = []
    current_section_header = ""

    def flush_section():
        """输出当前 section，检查是否需要封存。"""
        if not current_section_header:
            result_lines.extend(current_section_lines)
            return

        section_text = "\n".join(current_section_lines)
        if _text_contains_name(current_section_header, name) or _text_contains_name(section_text, name):
            # Archive this section: keep header + emotion/intensity only
            result_lines.append(current_section_header)
            result_lines.append(f"> *与{name}相关的内容已封存*")
            for sl in current_section_lines:
                stripped = sl.strip()
                if stripped.startswith("**情绪**") or stripped.startswith("**强度**"):
                    result_lines.append(sl)
        else:
            result_lines.append(current_section_header)
            result_lines.extend(current_section_lines)

    for line in lines:
        if line.strip().startswith("## "):
            flush_section()
            current_section_header = line
            current_section_lines = []
            continue

        if line.strip() == "---":
            flush_section()
            current_section_header = ""
            current_section_lines = []
            result_lines.append(line)
            continue

        current_section_lines.append(line)

    flush_section()
    return "\n".join(result_lines)


# ---------------------------------------------------------------------------
# Delete (彻底删除)
# ---------------------------------------------------------------------------

def delete_person(people_dir: str, diary_dir: str, memory_dir: str, name: str) -> dict:
    """彻底删除一个人的所有数据。

    返回 {"deleted_files": [...], "errors": [...]}
    """
    result = {"deleted_files": [], "errors": []}

    # 1. Delete people file
    people_path = Path(people_dir) / f"{name}.md"
    if people_path.exists():
        people_path.unlink()
        result["deleted_files"].append(str(people_path))

    # 2. Remove mentions from diary entries
    diary_path = Path(diary_dir)
    if diary_path.exists():
        for md_file in diary_path.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            if _text_contains_name(text, name):
                cleaned = _remove_person_from_diary(text, name)
                md_file.write_text(cleaned, encoding="utf-8")
                result["deleted_files"].append(f"cleaned: {md_file}")

    # 3. Remove memory files
    memory_path = Path(memory_dir)
    if memory_path.exists():
        for md_file in memory_path.glob("*.md"):
            if md_file.name in ("pending_followup.md", "time_capsules.md"):
                continue
            text = md_file.read_text(encoding="utf-8")
            if _text_contains_name(text, name):
                md_file.unlink()
                result["deleted_files"].append(f"deleted: {md_file}")

    return result


def _remove_person_from_diary(text: str, name: str) -> str:
    """从 diary 条目中移除包含该人的整个 section。"""
    lines = text.split("\n")
    result_lines = []
    skip_section = False

    for line in lines:
        if line.strip().startswith("## "):
            if _text_contains_name(line, name):
                skip_section = True
                continue
            else:
                skip_section = False

        if skip_section:
            if line.strip() == "---":
                skip_section = False
            continue

        result_lines.append(line)

    return "\n".join(result_lines)


# ---------------------------------------------------------------------------
# Time Capsule
# ---------------------------------------------------------------------------

CAPSULE_DURATION_MONTHS = 3


def create_time_capsule(memory_dir: str, content: str) -> dict:
    """创建一个时间胶囊。

    封存用户写的内容，3 个月后可可打开。
    写入 memory/time_capsules.md。
    """
    memory_path = Path(memory_dir)
    memory_path.mkdir(parents=True, exist_ok=True)
    capsule_file = memory_path / "time_capsules.md"

    now = datetime.now()
    open_date = now + timedelta(days=CAPSULE_DURATION_MONTHS * 30)

    capsule_id = f"capsule_{now.strftime('%Y%m%d_%H%M%S')}"

    entry = f"""
## {capsule_id}

- 封存日期：{now.strftime('%Y-%m-%d')}
- 开启日期：{open_date.strftime('%Y-%m-%d')}
- 状态：sealed

> {content}

---
"""

    # Append to file
    if capsule_file.exists():
        existing = capsule_file.read_text(encoding="utf-8")
        capsule_file.write_text(existing + entry, encoding="utf-8")
    else:
        capsule_file.write_text(f"# 时间胶囊\n{entry}", encoding="utf-8")

    return {
        "capsule_id": capsule_id,
        "sealed_date": now.strftime('%Y-%m-%d'),
        "open_date": open_date.strftime('%Y-%m-%d'),
    }


def check_time_capsules(memory_dir: str) -> list:
    """检查是否有到期的时间胶囊。"""
    capsule_file = Path(memory_dir) / "time_capsules.md"
    if not capsule_file.exists():
        return []

    text = capsule_file.read_text(encoding="utf-8")
    today = datetime.now().strftime('%Y-%m-%d')
    due_capsules = []

    current_id = ""
    current_open_date = ""
    current_content = ""
    current_status = ""

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## capsule_"):
            current_id = stripped[3:].strip()
            current_content = ""
        elif stripped.startswith("- 开启日期："):
            current_open_date = stripped.split("：", 1)[1].strip()
        elif stripped.startswith("- 状态："):
            current_status = stripped.split("：", 1)[1].strip()
        elif stripped.startswith("> ") and current_id:
            current_content = stripped[2:].strip()
        elif stripped == "---" and current_id:
            if current_status == "sealed" and current_open_date <= today:
                due_capsules.append({
                    "capsule_id": current_id,
                    "open_date": current_open_date,
                    "content": current_content,
                })
            current_id = ""

    return due_capsules


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  archive_manager.py archive <people_dir> <diary_dir> <memory_dir> <name>")
        print("  archive_manager.py delete <people_dir> <diary_dir> <memory_dir> <name>")
        print("  archive_manager.py capsule <memory_dir> create <content>")
        print("  archive_manager.py capsule <memory_dir> check")
        sys.exit(1)

    command = sys.argv[1]

    if command == "archive" and len(sys.argv) >= 6:
        result = archive_person(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "delete" and len(sys.argv) >= 6:
        result = delete_person(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "capsule" and len(sys.argv) >= 4:
        if sys.argv[3] == "create" and len(sys.argv) >= 5:
            result = create_time_capsule(sys.argv[2], sys.argv[4])
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif sys.argv[3] == "check":
            capsules = check_time_capsules(sys.argv[2])
            print(json.dumps(capsules, ensure_ascii=False, indent=2))
        else:
            print("Unknown capsule command")
            sys.exit(1)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
