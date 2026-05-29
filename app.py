"""发票 PDF 识别工具 - Tkinter 界面。"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from openpyxl import Workbook

from extractor import ExtractionError, extract_invoice_number, init_ocr_engine


class InvoiceApp(tk.Tk):
  def __init__(self) -> None:
    super().__init__()
    self.title("发票识别")
    self.geometry("860x520")
    self.minsize(720, 420)

    # 后台预加载 OCR 模型，避免首次识别时等待
    threading.Thread(target=init_ocr_engine, daemon=True).start()

    self.selected_files: list[Path] = []
    self.results: list[dict[str, str]] = []
    self._worker: threading.Thread | None = None

    self._build_ui()

  def _build_ui(self) -> None:
    toolbar = ttk.Frame(self, padding=10)
    toolbar.pack(fill=tk.X)

    ttk.Button(toolbar, text="选择 PDF 文件", command=self._choose_files).pack(
      side=tk.LEFT
    )
    ttk.Button(toolbar, text="选择文件夹", command=self._choose_folder).pack(
      side=tk.LEFT, padx=(8, 0)
    )
    self.recognize_btn = ttk.Button(
      toolbar, text="开始识别", command=self._start_recognition
    )
    self.recognize_btn.pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(toolbar, text="导出 Excel", command=self._export_excel).pack(
      side=tk.LEFT, padx=(8, 0)
    )
    ttk.Button(toolbar, text="清空", command=self._clear_all).pack(
      side=tk.LEFT, padx=(8, 0)
    )

    self.file_label = ttk.Label(toolbar, text="未选择文件")
    self.file_label.pack(side=tk.LEFT, padx=(16, 0))

    table_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
    table_frame.pack(fill=tk.BOTH, expand=True)

    columns = ("filename", "invoice_number", "status")
    self.tree = ttk.Treeview(
      table_frame, columns=columns, show="headings", selectmode="browse"
    )
    self.tree.heading("filename", text="文件名")
    self.tree.heading("invoice_number", text="发票号码")
    self.tree.heading("status", text="状态")
    self.tree.column("filename", width=360, anchor=tk.W)
    self.tree.column("invoice_number", width=220, anchor=tk.W)
    self.tree.column("status", width=220, anchor=tk.W)

    scrollbar = ttk.Scrollbar(
      table_frame, orient=tk.VERTICAL, command=self.tree.yview
    )
    self.tree.configure(yscrollcommand=scrollbar.set)
    self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    self.status_var = tk.StringVar(value="就绪")
    status_bar = ttk.Label(
      self, textvariable=self.status_var, anchor=tk.W, padding=(10, 6)
    )
    status_bar.pack(fill=tk.X, side=tk.BOTTOM)

  def _choose_files(self) -> None:
    filenames = filedialog.askopenfilenames(
      title="选择 PDF 文件",
      filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
    )
    if not filenames:
      return

    self.selected_files = [Path(name) for name in filenames]
    self.file_label.config(text=f"已选择 {len(self.selected_files)} 个文件")
    self.status_var.set("已选择文件，点击“开始识别”")

  def _choose_folder(self) -> None:
    folder = filedialog.askdirectory(title="选择包含 PDF 的文件夹")
    if not folder:
      return

    self.selected_files = sorted(Path(folder).glob("*.pdf"))
    if not self.selected_files:
      messagebox.showinfo("提示", "所选文件夹中没有 PDF 文件")
      return

    self.file_label.config(text=f"已选择 {len(self.selected_files)} 个文件")
    self.status_var.set("已选择文件，点击“开始识别”")

  def _clear_all(self) -> None:
    if self._worker and self._worker.is_alive():
      messagebox.showwarning("提示", "正在识别中，请稍候")
      return

    self.selected_files = []
    self.results = []
    for item in self.tree.get_children():
      self.tree.delete(item)
    self.file_label.config(text="未选择文件")
    self.status_var.set("就绪")

  def _start_recognition(self) -> None:
    if self._worker and self._worker.is_alive():
      return
    if not self.selected_files:
      messagebox.showinfo("提示", "请先选择 PDF 文件")
      return

    self.recognize_btn.config(state=tk.DISABLED)
    for item in self.tree.get_children():
      self.tree.delete(item)
    self.results = []
    self.status_var.set("识别中...")

    self._worker = threading.Thread(target=self._run_recognition, daemon=True)
    self._worker.start()

  def _run_recognition(self) -> None:
    for index, pdf_path in enumerate(self.selected_files, start=1):
      self.after(
        0,
        lambda i=index, total=len(self.selected_files), name=pdf_path.name: self.status_var.set(
          f"识别中 ({i}/{total}): {name}"
        ),
      )

      try:
        invoice_number = extract_invoice_number(pdf_path)
        row = {
          "filename": pdf_path.name,
          "invoice_number": invoice_number,
          "status": "成功",
        }
      except ExtractionError as exc:
        row = {
          "filename": pdf_path.name,
          "invoice_number": "",
          "status": str(exc),
        }
      except Exception as exc:
        row = {
          "filename": pdf_path.name,
          "invoice_number": "",
          "status": f"识别失败: {exc}",
        }

      self.results.append(row)
      self.after(0, lambda r=row: self._append_row(r))

    self.after(0, self._finish_recognition)

  def _append_row(self, row: dict[str, str]) -> None:
    self.tree.insert(
      "",
      tk.END,
      values=(row["filename"], row["invoice_number"], row["status"]),
    )

  def _finish_recognition(self) -> None:
    success_count = sum(1 for row in self.results if row["status"] == "成功")
    self.status_var.set(
      f"完成：成功 {success_count}/{len(self.results)}"
    )
    self.recognize_btn.config(state=tk.NORMAL)

  def _export_excel(self) -> None:
    if not self.results:
      messagebox.showinfo("提示", "没有可导出的结果")
      return

    save_path = filedialog.asksaveasfilename(
      title="导出 Excel",
      defaultextension=".xlsx",
      filetypes=[("Excel 文件", "*.xlsx")],
      initialfile="发票识别结果.xlsx",
    )
    if not save_path:
      return

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "识别结果"
    sheet.append(["文件名", "发票号码", "状态"])

    for row in self.results:
      sheet.append([row["filename"], row["invoice_number"], row["status"]])

    for cell in sheet["B"][1:]:
      cell.number_format = "@"

    sheet.column_dimensions["A"].width = 40
    sheet.column_dimensions["B"].width = 24
    sheet.column_dimensions["C"].width = 24

    workbook.save(save_path)

    self.status_var.set(f"已导出: {Path(save_path).name}")
    messagebox.showinfo("导出成功", f"结果已保存到:\n{save_path}")


def main() -> None:
  app = InvoiceApp()
  app.mainloop()


if __name__ == "__main__":
  main()
