"""发票号码提取：PDF 第一页文本优先，OCR 兜底。"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Iterator, Optional

import fitz
import numpy as np

_OCR_ENGINE = None
_OCR_LOCK = threading.Lock()

INVOICE_NUMBER_PATTERN = re.compile(
    r"发票号码\s*[：:]\s*(\d{20}|\d{12}|\d{8})"
)
INVOICE_NUMBER_LOOSE_PATTERN = re.compile(
    r"发票号\s*码\s*[：:]\s*(\d{20}|\d{12}|\d{8})"
)
INVOICE_NUMBER_FLEX_PATTERN = re.compile(
    r"发票号码[^\d]{0,8}(\d{20}|\d{12}|\d{8})"
)


class ExtractionError(Exception):
    """提取过程中发生的可预期错误。"""


def _normalize_ocr_text(text: str) -> str:
    cleaned = text.replace("　", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace("发 票 号 码", "发票号码")
    cleaned = cleaned.replace("发票号 码", "发票号码")
    cleaned = cleaned.replace("发 票号码", "发票号码")
    cleaned = re.sub(r"(?<=\d) (?=\d)", "", cleaned)
    return cleaned


def _match_invoice_number(text: str) -> Optional[str]:
    if not text:
        return None

    normalized = _normalize_ocr_text(text)
    for pattern in (
        INVOICE_NUMBER_PATTERN,
        INVOICE_NUMBER_LOOSE_PATTERN,
        INVOICE_NUMBER_FLEX_PATTERN,
    ):
        match = pattern.search(normalized)
        if match:
            return match.group(1)
    return None


def _get_ocr_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def init_ocr_engine() -> None:
    """预加载 OCR 引擎，避免首次识别时等待。"""
    _get_ocr_engine()


def _text_chunk_from_dict(result: dict) -> str:
    lines: list[str] = []
    for block in result.get("blocks", []):
        for line in block.get("lines", []):
            line_text = "".join(span["text"] for span in line.get("spans", []))
            if line_text:
                lines.append(line_text)
    return "\n".join(lines)


def _iter_page_text_chunks(page: fitz.Page) -> Iterator[str]:
    """按速度由快到慢产出文本块（跳过 xml/rawdict）。"""
    try:
        text = page.get_text("text")
        if text:
            yield text
    except Exception:
        pass

    try:
        blocks = page.get_text("blocks")
        if blocks:
            chunk = "\n".join(b[4] for b in blocks if b[6] == 0)
            if chunk:
                yield chunk
    except Exception:
        pass

    try:
        result = page.get_text("dict")
        if result:
            chunk = _text_chunk_from_dict(result)
            if chunk:
                yield chunk
    except Exception:
        pass

    try:
        words = page.get_text("words")
        if words:
            chunk = " ".join(w[4] for w in words)
            if chunk:
                yield chunk
    except Exception:
        pass


def _extract_invoice_number_from_page(page: fitz.Page) -> Optional[str]:
    """逐级提取文本，命中即停；最后再试拼接结果。"""
    parts: list[str] = []
    for chunk in _iter_page_text_chunks(page):
        number = _match_invoice_number(chunk)
        if number:
            return number
        parts.append(chunk)
    if parts:
        return _match_invoice_number("\n".join(parts))
    return None


def _run_ocr(image: np.ndarray):
    with _OCR_LOCK:
        return _get_ocr_engine()(image)


def _ocr_page_top(image: np.ndarray) -> str:
    """对图片上半部分执行 OCR（发票号码通常在顶部）。"""
    h = image.shape[0]
    top_region = image[: max(int(h * 0.4), 1), :, :]
    result, _ = _run_ocr(top_region)
    if not result:
        return ""
    return "\n".join(line[1] for line in result)


def _render_and_ocr(page: fitz.Page) -> str:
    """渲染页面并用 OCR 识别；顶部区域优先，未匹配时再整页。"""
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )
    if pixmap.n == 4:
        image = image[:, :, :3]

    text = _ocr_page_top(image)
    if _match_invoice_number(text):
        return text

    result, _ = _run_ocr(image)
    if not result:
        return ""
    return "\n".join(line[1] for line in result)


def extract_invoice_number(pdf_path: str | Path) -> str:
    """
    从 PDF 第一页提取发票号码。

    返回发票号码字符串；未识别到时抛出 ExtractionError。
    """
    path = Path(pdf_path)
    if not path.exists():
        raise ExtractionError(f"文件不存在: {path.name}")
    if path.suffix.lower() != ".pdf":
        raise ExtractionError(f"不是 PDF 文件: {path.name}")

    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise ExtractionError(f"无法打开 PDF: {path.name}") from exc

    try:
        if doc.page_count == 0:
            raise ExtractionError(f"PDF 无页面: {path.name}")

        page = doc[0]

        # 1. 文本层提取（快路径，命中即停）
        number = _extract_invoice_number_from_page(page)
        if number:
            return number

        # 2. OCR 兜底
        ocr_text = _render_and_ocr(page)
        number = _match_invoice_number(ocr_text)
        if number:
            return number

        raise ExtractionError(f"未识别到发票号码: {path.name}")
    finally:
        doc.close()


def process_pdf_file(pdf_path: str) -> dict[str, str]:
    """供外部批量调用的顶层函数。"""
    path = Path(pdf_path)
    try:
        invoice_number = extract_invoice_number(pdf_path)
        return {
            "filename": path.name,
            "invoice_number": invoice_number,
            "status": "成功",
        }
    except ExtractionError as exc:
        return {
            "filename": path.name,
            "invoice_number": "",
            "status": str(exc),
        }
    except Exception as exc:
        return {
            "filename": path.name,
            "invoice_number": "",
            "status": f"识别失败: {exc}",
        }
