# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：WordMem Windows 桌面应用（目录模式）。

构建：  .venv/Scripts/pyinstaller WordMem.spec --noconfirm
产物：  dist/WordMem/WordMem.exe
"""
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        # 词库种子数据随包分发（frozen 模式下 __file__ 指向 _MEIPASS，路径规则一致）
        (str(ROOT / "src" / "wordmem" / "resources" / "data"),
         "wordmem/resources/data"),
    ],
    hiddenimports=[
        "pyttsx3.drivers",
        "pyttsx3.drivers.sapi5",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WordMem",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,               # GUI 程序，不显示控制台
    icon=str(ROOT / "packaging" / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="WordMem",
)
