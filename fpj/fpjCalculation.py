import os
from pathlib import Path
import numpy as np
import pandas as pd
from crip.io import imreadRaw, imwriteRaw
from scipy.interpolate import interp1d
import cv2
from datetime import datetime

now = datetime.now()
month = now.month
day = now.day

# pmma厚度，关联co2！
pmma_thickness = 50

# debug 用
out_dir_test = Path("./test_raw")
out_dir_test.mkdir(exist_ok=True, parents=True)
'''
======================================
Part1 部分需要更改的配置
======================================
'''
dtype1      = np.float32          # 输出 dtype
RAW_SHAPE   = (300, 300)          # 每张 raw 的宽高（H, W）
ENERGY_GRID = np.arange(8, 101)  # keV，8–100 共 93 点,蒙卡最低要求8kev
MM2CM       = 0.1                 # 毫米 → 厘米
ENERGY_RANGE = 100
spectrum_file = 'spectrum100_Copper0.1mm.txt'
SCAN_SUFFIX = "530"
MATERIALS = {
    # 名称  (   密度 g/cm³ , μ(E)： Excel 路径 , 长度： raw 路径 )
    "pmma": ( 1.19, r"./attenuation_coefficient/pmma_u.xlsx", fr"./sgm/sgm_pmma_{pmma_thickness}mm_{SCAN_SUFFIX}.raw"),
    "fe"  : ( 7.87, r"./attenuation_coefficient/fe_u.xlsx"  , fr"./sgm/sgm_fe_1mm_{SCAN_SUFFIX}.raw"),
    "iodine2":(4.93, r"./attenuation_coefficient/iodine_u.xlsx", fr"./sgm/sgm_iodine_2mm_{SCAN_SUFFIX}.raw"),
    "iodine5":(4.93, r"./attenuation_coefficient/iodine_u.xlsx", fr"./sgm/sgm_iodine_5mm_{SCAN_SUFFIX}.raw"),
    "ta"  : (16.69, r"./attenuation_coefficient/ta_u.xlsx"  , fr"./sgm/sgm_ta_1mm_{SCAN_SUFFIX}.raw"),
    "pt"  : (21.45, r"./attenuation_coefficient/pt_u.xlsx"  , fr"./sgm/sgm_pt_1mm_{SCAN_SUFFIX}.raw"),
    "ba"  : ( 3.62, r"./attenuation_coefficient/ba_u.xlsx"  , fr"./sgm/sgm_ba_50mm_{SCAN_SUFFIX}.raw"),
    "bone": ( 1.85, r"./attenuation_coefficient/bone_u.xlsx", fr"./sgm/sgm_bone_40mm_{SCAN_SUFFIX}.raw"),
    "co2_2" : ( 8.90, r"./attenuation_coefficient/co2_u.xlsx" , fr"./sgm/sgm_co2_2mm_P{pmma_thickness}mm_{SCAN_SUFFIX}.raw"),
    "co2_5" : ( 8.90, r"./attenuation_coefficient/co2_u.xlsx" , fr"./sgm/sgm_co2_5mm_P{pmma_thickness}mm_{SCAN_SUFFIX}.raw"),
}



'''
======================================
Part2 部分需要更改的配置
======================================
'''
scatter_folder = r"./mcgpu/scat_raw"                  # mcgpu 图像输出目录
scatter_prefix = f"P{pmma_thickness}_muti_100kv_repeat_1_521_1"    # mcgpu模拟图像
AIR_PATH     = fr"./mcgpu/scat_raw/air/P{pmma_thickness}_muti_100kv_repeat_1_Air_521_1.raw"                   # 空气图像
round_num = 1
file_remarks = f'by_QM_{month}{day}_{round_num}'



#  1. 载入能谱并插值到 1 keV
spec_e_raw, spec_w_raw = np.loadtxt(f"./spectrum/{spectrum_file}", unpack=True)
interp = interp1d(spec_e_raw, spec_w_raw, kind='linear', bounds_error=False, fill_value=0)
spec_w = interp(ENERGY_GRID * 1_000)          # 把 keV→eV 再插值
spec_e = ENERGY_GRID                          # keV       (20…100)
spec_w /= spec_w.sum()                        # 若需要归一化，可取消注释


# 2. 为每种材料读取 μ(E) → 93 ×1 数组，读取厚度 raw → H×W
mu_dict   = {}   # key: material → (93,)
thick_dict = {}  # key: material → (H,W)

# 直接获得每个材料所对应的图像的密度、插值获得的μ/ρ(E)，和raw中记录的长度
for name, (rho, mu_xlsx, raw_path) in MATERIALS.items():
    # 2-1 μ(E) 插值到 ENERGY_GRID
    df = pd.read_excel(mu_xlsx)
    # mu_xlsx → 该材料的 μ/ρ(E) Excel 文件
    mu_interp = np.exp(np.interp(np.log(ENERGY_GRID),
                                 np.log(df['Energy(kev)'].values),
                                 np.log(df['u'].values)))

    # mu_dict 是全局 dict，key = 材料名，value = (93,) ndarray
    mu_dict[name] = mu_interp  # 长度 93

    # 2-2 厚度 map（mm）
    thick = imreadRaw(raw_path, *RAW_SHAPE, nSlice=1).astype(np.float32)
    # 给的正投影图不是三维的，下面关于三维的判断没必要
    # if thick.ndim == 3:
    #     thick = np.squeeze(thick, axis=0)  # 1×H×W → H×W
    thick_dict[name] = thick  # H×W

print("Loaded materials:", list(MATERIALS))

TARGET_FACTOR = 0.97        # mgfpj primary ×0.97 → mcgpu
BONE_THICK_REF = 3.0        # ← 测 0.97 时那张纯骨像素的厚度(cm)
ln_factor = -np.log(TARGET_FACTOR)          # >0
delta_mu = ln_factor / BONE_THICK_REF       # 标量 (cm-1)

# delta_mu_E = delta_mu * energy_weight[k] ...

# 3. 计算 lower 与 higher

lower  = np.sum(spec_w * spec_e)             # 入射总能量 (标量),用numpy来加速积分过程
higher = np.zeros(RAW_SHAPE, dtype=np.float32)
for k, E_keV in enumerate(ENERGY_GRID):
    mu_t = np.zeros(RAW_SHAPE, dtype=np.float32)

    for name, (rho, _, _) in MATERIALS.items():
        mu = mu_dict[name][k]            # (μ/ρ)_E
        thick = thick_dict[name]         # mm
        if name == "bone":
            mu += delta_mu / rho         # ← 只给骨加 Δμ/ρ
        mu_t += mu * rho * thick * MM2CM

    # 3-2 能量加权累加
    higher += spec_w[k] * spec_e[k] * np.exp(-mu_t)


# 4. 取透过率、Post-log，并写 raw
primary  = higher / lower

postlog  = -np.log(primary + 1e-6)  # 对primary做postlog,已方便对比
# ── 4. 输出 ────────────────────────────────────────────────────
out_dir = Path("./proj_with_scatter")
out_dir.mkdir(exist_ok=True, parents=True)

imwriteRaw(postlog, out_dir/f"P{pmma_thickness}_primary_to_postlog_muti_{ENERGY_RANGE}kv_by_QM_1.raw", dtype=dtype1)
print("primary_to_postlog 已写入", out_dir)