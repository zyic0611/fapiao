"""发票号码提取：PDF 第一页文本优先，OCR 兜底。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import fitz
import numpy as np

_OCR_ENGINE = None

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


def _extract_text_via_all_methods(page: fitz.Page) -> str:
    """尝试多种方式提取文本，返回所有结果的拼接。"""
    parts: list[str] = []
    for method in ("text", "blocks", "dict", "rawdict", "words", "xml"):
        try:
            result = page.get_text(method)
            if not result:
                continue
            if method in ("text", "xml"):
                parts.append(str(result))
            elif method == "blocks":
                parts.append("\n".join(b[4] for b in result if b[6] == 0))
            elif method == "dict":
                for block in result.get("blocks", []):
                    for line in block.get("lines", []):
                        line_text = "".join(
                            span["text"] for span in line.get("spans", [])
                        )
                        parts.append(line_text)
            elif method == "rawdict":
                for block in result.get("blocks", []):
                    for line in block.get("lines", []):
                        line_text = "".join(
                            span["text"] for span in line.get("spans", [])
                        )
                        parts.append(line_text)
            elif method == "words":
                parts.append(" ".join(w[4] for w in result))
        except Exception:
            continue
    return "\n".join(parts)


def _ocr_page_top(image: np.ndarray) -> str:
    """对图片上半部分执行 OCR（发票号码通常在顶部）。"""
    h = image.shape[0]
    top_region = image[: max(int(h * 0.4), 1), :, :]
    result, _ = _get_ocr_engine()(top_region)
    if not result:
        return ""
    return "\n".join(line[1] for line in result)


def _render_and_ocr(page: fitz.Page) -> str:
    """渲染页面顶部区域并用 OCR 识别。"""
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )
    if pixmap.n == 4:
        image = image[:, :, :3]

    text = _ocr_page_top(image)
    if text:
        return text

    # 顶部没找到则 OCR 整页
    result, _ = _get_ocr_engine()(image)
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

        # 1. 尝试多种文本提取方式
        combined_text = _extract_text_via_all_methods(page)
        number = _match_invoice_number(combined_text)
        if number:
            return number

        # 2. OCR 兜底（仅识别页面顶部区域）
        ocr_text = _render_and_ocr(page)
        number = _match_invoice_number(ocr_text)
        if number:
            return number

        raise ExtractionError(f"未识别到发票号码: {path.name}")
    finally:
        doc.close()
