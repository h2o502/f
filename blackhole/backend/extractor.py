"""文件内容提取器"""
import os
from pathlib import Path


def extract_text(file_path: str) -> str:
    """提取文件文本内容"""
    path = Path(file_path)
    if not path.exists():
        return ""

    ext = path.suffix.lower()

    try:
        if ext in (".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm",
                    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".go",
                    ".rs", ".rb", ".php", ".sh", ".bat", ".ps1", ".log", ".ini",
                    ".yaml", ".yml", ".toml", ".cfg", ".conf"):
            return _extract_plain(file_path, ext)
        elif ext == ".pdf":
            return _extract_pdf(file_path)
        elif ext in (".docx", ".doc"):
            return _extract_docx(file_path)
        elif ext in (".xlsx", ".xls"):
            return _extract_xlsx(file_path)
        elif ext in (".pptx", ".ppt"):
            return _extract_pptx(file_path)
        else:
            return f"[不支持的文件格式: {ext}]"
    except Exception as e:
        return f"[提取失败: {str(e)}]"


def _extract_plain(file_path: str, ext: str) -> str:
    """提取纯文本文件"""
    encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            # 限制长度，避免超大文件
            if len(content) > 50000:
                content = content[:50000] + "\n...[内容已截断]"
            return content
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "[无法解码文件内容]"


def _extract_pdf(file_path: str) -> str:
    """提取 PDF 文本"""
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    texts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            texts.append(text)
        if i >= 50:  # 最多提取50页
            texts.append("...[仅提取前50页]")
            break
    content = "\n\n".join(texts)
    if len(content) > 50000:
        content = content[:50000] + "\n...[内容已截断]"
    return content or "[PDF 无可提取文本]"


def _extract_docx(file_path: str) -> str:
    """提取 Word 文档文本"""
    from docx import Document
    doc = Document(file_path)
    texts = []
    for para in doc.paragraphs:
        if para.text.strip():
            texts.append(para.text)
    # 提取表格内容
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells)
            if row_text.strip(" |"):
                texts.append(row_text)
    content = "\n".join(texts)
    if len(content) > 50000:
        content = content[:50000] + "\n...[内容已截断]"
    return content or "[Word 文档无可提取文本]"


def _extract_xlsx(file_path: str) -> str:
    """提取 Excel 文本"""
    from openpyxl import load_workbook
    wb = load_workbook(file_path, read_only=True, data_only=True)
    texts = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        texts.append(f"=== 工作表: {sheet_name} ===")
        row_count = 0
        for row in ws.iter_rows(values_only=True):
            row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
            if row_text.strip(" |"):
                texts.append(row_text)
            row_count += 1
            if row_count >= 200:
                texts.append("...[仅提取前200行]")
                break
    wb.close()
    content = "\n".join(texts)
    if len(content) > 50000:
        content = content[:50000] + "\n...[内容已截断]"
    return content or "[Excel 无可提取文本]"


def _extract_pptx(file_path: str) -> str:
    """提取 PPT 文本"""
    from pptx import Presentation
    prs = Presentation(file_path)
    texts = []
    for i, slide in enumerate(prs.slides):
        texts.append(f"=== 幻灯片 {i+1} ===")
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                texts.append(shape.text)
        if i >= 30:
            texts.append("...[仅提取前30页]")
            break
    content = "\n".join(texts)
    if len(content) > 50000:
        content = content[:50000] + "\n...[内容已截断]"
    return content or "[PPT 无可提取文本]"


def get_file_info(file_path: str) -> dict:
    """获取文件基本信息"""
    path = Path(file_path)
    stat = path.stat()
    return {
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size": stat.st_size,
        "created": stat.st_ctime,
        "modified": stat.st_mtime,
    }
