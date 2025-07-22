#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a 10 cm × (变量厚度) × 10 cm multi-material phantom.
• 体素值 = 材料 ID（uint8，可自行改成 uint16）
• 输出二进制 .raw 或 .raw.gz（MC-GPU 能直接读取）
• 密度不写入文件——在 .in 的 [SECTION MATERIAL FILE LIST]
  内用 density= 覆盖即可
"""

import numpy as np
import gzip, os, time

# ────────────────────────── 1. 基本参数 ──────────────────────────
# Phantom 像素尺寸 (X,Z 方向固定 10 cm/0.1 cm = 100 像素)
VOX_NX, VOX_NZ   = 100, 100     # 每层 100 × 100
VOX_SIZE_CM      = 0.1          # 各向 0.1 cm

# 厚度相关参数（Y 方向随 PMMA 厚度而变）
PMMA_OFFSET_Y    = 50           # 顶部留空气 50 像素

# 材料 ID（≤255 即可用 uint8；>255 请用 uint16）
AirID, PMMAID, Iodine5ID, FeID       = 1, 2, 3, 4
TaID, PtID, BaID, BoneID, CO2ID      = 5, 6, 7, 8, 9
Iodine2ID                             = 10

# 各材料块厚度（Y 方向的层数，像素为单位）
thickness_iodine_2 = 2
thickness_iodine_5 = 5
thickness_fe       = 1
thickness_ta       = 1
thickness_pt       = 1
thickness_ba       = 50
thickness_bone     = 40
thickness_co2_2    = 2
thickness_co2_5    = 5

# 输出目录
OUT_DIR   = "./"
os.makedirs(OUT_DIR, exist_ok=True)

# ────────────────────────── 2. 保存 RAW 的辅助函数 ──────────────────────────
def save_as_raw(mat_id: np.ndarray,
                pmma_thickness: int,
                out_dir: str = OUT_DIR,
                compress_gz: bool = True) -> str:
    """把材料 ID 数组写成 .raw(.gz)，返回文件名（含扩展名）"""
    raw_name = f"P{pmma_thickness}mm_Muti_QM_607_5.0.raw"
    raw_path = os.path.join(out_dir,
                            raw_name + (".gz" if compress_gz else ""))
    t0 = time.time()
    if compress_gz:
        with gzip.open(raw_path, "wb", compresslevel=6) as fp:
            fp.write(mat_id.astype(np.uint8).tobytes(order="C"))
    else:
        mat_id.astype(np.uint8).tofile(raw_path)
    print(f"→  {raw_path}  写入完成，用时 {time.time()-t0:.2f}s")
    return raw_name + (".gz" if compress_gz else "")

# ────────────────────────── 3. 主函数：生成体素数组并写 RAW ──────────────────────────
def build_phantom_and_dump(pmma_thickness: int):
    """
    生成材料 ID 体素数组 (uint8) 并保存为 RAW
    """
    vox_ny = pmma_thickness + PMMA_OFFSET_Y              # Y 方向尺寸
    mat_id = np.full((VOX_NX, vox_ny, VOX_NZ),
                     fill_value=AirID, dtype=np.uint8)   # 默认填空气

    half = 5                                             # 方块半边 = 5 像素
    # ---- PMMA 板 ----
    mat_id[:, PMMA_OFFSET_Y:PMMA_OFFSET_Y+pmma_thickness, :] = PMMAID

    # ---- 各材料方块（按您给定坐标） ----
    def fill_block(cx, cz, topY, height, ID):
        for y in range(topY, topY + height):
            mat_id[cx-half:cx+half, y, cz-half:cz+half] = ID

    fill_block(75, 50, 0, thickness_iodine_2, Iodine2ID)
    fill_block(72, 66, 0, thickness_iodine_5, Iodine5ID)
    fill_block(68, 35, 0, thickness_fe,       FeID)
    fill_block(50, 80, 0, thickness_ta,       TaID)
    fill_block(53, 25, 0, thickness_pt,       PtID)
    fill_block(28, 66, 0, thickness_ba,       BaID)
    fill_block(25, 50, 0, thickness_bone,     BoneID)

    # —— 嵌入 CO₂ 方块（位于 PMMA 板内部）——
    if pmma_thickness >= 10:
        midY = PMMA_OFFSET_Y + pmma_thickness // 2
        fill_block(28, 34, midY-1, thickness_co2_2, CO2ID)
        fill_block(37, 20, midY-2, thickness_co2_5, CO2ID)

    # ---- 写 RAW ----
    raw_fname = save_as_raw(mat_id, pmma_thickness, OUT_DIR, compress_gz=True)

    # ---- 打印 .in 文件模板 ----
    print("\n------ 复制下方片段到 .in 文件 ------")
    print("[SECTION VOXELIZED GEOMETRY FILE v.2025-06-24]")
    print(f"phantom/{raw_fname:<40} # VOXEL FILE (.gz accepted)")
    print("0 0 0                                   # OFFSET [cm]")
    print(f"{VOX_NX} {vox_ny} {VOX_NZ}                          # NUM VOXELS  X Y Z")
    print(f"{VOX_SIZE_CM} {VOX_SIZE_CM} {VOX_SIZE_CM}           # VOXEL SIZE cm")
    print("0 0 0                                   # DISABLE BINARY TREE")
    print("------ 片段结束 ------\n")

# ────────────────────────── 4. 执行入口 ──────────────────────────
if __name__ == "__main__":
    for pmma_t in range(10, 401, 10):         # 可批量生成多厚度
        build_phantom_and_dump(pmma_t)
