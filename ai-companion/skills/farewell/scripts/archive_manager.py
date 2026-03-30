"""
archive_manager.py — 数据封存与删除管理器

处理告别仪式（S10）的数据操作：
- 封存（archive）：保留模式级洞察，清除具体事件内容
- 恢复（restore）：将已封存的关系恢复到封存前状态
- 状态（status）：查询封存状态
- 删除（delete）：彻底删除所有相关数据
- 时间胶囊（capsule）：封存用户留言，到期后打开

设计参考：docs/product/product-experience-design.md §5.5
只用 Python 标准库。

用法（由 AI agent 通过 exec 调用）：
    python3 .../archive_manager.py archive --person <名字> --people-dir people/ --diary-dir diary/ --memory-dir memory/
    python3 .../archive_manager.py restore --person <名字> --people-dir people/ --diary-dir diary/ --memory-dir memory/
    python3 .../archive_manager.py status --person <名字> --people-dir people/
    python3 .../archive_manager.py delete --person <名字> --people-dir people/ --diary-dir diary/ --memory-dir memory/
    python3 .../archive_manager.py capsule <memory_dir> create "<content>"
    python3 .../archive_manager.py capsule <memory_dir> check
    python3 .../archive_manager.py capsule <memory_dir> open <capsule_id>
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Pattern Insight Extraction
# ---------------------------------------------------------------------------


def extract_pattern_insights(people_file: str) -> list[dict[str, str]]:
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
        if stripped.startswith("## 退出信号"):
            current_section = "exit_signals"
            continue
        if stripped.startswith("## 跨关系匹配"):
            current_section = "cross_matches"
            continue
        if stripped.startswith("## "):
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
                    insights.append(
                        {
                            "source": current_section,
                            "content": anonymized,
                        }
                    )

    return insights


def _get_name_variants(name: str) -> list[str]:
    """生成人名的所有可能变体（昵称、称呼等）。"""
    variants = [name]
    if len(name) >= 2:
        last_char = name[-1]
        first_char = name[0] if len(name) == 2 else name[1]
        variants.extend(
            [
                f"阿{last_char}",
                f"{last_char}{last_char}",
                f"{last_char}哥",
                f"{last_char}姐",
                f"小{last_char}",
                f"老{last_char}",
            ]
        )
        if len(name) == 2:
            variants.append(first_char + first_char)
    return list(set(variants))


def _text_contains_name(text: str, name: str) -> bool:
    """检查文本是否包含人名或其任何变体。"""
    return any(variant in text for variant in _get_name_variants(name))


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


def _create_backup(
    people_dir: str,
    diary_dir: str,
    memory_dir: str,
    name: str,
) -> tuple[str, list[str]]:
    """Create backup directory with copies of all files related to a person.

    Returns (backup_path, files_backed_up).
    """
    today = datetime.now().strftime("%Y-%m-%d")
    archive_dir = Path(people_dir).parent / "archive"
    backup_path = archive_dir / f"{name}_{today}"
    backup_path.mkdir(parents=True, exist_ok=True)

    files_backed_up: list[str] = []

    # Backup people file
    people_path = Path(people_dir) / f"{name}.md"
    if people_path.exists():
        shutil.copy2(str(people_path), str(backup_path / people_path.name))
        files_backed_up.append(str(people_path))

    # Backup diary files mentioning this person
    diary_path = Path(diary_dir)
    if diary_path.exists():
        diary_backup = backup_path / "diary"
        for md_file in diary_path.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            if _text_contains_name(text, name):
                rel_path = md_file.relative_to(diary_path)
                dest = diary_backup / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(md_file), str(dest))
                files_backed_up.append(str(md_file))

    # Backup memory files mentioning this person
    memory_path = Path(memory_dir)
    if memory_path.exists():
        memory_backup = backup_path / "memory"
        for md_file in memory_path.glob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            if _text_contains_name(text, name):
                memory_backup.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(md_file), str(memory_backup / md_file.name))
                files_backed_up.append(str(md_file))

    return str(backup_path), files_backed_up


def archive_person(
    people_dir: str,
    diary_dir: str,
    memory_dir: str,
    name: str,
    ritual_type: str = "standard",
) -> dict[str, Any]:
    """封存一个人的所有数据。

    操作：
    1. 创建备份目录 archive/{名字}_{日期}/
    2. people/{name}.md → 保留头部（标记 archived），清空具体事件内容
    3. diary/ → 扫描所有条目，标记含该人的条目为 archived
    4. memory/ → 删除含该人名字的记忆文件
    5. 返回保留的模式级洞察（供写入 USER.md）

    参数：
    - ritual_type: 告别仪式类型（standard / gentle / quick），默认 standard

    返回 spec-compliant JSON:
    {"status": "ok", "action": "archive", "person": ..., "pattern_insights": [...],
     "files_affected": [...], "backup_path": "...", "error": null}
    """
    result: dict[str, Any] = {
        "status": "ok",
        "action": "archive",
        "person": name,
        "pattern_insights": [],
        "files_affected": [],
        "backup_path": "",
        "error": None,
    }

    people_path = Path(people_dir) / f"{name}.md"

    if not people_path.exists():
        return {
            "status": "not_found",
            "action": "archive",
            "person": name,
            "pattern_insights": [],
            "files_affected": [],
            "backup_path": "",
            "error": f"Person '{name}' not found in people/",
        }

    # Check if already archived
    text = people_path.read_text(encoding="utf-8")
    if "当前状态：封存" in text:
        return {
            "status": "already_archived",
            "action": "archive",
            "person": name,
            "pattern_insights": [],
            "files_affected": [],
            "backup_path": "",
            "error": f"Person '{name}' is already archived",
        }

    # Step 1: Create backup
    backup_path, _backup_files = _create_backup(
        people_dir, diary_dir, memory_dir, name
    )
    result["backup_path"] = backup_path

    # Step 2: Extract insights before archiving
    insights = extract_pattern_insights(str(people_path))
    result["pattern_insights"] = [i["content"] for i in insights]

    # Step 3: Rewrite people file: keep header, clear body
    archived_text = _archive_people_file(text, name, ritual_type)
    people_path.write_text(archived_text, encoding="utf-8")
    result["files_affected"].append(str(people_path))

    # Step 4: Archive diary entries mentioning this person
    diary_path = Path(diary_dir)
    if diary_path.exists():
        for md_file in diary_path.rglob("*.md"):
            diary_text = md_file.read_text(encoding="utf-8")
            if _text_contains_name(diary_text, name):
                archived = _archive_diary_entry(diary_text, name)
                md_file.write_text(archived, encoding="utf-8")
                result["files_affected"].append(str(md_file))

    # Step 5: Clean memory files mentioning this person
    memory_path = Path(memory_dir)
    if memory_path.exists():
        for md_file in memory_path.glob("*.md"):
            mem_text = md_file.read_text(encoding="utf-8")
            if not _text_contains_name(mem_text, name):
                continue

            if md_file.name in ("pending_followup.md", "time_capsules.md"):
                cleaned = _remove_sections_mentioning(mem_text, name)
                md_file.write_text(cleaned, encoding="utf-8")
                result["files_affected"].append(str(md_file))
            else:
                md_file.unlink()
                result["files_affected"].append(str(md_file))

    return result


def _archive_people_file(text: str, name: str, ritual_type: str = "standard") -> str:
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
            stripped.startswith("关系类型")
            or stripped.startswith("认识时间")
            or stripped.startswith("首次提及")
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
    archived_lines.insert(
        2,
        f"> **已封存** — 仪式类型：{ritual_type} | 具体内容已清除，模式级洞察已保留到 USER.md",
    )
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

    def flush_section() -> None:
        """输出当前 section，检查是否需要封存。"""
        if not current_section_header:
            result_lines.extend(current_section_lines)
            return

        section_text = "\n".join(current_section_lines)
        if _text_contains_name(current_section_header, name) or _text_contains_name(
            section_text, name
        ):
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
# Restore (恢复)
# ---------------------------------------------------------------------------


def restore_person(
    people_dir: str,
    diary_dir: str,
    memory_dir: str,
    name: str,
) -> dict[str, Any]:
    """恢复已封存的关系到封存前状态。

    从 archive/{名字}_{日期}/ 读取备份文件，覆盖当前文件。

    返回 spec-compliant JSON:
    {"status": "ok|not_found", "action": "restore", "person": ...,
     "files_affected": [...], "backup_path": "...", "error": null}
    """
    result: dict[str, Any] = {
        "status": "ok",
        "action": "restore",
        "person": name,
        "pattern_insights": [],
        "files_affected": [],
        "backup_path": "",
        "error": None,
    }

    # Find the backup directory (most recent if multiple)
    archive_dir = Path(people_dir).parent / "archive"
    if not archive_dir.exists():
        return {
            "status": "not_found",
            "action": "restore",
            "person": name,
            "pattern_insights": [],
            "files_affected": [],
            "backup_path": "",
            "error": "Backup not found",
        }

    # Find backup dirs matching the person name
    backup_dirs = sorted(
        [d for d in archive_dir.iterdir() if d.is_dir() and d.name.startswith(f"{name}_")],
        reverse=True,
    )

    if not backup_dirs:
        return {
            "status": "not_found",
            "action": "restore",
            "person": name,
            "pattern_insights": [],
            "files_affected": [],
            "backup_path": "",
            "error": f"Backup not found for '{name}'",
        }

    backup_path = backup_dirs[0]
    result["backup_path"] = str(backup_path)

    # Restore people file
    backup_people = backup_path / f"{name}.md"
    if backup_people.exists():
        dest = Path(people_dir) / f"{name}.md"
        shutil.copy2(str(backup_people), str(dest))
        result["files_affected"].append(str(dest))

    # Restore diary files
    backup_diary = backup_path / "diary"
    if backup_diary.exists():
        diary_path = Path(diary_dir)
        for md_file in backup_diary.rglob("*.md"):
            rel_path = md_file.relative_to(backup_diary)
            dest = diary_path / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(md_file), str(dest))
            result["files_affected"].append(str(dest))

    # Restore memory files
    backup_memory = backup_path / "memory"
    if backup_memory.exists():
        memory_path = Path(memory_dir)
        for md_file in backup_memory.glob("*.md"):
            dest = memory_path / md_file.name
            shutil.copy2(str(md_file), str(dest))
            result["files_affected"].append(str(dest))

    return result


# ---------------------------------------------------------------------------
# Status (查询封存状态)
# ---------------------------------------------------------------------------


def status_person(
    people_dir: str,
    name: str,
) -> dict[str, Any]:
    """查询指定人物的封存状态。

    返回 spec-compliant JSON:
    {"status": "ok|not_found", "action": "status", "person": ...,
     "current_status": "active|archived", "backup_path": "...", "error": null}
    """
    people_path = Path(people_dir) / f"{name}.md"

    if not people_path.exists():
        return {
            "status": "not_found",
            "action": "status",
            "person": name,
            "pattern_insights": [],
            "files_affected": [],
            "backup_path": "",
            "error": f"Person '{name}' not found in people/",
        }

    text = people_path.read_text(encoding="utf-8")
    is_archived = "当前状态：封存" in text

    # Check for backup
    archive_dir = Path(people_dir).parent / "archive"
    backup_path = ""
    if archive_dir.exists():
        backup_dirs = sorted(
            [d for d in archive_dir.iterdir() if d.is_dir() and d.name.startswith(f"{name}_")],
            reverse=True,
        )
        if backup_dirs:
            backup_path = str(backup_dirs[0])

    return {
        "status": "ok" if is_archived else "already_active",
        "action": "status",
        "person": name,
        "pattern_insights": [],
        "files_affected": [str(people_path)],
        "backup_path": backup_path,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Delete (彻底删除)
# ---------------------------------------------------------------------------


def delete_person(
    people_dir: str, diary_dir: str, memory_dir: str, name: str
) -> dict[str, Any]:
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
            text = md_file.read_text(encoding="utf-8")
            if not _text_contains_name(text, name):
                continue

            if md_file.name in ("pending_followup.md", "time_capsules.md"):
                # Section-level cleanup: remove sections mentioning this person,
                # keep unrelated sections intact (aligned with archive_person behavior)
                cleaned = _remove_sections_mentioning(text, name)
                md_file.write_text(cleaned, encoding="utf-8")
                result["deleted_files"].append(f"cleaned: {md_file}")
            else:
                md_file.unlink()
                result["deleted_files"].append(f"deleted: {md_file}")

    return result


def _remove_person_from_diary(text: str, name: str) -> str:
    """从 diary 条目中移除包含该人的整个 section。

    检查整个 section 内容（标题 + 正文），不仅限于标题行。
    """
    # Reuse the same section-level approach as _remove_sections_mentioning
    # but adapted for diary format (## sections separated by ---)
    sections = []
    current_header = ""
    current_lines = []

    for line in text.split("\n"):
        if line.strip().startswith("## "):
            if current_header or current_lines:
                sections.append((current_header, list(current_lines)))
            current_header = line
            current_lines = []
        elif line.strip() == "---":
            if current_header or current_lines:
                sections.append((current_header, list(current_lines)))
            sections.append(("---", []))
            current_header = ""
            current_lines = []
        else:
            current_lines.append(line)

    if current_header or current_lines:
        sections.append((current_header, list(current_lines)))

    result_lines = []
    for header, lines in sections:
        if header == "---":
            result_lines.append("---")
            continue

        # Check entire section content for name variants
        section_text = header + "\n" + "\n".join(lines)
        if _text_contains_name(section_text, name):
            continue  # Remove entire section

        if header:
            result_lines.append(header)
        result_lines.extend(lines)

    return "\n".join(result_lines)


# ---------------------------------------------------------------------------
# Time Capsule
# ---------------------------------------------------------------------------

CAPSULE_DURATION_MONTHS = 3


def _add_months(dt: datetime, months: int) -> datetime:
    """精确加 N 个月（处理月末溢出）。"""
    import calendar

    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def create_time_capsule(memory_dir: str, content: str) -> dict[str, str]:
    """创建一个时间胶囊。

    封存用户写的内容，精确 3 个自然月后可可打开。
    写入 memory/time_capsules.md。
    """
    memory_path = Path(memory_dir)
    memory_path.mkdir(parents=True, exist_ok=True)
    capsule_file = memory_path / "time_capsules.md"

    now = datetime.now()
    open_date = _add_months(now, CAPSULE_DURATION_MONTHS)

    capsule_id = f"capsule_{now.strftime('%Y%m%d_%H%M%S')}"

    entry = f"""
