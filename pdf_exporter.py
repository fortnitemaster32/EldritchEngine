import os
import re
from datetime import datetime

import fitz

PAGE_WIDTH, PAGE_HEIGHT = fitz.paper_size("a4")
MARGIN = 40
BODY_WIDTH = PAGE_WIDTH - 2 * MARGIN
BODY_HEIGHT = PAGE_HEIGHT - 2 * MARGIN


def _normalize_text(text: str) -> str:
    """Ensures text is compatible with standard PDF fonts while preserving meaning."""
    replacements = {
        # Only normalize if we fall back to basic fonts (triple dash is better than question mark)
        '\u00a0': ' ',   # non-breaking space
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


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


def _clean_engine_metadata(text: str) -> str:
    """Removes internal XML-like tags and engine metadata blocks from final output."""
    # Remove <critique>...</critique>
    text = re.sub(r'<critique>.*?</critique>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove <paragraph_plan>...</paragraph_plan>
    text = re.sub(r'<paragraph_plan>.*?</paragraph_plan>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove <editor_notes>...</editor_notes>
    text = re.sub(r'<editor_notes>.*?</editor_notes>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove specific lines that look like engine breadcrumbs
    text = re.sub(r'^\[CURRENTLY REVIEWING\].*$', '', text, flags=re.MULTILINE)
    return text.strip()


def _extract_title_from_markdown(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        match = re.match(r'^\s*#{1,2}\s+(.+)$', line)
        if match:
            return match.group(1).strip()
    return ""


def _tokenize_markdown(markdown_text: str) -> list[dict]:
    # First, clean the metadata
    markdown_text = _clean_engine_metadata(markdown_text)
    
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

    # Post-process for math blocks
    for item in items:
        if item["type"] == "paragraph":
            # Simple LaTeX detection for blocks like $$...$$
            if item["text"].startswith("$$") and item["text"].endswith("$$"):
                item["type"] = "math"
                item["text"] = item["text"].strip("$").strip()

    return items


def _find_system_font(names: list[str]) -> str | None:
    """Finds a system font path from a list of possible names across OSes."""
    search_paths = []
    if os.name == "nt": # Windows
        search_paths.append("C:/Windows/Fonts/")
    elif os.name == "posix": # macOS and Linux
        search_paths.extend([
            "/Library/Fonts/", "/System/Library/Fonts/", 
            "/usr/share/fonts/truetype/", "/usr/share/fonts/TTF/",
            os.path.expanduser("~/.local/share/fonts/")
        ])
    
    for base in search_paths:
        if not os.path.exists(base): continue
        for name in names:
            for ext in [".ttf", ".TTF"]:
                path = os.path.join(base, name + ext)
                if os.path.exists(path):
                    return path
    return None

def _get_safe_font(names: list[str], fallback: str) -> str:
    """Returns a valid font path or the fallback name."""
    path = _find_system_font(names)
    if path:
        try:
            # Test if it can be loaded
            f = fitz.Font(fontfile=path)
            return path
        except:
            pass
    return fallback

# Pre-resolve fonts once at startup
_SERIF = _get_safe_font(["times", "timesnewroman", "LiberationSerif-Regular"], "tiro")
_SERIF_BOLD = _get_safe_font(["timesbd", "timesnewromanbold", "LiberationSerif-Bold"], "tibo")
_SERIF_ITALIC = _get_safe_font(["timesi", "timesnewromanitalic", "LiberationSerif-Italic"], "tiit")

_SANS = _get_safe_font(["arial", "segoeui", "Helvetica", "LiberationSans-Regular"], "helv")
_SANS_BOLD = _get_safe_font(["arialbd", "segoeuib", "Helvetica-Bold", "LiberationSans-Bold"], "hebo")

_MONO = _get_safe_font(["consola", "courier", "LiberationMono-Regular"], "cour")

FONT_THEMES = {
    "Modern Sans": {
        "heading": _SANS_BOLD,
        "body": _SANS,
        "italic": _SANS,
        "bold": _SANS_BOLD,
        "mono": _MONO
    },
    "Classic Serif": {
        "heading": _SERIF_BOLD,
        "body": _SERIF,
        "italic": _SERIF_ITALIC,
        "bold": _SERIF_BOLD,
        "mono": _MONO
    },
    "Academic": {
        "heading": _SERIF_BOLD,
        "body": _SERIF,
        "italic": _SERIF_ITALIC,
        "bold": _SERIF_BOLD,
        "mono": _MONO
    }
}

def _wrap_text(text: str, font: fitz.Font, fontsize: float, max_width: float) -> list[str]:
    if not text:
        return [""]
    max_width -= 4
    words = re.split(r'(\s+)', text)
    lines = []
    current = ""
    for token in words:
        if not token:
            continue
        candidate = current + token
        try:
            if font.text_length(candidate, fontsize) <= max_width or not current:
                current = candidate
                continue
        except:
            pass
        lines.append(current.rstrip())
        current = token.lstrip()
    if current:
        lines.append(current.rstrip())
    return lines


def _setup_page_fonts(page: fitz.Page, theme_fonts: dict) -> dict:
    """Registers fonts on a specific page and returns a mapping of names."""
    mapping = {}
    for key, val in theme_fonts.items():
        # Only treat as a path if it looks like one and exists
        if isinstance(val, str) and (val.endswith(".ttf") or val.endswith(".TTF")) and os.path.isabs(val):
            font_name = f"F_{key}"
            try:
                page.insert_font(fontname=font_name, fontfile=val)
                mapping[key] = font_name
            except:
                mapping[key] = "helv" 
        else:
            mapping[key] = val
    return mapping

def _get_font_obj(font_spec: str) -> fitz.Font:
    """Helper to get a Font object safely for text wrapping."""
    try:
        if os.path.exists(font_spec):
            return fitz.Font(fontfile=font_spec)
        return fitz.Font(font_spec)
    except:
        return fitz.Font("helv")


def _new_page(doc: fitz.Document, theme_fonts: dict) -> tuple[fitz.Page, dict]:
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    font_mapping = _setup_page_fonts(page, theme_fonts)
    return page, font_mapping


def _render_items(doc: fitz.Document, items: list[dict], theme_fonts: dict, start_y: float = None) -> None:
    if start_y is not None and len(doc) > 0:
        page = doc[-1]
        font_mapping = _setup_page_fonts(page, theme_fonts)
        y = start_y
    else:
        page, font_mapping = _new_page(doc, theme_fonts)
        y = MARGIN

    for item in items:
        if "text" in item:
            item["text"] = _normalize_text(item["text"])
            
        if item["type"] == "spacer":
            y += 12
            continue

        if item["type"] == "heading":
            size = max(18 - (item["level"] - 1) * 2, 12)
            if y + size * 2.5 > PAGE_HEIGHT - MARGIN:
                page, font_mapping = _new_page(doc, theme_fonts)
                y = MARGIN
            text = item["text"]
            f_name = font_mapping["heading"] if item["level"] <= 2 else font_mapping["bold"]
            page.insert_textbox(fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + size * 2.5), text, fontname=f_name, fontsize=size, align=1)
            y += size * 1.8
            continue

        if item["type"] == "blockquote":
            f_italic = font_mapping["italic"]
            wrapped = _wrap_text(item["text"], _get_font_obj(theme_fonts["italic"]), 12, BODY_WIDTH - 40)
            if y + len(wrapped) * 20 > PAGE_HEIGHT - MARGIN:
                page, font_mapping = _new_page(doc, theme_fonts)
                y = MARGIN
            for line in wrapped:
                page.insert_textbox(fitz.Rect(MARGIN + 20, y, PAGE_WIDTH - MARGIN, y + 20), line, fontname=f_italic, fontsize=12, align=0)
                y += 18
            y += 10
            continue

        if item["type"] == "math":
            f_mono = font_mapping["mono"]
            wrapped = _wrap_text(item["text"], _get_font_obj(theme_fonts["mono"]), 11, BODY_WIDTH - 60)
            if y + len(wrapped) * 20 > PAGE_HEIGHT - MARGIN:
                page, font_mapping = _new_page(doc, theme_fonts)
                y = MARGIN
            for line in wrapped:
                page.insert_textbox(fitz.Rect(MARGIN + 30, y, PAGE_WIDTH - MARGIN, y + 20), line, fontname=f_mono, fontsize=11, align=1, color=(0.1, 0.1, 0.3))
                y += 18
            y += 15
            continue

        if item["type"] == "list":
            bullet = "•" if not item["prefix"].strip().isdigit() else f"{item['prefix']}"
            f_body = font_mapping["body"]
            wrapped = _wrap_text(f"{bullet} {item['text']}", _get_font_obj(theme_fonts["body"]), 12, BODY_WIDTH - 20)
            if y + len(wrapped) * 20 > PAGE_HEIGHT - MARGIN:
                page, font_mapping = _new_page(doc, theme_fonts)
                y = MARGIN
            for line in wrapped:
                page.insert_textbox(fitz.Rect(MARGIN + 20, y, PAGE_WIDTH - MARGIN, y + 20), line, fontname=f_body, fontsize=12, align=0)
                y += 18
            y += 4
            continue

        if item["type"] == "code":
            f_mono = font_mapping["mono"]
            code_lines = item["text"].splitlines()
            if y + len(code_lines) * 18 > PAGE_HEIGHT - MARGIN:
                page, font_mapping = _new_page(doc, theme_fonts)
                y = MARGIN
            for code_line in code_lines:
                wrapped = _wrap_text(code_line, _get_font_obj(theme_fonts["mono"]), 10, BODY_WIDTH - 20)
                for line in wrapped:
                    page.insert_textbox(fitz.Rect(MARGIN + 10, y, PAGE_WIDTH - MARGIN, y + 16), line, fontname=f_mono, fontsize=10, align=0)
                    y += 15
            y += 6
            continue

        if item["type"] == "paragraph":
            f_body = font_mapping["body"]
            wrapped = _wrap_text(item["text"], _get_font_obj(theme_fonts["body"]), 12, BODY_WIDTH)
            if y + len(wrapped) * 20 > PAGE_HEIGHT - MARGIN:
                page, font_mapping = _new_page(doc, theme_fonts)
                y = MARGIN
            for line in wrapped:
                page.insert_textbox(fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + 20), line, fontname=f_body, fontsize=12, align=0)
                y += 18
            y += 8
            continue


def _add_title_page(doc: fitz.Document, title: str, subtitle: str = "", summary: str = "", theme_fonts: dict = None) -> None:
    if theme_fonts is None:
        theme_fonts = FONT_THEMES["Modern Sans"]
    
    page, fonts = _new_page(doc, theme_fonts)
    
    # Elegant border lines
    shape = page.new_shape()
    shape.draw_line(fitz.Point(MARGIN, PAGE_HEIGHT*0.2), fitz.Point(PAGE_WIDTH-MARGIN, PAGE_HEIGHT*0.2))
    shape.draw_line(fitz.Point(MARGIN, PAGE_HEIGHT*0.8), fitz.Point(PAGE_WIDTH-MARGIN, PAGE_HEIGHT*0.8))
    shape.finish(width=1.0, color=(0.2, 0.2, 0.2))
    shape.commit()

    # Main Title
    title_rect = fitz.Rect(MARGIN, PAGE_HEIGHT * 0.28, PAGE_WIDTH - MARGIN, PAGE_HEIGHT * 0.5)
    title_fsize = 32 if len(title) < 40 else 24
    page.insert_textbox(title_rect, title.upper(), fontname=fonts["heading"], fontsize=title_fsize, align=1, color=(0, 0, 0))
    
    # Summary (if available) - Adds weight to the page
    if summary:
        summary_rect = fitz.Rect(MARGIN + 40, PAGE_HEIGHT * 0.5, PAGE_WIDTH - MARGIN - 40, PAGE_HEIGHT * 0.65)
        clean_summary = _normalize_text(summary)
        page.insert_textbox(summary_rect, clean_summary, fontname=fonts["italic"], fontsize=12, align=1, color=(0.2, 0.2, 0.2))

    # Subtitle / Generated On
    if subtitle:
        meta_rect = fitz.Rect(MARGIN, PAGE_HEIGHT * 0.68, PAGE_WIDTH - MARGIN, PAGE_HEIGHT * 0.72)
        page.insert_textbox(meta_rect, subtitle, fontname=fonts["body"], fontsize=11, align=1, color=(0.4, 0.4, 0.4))

    # Branding
    footer_rect = fitz.Rect(MARGIN, PAGE_HEIGHT - 60, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 30)
    page.insert_textbox(footer_rect, "ELD R I T C H   E N G I N E", fontname=fonts["heading"], fontsize=10, align=1, color=(0.6, 0.6, 0.6))


def _fill_toc_page(doc: fitz.Document, toc_page_index: int, toc_items: list, theme_fonts: dict) -> None:
    page = doc[toc_page_index]
    fonts = _setup_page_fonts(page, theme_fonts)
    
    y = MARGIN
    page.insert_textbox(fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + 50), "Table of Contents", fontname=fonts["heading"], fontsize=28, align=1)
    y += 70
    for title, pno in toc_items:
        if y + 30 > PAGE_HEIGHT - MARGIN:
            # For simplicity, we only support one page of TOC for now
            break
        rect = fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + 25)
        page.insert_textbox(rect, f"{title}", fontname=fonts["body"], fontsize=13, align=0)
        page.insert_textbox(rect, f"{pno}", fontname=fonts["body"], fontsize=13, align=2)
        y += 28


def export_markdown_file_to_pdf(input_path: str, output_path: str, title: str = None, font_theme: str = "Modern Sans") -> str:
    theme_fonts = FONT_THEMES.get(font_theme, FONT_THEMES["Modern Sans"])
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()
    title_text = title or _extract_title_from_markdown(content)
    doc = fitz.open()
    # Fixed: Use keyword arguments to avoid positional mismatch
    _add_title_page(doc, title_text, subtitle=f"Generated on {datetime.now().strftime('%B %d, %Y')}", theme_fonts=theme_fonts)
    _render_items(doc, _tokenize_markdown(content), theme_fonts=theme_fonts)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()
    return output_path


def _clean_chapter_title(title: str) -> str:
    # Remove planning metadata often found in EldritchEngine logs
    title = re.sub(r'\s*\*\*?\s*-\s*Core Topic/Goal.*$', '', title, flags=re.IGNORECASE)
    title = title.strip().rstrip("*").strip()
    return title


def export_book_dir_to_pdf(log_dir: str, book_title: str, output_path: str, font_theme: str = "Modern Sans") -> str:
    theme_fonts = FONT_THEMES.get(font_theme, FONT_THEMES["Modern Sans"])
    chapter_dir = os.path.join(log_dir, "chapters")
    # Sort chapter files numerically by the index in the filename (e.g. Chapter_1_...)
    chapter_files = sorted(
        [os.path.join(chapter_dir, fn) for fn in os.listdir(chapter_dir) if fn.lower().endswith('.md')],
        key=lambda x: int(re.search(r'Chapter_(\d+)', os.path.basename(x)).group(1)) if re.search(r'Chapter_(\d+)', os.path.basename(x)) else 0
    )

    # Try to load chapter titles and book summary from state.json
    state_titles = {}
    book_summary = ""
    state_path = os.path.join(log_dir, "state.json")
    if os.path.exists(state_path):
        try:
            import json
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
                book_summary = state.get("book_summary", "")
                for i, ch in enumerate(state.get("chapters", [])):
                    state_titles[i] = _clean_chapter_title(ch.get("title", ""))
        except:
            pass

    doc = fitz.open()
    _add_title_page(doc, book_title, f"Generated on {datetime.now().strftime('%B %d, %Y')} - EldritchEngine", summary=book_summary, theme_fonts=theme_fonts)
    
    # Create TOC placeholder
    toc_page, fonts = _new_page(doc, theme_fonts)
    toc_page_index = doc.page_count - 1
    
    toc_items = []
    for idx, chapter_path in enumerate(chapter_files):
        with open(chapter_path, "r", encoding="utf-8") as f:
            chapter_md = f.read()
        
        # Get title from state.json, then markdown, then filename
        raw_title = state_titles.get(idx) or _extract_title_from_markdown(chapter_md) or os.path.splitext(os.path.basename(chapter_path))[0]
        chapter_title = _clean_chapter_title(raw_title)
        chapter_title = _normalize_text(chapter_title)
        
        chapter_label = f"Chapter {idx + 1}"
        full_title = f"{chapter_label}: {chapter_title}"
        
        # Chapter Splash Page
        splash_page, fonts = _new_page(doc, theme_fonts)
        toc_items.append((full_title, doc.page_count)) 
        
        mid_y = PAGE_HEIGHT * 0.4
        splash_page.insert_textbox(fitz.Rect(MARGIN, mid_y, PAGE_WIDTH - MARGIN, mid_y + 40), chapter_label, fontname=fonts["heading"], fontsize=26, align=1)
        # Use a larger rectangle for the title to allow wrapping if still long
        splash_page.insert_textbox(fitz.Rect(MARGIN, mid_y + 50, PAGE_WIDTH - MARGIN, mid_y + 300), chapter_title, fontname=fonts["heading"], fontsize=42, align=1)
        
        # Chapter Content
        lines = chapter_md.splitlines()
        content = "\n".join(lines[1:]) if lines and lines[0].strip().startswith("#") else chapter_md
        _render_items(doc, _tokenize_markdown(content), theme_fonts=theme_fonts)

    _fill_toc_page(doc, toc_page_index, toc_items, theme_fonts)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()
    return output_path
