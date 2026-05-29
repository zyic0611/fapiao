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
  """清洗 OCR 文本，合并被拆开的字段名与数字。"""
  cleaned = text.replace("\u3000", " ")
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


def _ocr_page_image(page: fitz.Page) -> str:
  pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
  image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
    pixmap.height, pixmap.width, pixmap.n
  )
  if pixmap.n == 4:
    image = image[:, :, :3]

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
    text = page.get_text("text") or ""
    number = _match_invoice_number(text)
    if number:
      return number

    ocr_text = _ocr_page_image(page)
    number = _match_invoice_number(ocr_text)
    if number:
      return number

    raise ExtractionError(f"未识别到发票号码: {path.name}")
  finally:
    doc.close()