## {capsule_id}

- 封存日期：{now.strftime("%Y-%m-%d")}
- 开启日期：{open_date.strftime("%Y-%m-%d")}
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
        "sealed_date": now.strftime("%Y-%m-%d"),
        "open_date": open_date.strftime("%Y-%m-%d"),
    }


def check_time_capsules(memory_dir: str) -> list[dict[str, str]]:
    """检查是否有到期的时间胶囊。"""
    capsule_file = Path(memory_dir) / "time_capsules.md"
    if not capsule_file.exists():
        return []

    text = capsule_file.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")
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
                due_capsules.append(
                    {
                        "capsule_id": current_id,
                        "open_date": current_open_date,
                        "content": current_content,
                    }
                )
            current_id = ""

    return due_capsules


def open_time_capsule(memory_dir: str, capsule_id: str) -> dict[str, str]:
    """打开一个时间胶囊，返回内容并标记为 opened。

    1. 读取 time_capsules.md
    2. 找到匹配 capsule_id 的段落
    3. 提取 content
    4. 将状态从 "sealed" 改为 "opened"
    5. 写回文件
    6. 返回 {"capsule_id": ..., "content": ..., "opened_date": ...}
    """
    capsule_file = Path(memory_dir) / "time_capsules.md"
    if not capsule_file.exists():
        return {"error": f"time_capsules.md not found in {memory_dir}"}

    text = capsule_file.read_text(encoding="utf-8")
    lines = text.split("\n")

    found = False
    content = ""
    new_lines = []
    in_target = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## ") and capsule_id in stripped:
            in_target = True
            found = True
            new_lines.append(line)
            continue

        if in_target:
            if stripped == "---" or (
                stripped.startswith("## ") and capsule_id not in stripped
            ):
                in_target = False
                new_lines.append(line)
                continue

            # Extract content from blockquote
            if stripped.startswith("> "):
                content = stripped[2:].strip()

            # Transition state: sealed -> opened
            if stripped == "- 状态：sealed":
                new_lines.append(line.replace("sealed", "opened"))
                continue

        new_lines.append(line)

    if not found:
        return {"error": f"capsule {capsule_id} not found"}

    capsule_file.write_text("\n".join(new_lines), encoding="utf-8")

    return {
        "capsule_id": capsule_id,
        "content": content,
        "opened_date": datetime.now().strftime("%Y-%m-%d"),
    }


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def _parse_named_args(argv: list[str]) -> dict[str, str]:
    """Parse --key value pairs from argv after the action word."""
    result: dict[str, str] = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            key = argv[i][2:]
            result[key] = argv[i + 1]
            i += 2
        else:
            i += 1
    return result


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:")
        print(
            "  archive_manager.py archive --person <名字> --people-dir people/ --diary-dir diary/ --memory-dir memory/"
        )
        print(
            "  archive_manager.py restore --person <名字> --people-dir people/ --diary-dir diary/ --memory-dir memory/"
        )
        print("  archive_manager.py status --person <名字> --people-dir people/")
        print(
            "  archive_manager.py delete --person <名字> --people-dir people/ --diary-dir diary/ --memory-dir memory/"
        )
        print("  archive_manager.py capsule <memory_dir> create <content>")
        print("  archive_manager.py capsule <memory_dir> check")
        print("  archive_manager.py capsule <memory_dir> open <capsule_id>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "archive":
        named = _parse_named_args(sys.argv[2:])
        person = named.get("person", "")
        people_dir = named.get("people-dir", "people/")
        diary_dir = named.get("diary-dir", "diary/")
        memory_dir = named.get("memory-dir", "memory/")
        ritual_type = named.get("ritual-type", "standard")
        if not person:
            # Legacy positional args fallback
            if len(sys.argv) >= 6:
                people_dir, diary_dir, memory_dir, person = sys.argv[2:6]
                ritual_type = sys.argv[6] if len(sys.argv) >= 7 else "standard"
            else:
                print("Error: --person is required")
                sys.exit(1)
        result = archive_person(
            people_dir, diary_dir, memory_dir, person, ritual_type=ritual_type
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "restore":
        named = _parse_named_args(sys.argv[2:])
        person = named.get("person", "")
        people_dir = named.get("people-dir", "people/")
        diary_dir = named.get("diary-dir", "diary/")
        memory_dir = named.get("memory-dir", "memory/")
        if not person:
            print("Error: --person is required")
            sys.exit(1)
        result = restore_person(people_dir, diary_dir, memory_dir, person)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "status":
        named = _parse_named_args(sys.argv[2:])
        person = named.get("person", "")
        people_dir = named.get("people-dir", "people/")
        if not person:
            print("Error: --person is required")
            sys.exit(1)
        result = status_person(people_dir, person)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "delete":
        named = _parse_named_args(sys.argv[2:])
        person = named.get("person", "")
        people_dir = named.get("people-dir", "people/")
        diary_dir = named.get("diary-dir", "diary/")
        memory_dir = named.get("memory-dir", "memory/")
        if not person:
            # Legacy positional args fallback
            if len(sys.argv) >= 6:
                people_dir, diary_dir, memory_dir, person = sys.argv[2:6]
            else:
                print("Error: --person is required")
                sys.exit(1)
        result = delete_person(people_dir, diary_dir, memory_dir, person)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "capsule" and len(sys.argv) >= 4:
        if sys.argv[3] == "create" and len(sys.argv) >= 5:
            result = create_time_capsule(sys.argv[2], sys.argv[4])
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif sys.argv[3] == "check":
            capsules = check_time_capsules(sys.argv[2])
            print(json.dumps(capsules, ensure_ascii=False, indent=2))
        elif sys.argv[3] == "open" and len(sys.argv) >= 5:
            result = open_time_capsule(sys.argv[2], sys.argv[4])
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("Unknown capsule command")
            sys.exit(1)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
