#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from PIL import Image
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
import subprocess

# 定义项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 定义输入SVG文件路径
SVG_FILE = os.path.join(PROJECT_ROOT, 'logo.svg')

# 定义输出图标路径
ICO_FILE = os.path.join(PROJECT_ROOT, 'logo.ico')
ICNS_FILE = os.path.join(PROJECT_ROOT, 'logo.icns')
PNG_FILE = os.path.join(PROJECT_ROOT, 'logo.png')

# 转换SVG到PNG
def svg_to_png(svg_path, png_path, size=(256, 256)):
    print('将SVG转换为PNG...')
    drawing = svg2rlg(svg_path)
    renderPM.drawToFile(drawing, png_path, fmt='PNG', dpi=300, bg=0xFFFFFF, fg=0x000000)
    print(f'PNG文件已创建: {png_path}')

# 转换PNG到ICO
def png_to_ico(png_path, ico_path):
    print('将PNG转换为ICO...')
    img = Image.open(png_path)
    # 创建不同尺寸的图标
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f'ICO文件已创建: {ico_path}')

# 转换PNG到ICNS (macOS)
def png_to_icns(png_path, icns_path):
    print('将PNG转换为ICNS...')
    # 使用iconutil命令行工具 (macOS自带)
    try:
        # 创建临时目录
        temp_dir = os.path.join(PROJECT_ROOT, 'temp.iconset')
        os.makedirs(temp_dir, exist_ok=True)

        # 创建不同尺寸的图标
        sizes = [16, 32, 64, 128, 256, 512, 1024]
        for size in sizes:
            img = Image.open(png_path)
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            img.save(os.path.join(temp_dir, f'icon_{size}x{size}.png'))
            # 创建@2x版本
            if size <= 512:
                img_2x = img.resize((size*2, size*2), Image.Resampling.LANCZOS)
                img_2x.save(os.path.join(temp_dir, f'icon_{size}x{size}@2x.png'))

        # 使用iconutil创建icns文件
        subprocess.run(['iconutil', '-c', 'icns', temp_dir, '-o', icns_path], check=True)
        print(f'ICNS文件已创建: {icns_path}')

        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir)
    except Exception as e:
        print(f'转换ICNS失败: {e}')

# 主函数
def main():
    # 首先转换SVG到PNG
    svg_to_png(SVG_FILE, PNG_FILE)

    # 转换PNG到ICO
    png_to_ico(PNG_FILE, ICO_FILE)

    # 转换PNG到ICNS (仅在macOS上执行)
    import platform
    if platform.system() == 'Darwin':
        png_to_icns(PNG_FILE, ICNS_FILE)
    else:
        print('跳过ICNS转换，仅在macOS系统上支持')

if __name__ == '__main__':
    main()