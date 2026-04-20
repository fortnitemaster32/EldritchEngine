import os
import re
from datetime import datetime

import fitz

PAGE_WIDTH, PAGE_HEIGHT = fitz.paper_size("a4")
MARGIN = 40
BODY_WIDTH = PAGE_WIDTH - 2 * MARGIN
BODY_HEIGHT = PAGE_HEIGHT - 2 * MARGIN


def _clean_inline_markdown(text: str) -> str:
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    text = re.sub(r'\s*\|\s*', ' | ', text)
    return text


def _extract_title_from_markdown(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        match = re.match(r'^\s*#\s+(.+)$', line)
        if match:
            return match.group(1).strip()
    return "Untitled Document"


def _tokenize_markdown(markdown_text: str) -> list[dict]:
    items = []
    in_code = False
    code_buffer = []

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip("\r\n")
        if line.strip().startswith("```"):
            if in_code:
                items.append({"type": "code", "text": "\n".join(code_buffer)})
                code_buffer = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_buffer.append(line)
            continue

        if not line.strip():
            items.append({"type": "spacer"})
            continue

        heading = re.match(r'^(#{1,6})\s+(.*)$', line)
        if heading:
            items.append({"type": "heading", "level": len(heading.group(1)), "text": _clean_inline_markdown(heading.group(2).strip())})
            continue

        blockquote = re.match(r'^>\s?(.*)$', line)
        if blockquote:
            items.append({"type": "blockquote", "text": _clean_inline_markdown(blockquote.group(1).strip())})
            continue

        list_match = re.match(r'^\s*([-\*\+]|\d+\.)\s+(.*)$', line)
        if list_match:
            prefix = list_match.group(1)
            content = _clean_inline_markdown(list_match.group(2).strip())
            items.append({"type": "list", "text": content, "prefix": prefix})
            continue

        items.append({"type": "paragraph", "text": _clean_inline_markdown(line.strip())})

    if in_code and code_buffer:
        items.append({"type": "code", "text": "\n".join(code_buffer)})

    return items


def _wrap_text(text: str, font: fitz.Font, fontsize: float, max_width: float) -> list[str]:
    if not text:
        return [""]
    words = re.split(r'(\s+)', text)
    lines = []
    current = ""
    for token in words:
        if not token:
            continue
        candidate = current + token
        if font.text_length(candidate, fontsize) <= max_width or not current:
            current = candidate
            continue
        lines.append(current.rstrip())
        current = token.lstrip()
    if current:
        lines.append(current.rstrip())
    return lines


def _new_page(doc: fitz.Document) -> fitz.Page:
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    return page


def _draw_lines(page: fitz.Page, lines: list[str], fontname: str, fontsize: float, start_y: float, indent: float = 0, align: int = 0) -> float:
    try:
        font = fitz.Font(fontname)
    except Exception as e:
        print(f"Warning: Could not load font '{fontname}'. Using default text drawing method. Error: {e}")
        return -1 # Indicate failure to draw lines
    y = start_y
    line_height = fontsize * 1.35
    max_width = BODY_WIDTH - indent
    for text in lines:
        if y + line_height > PAGE_HEIGHT - MARGIN:
            return -1
        rect = fitz.Rect(MARGIN + indent, y, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN)
        page.insert_textbox(rect, text, fontname=fontname, fontsize=fontsize, align=align)
        y += line_height
    return y


def _render_items(doc: fitz.Document, items: list[dict], start_y: float = None) -> None:
    if start_y is not None and len(doc) > 0:
        page = doc[-1]
        y = start_y
    else:
        page = _new_page(doc)
        y = MARGIN
    for item in items:
        if item["type"] == "spacer":
            y += 12
            continue

        if item["type"] == "heading":
            size = max(36 - (item["level"] - 1) * 4, 16)
            if y + size * 1.4 > PAGE_HEIGHT - MARGIN:
                page = _new_page(doc)
                y = MARGIN
            text = item["text"]
            page.insert_textbox(fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN), text, fontname="hebo", fontsize=size, align=1)
            y += size * 1.8
            continue

        if item["type"] == "blockquote":
            wrapped = _wrap_text(item["text"], fitz.Font("helv"), 12, BODY_WIDTH - 20)
            if y + len(wrapped) * 16 > PAGE_HEIGHT - MARGIN:
                page = _new_page(doc)
                y = MARGIN
            page.insert_textbox(fitz.Rect(MARGIN + 20, y, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN), "\n".join(wrapped), fontname="heit", fontsize=12, align=0)
            y += len(wrapped) * 16 + 10
            continue

        if item["type"] == "list":
            bullet = "•" if not item["prefix"].strip().isdigit() else f"{item['prefix']}"
            wrapped = _wrap_text(f"{bullet} {item['text']}", fitz.Font("helv"), 12, BODY_WIDTH - 20)
            if y + len(wrapped) * 16 > PAGE_HEIGHT - MARGIN:
                page = _new_page(doc)
                y = MARGIN
            for line in wrapped:
                page.insert_textbox(fitz.Rect(MARGIN + 20, y, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN), line, fontname="helv", fontsize=12, align=0)
                y += 16
            y += 4
            continue

        if item["type"] == "code":
            code_lines = item["text"].splitlines()
            if y + len(code_lines) * 14 > PAGE_HEIGHT - MARGIN:
                page = _new_page(doc)
                y = MARGIN
            for code_line in code_lines:
                wrapped = _wrap_text(code_line, fitz.Font("cour"), 10, BODY_WIDTH - 20)
                for line in wrapped:
                    page.insert_textbox(fitz.Rect(MARGIN + 10, y, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN), line, fontname="cour", fontsize=10, align=0)
                    y += 14
            y += 6
            continue

        if item["type"] == "paragraph":
            wrapped = _wrap_text(item["text"], fitz.Font("helv"), 12, BODY_WIDTH)
            if y + len(wrapped) * 16 > PAGE_HEIGHT - MARGIN:
                page = _new_page(doc)
                y = MARGIN
            for line in wrapped:
                page.insert_textbox(fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN), line, fontname="helv", fontsize=12, align=0)
                y += 16
            y += 8
            continue


