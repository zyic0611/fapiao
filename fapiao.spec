# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

block_cipher = None

rapidocr_datas, rapidocr_binaries, rapidocr_hiddenimports = collect_all(
  "rapidocr_onnxruntime"
)
onnx_datas, onnx_binaries, onnx_hiddenimports = collect_all("onnxruntime")

a = Analysis(
  ["app.py"],
  pathex=[],
  binaries=rapidocr_binaries + onnx_binaries,
  datas=rapidocr_datas + onnx_datas,
  hiddenimports=[
    "rapidocr_onnxruntime",
    "onnxruntime",
    "fitz",
    "numpy",
  ]
  + rapidocr_hiddenimports
  + onnx_hiddenimports,
  hookspath=[],
  hooksconfig={},
  runtime_hooks=[],
  excludes=[],
  win_no_prefer_redirects=False,
  win_private_assemblies=False,
  cipher=block_cipher,
  noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
  pyz,
  a.scripts,
  a.binaries,
  a.zipfiles,
  a.datas,
  [],
  name="发票识别",
  debug=False,
  bootloader_ignore_signals=False,
  strip=False,
  upx=True,
  upx_exclude=[],
  runtime_tmpdir=None,
  console=False,
  disable_windowed_traceback=False,
  argv_emulation=False,
  target_arch=None,
  codesign_identity=None,
  entitlements_file=None,
)
