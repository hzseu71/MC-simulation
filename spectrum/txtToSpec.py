#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert 2-column spectrum (E[eV] intensity) → MC-GPU style .spec (UTF-8)

步骤：
1. 确保 raw_spectrum.txt 位于与脚本相同目录或修改 INPUT_FILE 路径
2. 执行：python convert_to_spec.py
   将生成 formatted_spectrum.spec（UTF-8）
"""

from pathlib import Path
import numpy as np

# ─────────── 可按需修改 ─────────── #
INPUT_FILE   = Path("./spectrum100_Copper0.1mm.txt")        # ← 两列原始能谱文件
OUTPUT_FILE  = Path("./Spectrum100_Copper0.1mm.spc") # ← 目标 .spc 文件

HEADER_LINES = [
    "#  Converted spectrum (two-column → MC-GPU style)",
    "#  Source file: raw_spectrum.txt",
    "#  Edit this header as needed.",
]

SCALE_FACTOR = 1.0        # 整体缩放强度（1.0 = 不变）
ENERGY_FMT   = "{:4.1f}e3"   # 8.0e3, 8.5e3 … 的格式
INTENS_FMT   = "{:12.6g}"    # 强度：科学计数宽 12
# ─────────────────────────────── #

# 1) 读取数据
data = np.loadtxt(INPUT_FILE)
energy_eV, flux = data[:, 0], data[:, 1]

# 2) 过滤掉非正强度
mask = flux > 0.0
energy_eV, flux = energy_eV[mask], flux[mask]

# 3) 写入 .spec（UTF-8）
with open(OUTPUT_FILE, "w", encoding="utf-8") as fout:
    for line in HEADER_LINES:
        fout.write(line + "\n")
    fout.write("#\n#  Energy [eV]    Num. photons/(mm^2*keV)\n")
    fout.write("# ----------------------------------------------------\n")
    for e, p in zip(energy_eV, flux * SCALE_FACTOR):
        fout.write(f"{ENERGY_FMT.format(e / 1e3)}  {INTENS_FMT.format(p)}\n")

print(f"✓ 已生成 UTF-8 文件：{OUTPUT_FILE}  （共 {len(energy_eV)} 行数据）")
