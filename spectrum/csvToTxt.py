import pandas as pd

def convert_csv_to_txt(input_csv, output_txt):
    """
    将能谱文件从 CSV 格式转换为指定的 TXT 格式，并将能量单位从 keV 转换为 eV。

    参数：
        input_csv (str): 输入的 CSV 文件路径。
        output_txt (str): 输出的 TXT 文件路径。
    """
    # 读取 CSV 文件，注意分隔符是 `;`
    data = pd.read_csv(input_csv, sep=';', header=None, names=['Energy', 'Intensity'])

    # 将能量单位从 keV 转换为 eV
    data['Energy'] = data['Energy'] * 1000

    # 保存为 TXT 格式
    with open(output_txt, "w") as f:
        for _, row in data.iterrows():
            f.write(f"{int(row['Energy'])}  {row['Intensity']:.6e}\n")

    print(f"转换完成，文件已保存为: {output_txt}")

# 示例用法
if __name__ == "__main__":
    input_csv_path = "./spec/spectrum100_None.csv"  # 替换为你的 CSV 文件路径
    output_txt_path = "./spec/spectrum100_None.txt"  # 替换为输出的 TXT 文件路径

    convert_csv_to_txt(input_csv_path, output_txt_path)