def _add_title_page(doc: fitz.Document, title: str, subtitle: str = "") -> None:
    try:
        # Attempt to use a reliable font for the title page elements
        title_font = fitz.Font("hebo")
        subtitle_font = fitz.Font("helv")
    except Exception as e:
        print(f"Warning: Could not load fonts for title page. Using default text drawing method. Error: {e}")
        return # Exit function if essential fonts cannot be loaded

    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    title_rect = fitz.Rect(MARGIN, PAGE_HEIGHT * 0.28, PAGE_WIDTH - MARGIN, PAGE_HEIGHT * 0.48)
    page.insert_textbox(title_rect, title, fontname="hebo", fontsize=48, align=1)
    if subtitle:
        subtitle_rect = fitz.Rect(MARGIN, PAGE_HEIGHT * 0.52, PAGE_WIDTH - MARGIN, PAGE_HEIGHT * 0.6)
        page.insert_textbox(subtitle_rect, subtitle, fontname="helv", fontsize=16, align=1)


def export_markdown_file_to_pdf(input_path: str, output_path: str, title: str = None) -> str:
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    title_text = title or _extract_title_from_markdown(content)
    subtitle = f"Generated on {datetime.now().strftime('%B %d, %Y')}"

    doc = fitz.open()
    _add_title_page(doc, title_text, subtitle)
    items = _tokenize_markdown(content)
    _render_items(doc, items)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()
    return output_path


def export_book_dir_to_pdf(log_dir: str, book_title: str, output_path: str) -> str:
    chapter_dir = os.path.join(log_dir, "chapters")
    if not os.path.isdir(chapter_dir):
        raise FileNotFoundError(f"No chapters directory found at {chapter_dir}")

    chapter_files = sorted(
        [os.path.join(chapter_dir, fn) for fn in os.listdir(chapter_dir) if fn.lower().endswith('.md')]
    )

    doc = fitz.open()
    _add_title_page(doc, book_title, f"Generated on {datetime.now().strftime('%B %d, %Y')} - EldritchEngine")

    for chapter_path in chapter_files:
        with open(chapter_path, "r", encoding="utf-8") as f:
            chapter_md = f.read()

        chapter_title = _extract_title_from_markdown(chapter_md) or os.path.splitext(os.path.basename(chapter_path))[0]
        chapter_content = chapter_md
        page = _new_page(doc)
        page.insert_textbox(fitz.Rect(MARGIN, PAGE_HEIGHT * 0.18, PAGE_WIDTH - MARGIN, PAGE_HEIGHT * 0.28), chapter_title, fontname="hebo", fontsize=36, align=1)
        y_start = PAGE_HEIGHT * 0.5
        items = _tokenize_markdown(chapter_content)
        _render_items(doc, items, start_y=y_start)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()
    return output_path
