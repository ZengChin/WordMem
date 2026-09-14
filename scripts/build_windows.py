# -*- coding: utf-8 -*-
"""WordMem Windows 一键构建：PyInstaller 打包 + Inno Setup 生成 setup.exe。

用法（在仓库根目录）：
    .venv\\Scripts\\python scripts\\build_windows.py            # 完整构建
    .venv\\Scripts\\python scripts\\build_windows.py --skip-exe  # 跳过 exe 打包
    .venv\\Scripts\\python scripts\\build_windows.py --skip-installer

产物：
    dist/WordMem/WordMem.exe            免安装目录版
    dist/WordMem-<版本>-setup.exe       Inno Setup 安装包
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISL = ROOT / "packaging" / "Languages" / "ChineseSimplified.isl"

# 中文语言包下载源（按序尝试，全部失败则安装向导回退英文，不阻断构建）
ISL_URLS = (
    "https://cdn.jsdelivr.net/gh/jrsoftware/issrc@main/"
    "Files/Languages/ChineseSimplified.isl",
    "https://raw.githubusercontent.com/jrsoftware/issrc/main/"
    "Files/Languages/ChineseSimplified.isl",
)


def _iscc_candidates() -> list[Path | None]:
    """ISCC.exe 常见安装位置（winget 用户级 / choco / 官方安装器）。"""
    local = os.environ.get("LOCALAPPDATA")
    return [
        ROOT / "packaging" / "ISCC.exe",
        Path(local) / "Programs" / "Inno Setup 6" / "ISCC.exe" if local else None,
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]


def read_version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def run(cmd: list[str]) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT)


def build_exe() -> None:
    # 用当前解释器运行 PyInstaller，兼容本地 .venv 与 CI 系统 Python
    probe = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        capture_output=True, text=True, cwd=ROOT)
    if probe.returncode != 0:
        sys.exit("未找到 PyInstaller，请先执行: pip install pyinstaller")
    run([sys.executable, "-m", "PyInstaller", "WordMem.spec", "--noconfirm", "--clean"])


def ensure_chinese_isl() -> None:
    if ISL.exists() and ISL.stat().st_size > 10_000:
        return
    ISL.parent.mkdir(parents=True, exist_ok=True)
    for url in ISL_URLS:
        try:
            print("+ 下载中文语言包:", url, flush=True)
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = resp.read()
            if len(data) > 10_000:
                ISL.write_bytes(data)
                return
        except Exception as exc:  # 网络失败继续尝试下一个源
            print("  失败:", exc, flush=True)
    print("警告：中文语言包下载失败，安装向导将回退英文界面。", flush=True)


def find_iscc() -> Path:
    for cand in _iscc_candidates():
        if cand and cand.exists():
            return cand
    which = shutil.which("ISCC")
    if which:
        return Path(which)
    sys.exit(
        "未找到 Inno Setup（ISCC.exe）。请安装后重试：\n"
        "  winget install --id JRSoftware.InnoSetup -e"
    )


def build_installer(version: str) -> None:
    ensure_chinese_isl()
    iscc = find_iscc()
    run([iscc, f"/DAPP_VERSION={version}",
         ROOT / "packaging" / "installer.iss"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-exe", action="store_true", help="跳过 PyInstaller 打包")
    ap.add_argument("--skip-installer", action="store_true", help="跳过 Inno Setup")
    args = ap.parse_args()

    version = read_version()
    print(f"WordMem v{version}\n")
    if not args.skip_exe:
        build_exe()
    if not args.skip_installer:
        build_installer(version)
    print("\n构建完成，产物见 dist/")


if __name__ == "__main__":
    main()
