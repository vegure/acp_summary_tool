#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

# 确保中文显示正常
import matplotlib
matplotlib.use('Agg')

# 定义项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 定义应用程序名称和主文件
APP_NAME = 'ACP总结报告工具'
MAIN_SCRIPT = 'gui_app.py'

# 定义图标路径
ICON_PATH = os.path.join(PROJECT_ROOT, 'logo.ico')  # Windows图标
ICON_PATH_MAC = os.path.join(PROJECT_ROOT, 'logo.icns')  # macOS图标

# 清理之前的构建文件
def clean_build():
    print('清理之前的构建文件...')
    build_dir = os.path.join(PROJECT_ROOT, 'build')
    dist_dir = os.path.join(PROJECT_ROOT, 'dist')
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    print('清理完成')

# 为不同平台创建spec文件
def create_spec_file():
    print('创建spec文件...')
    
    # 构建spec文件内容
    spec_content = []
    spec_content.append('# -*- mode: python ; coding: utf-8 -*-\n')
    spec_content.append('\n')
    spec_content.append('block_cipher = None\n')
    spec_content.append('\n')
    # 添加fastmcp元数据文件
    spec_content.append('# 添加fastmcp元数据文件\n')
    spec_content.append('fastmcp_metadata = \'/Users/yulei/miniconda3/envs/llm_app/lib/python3.11/site-packages/fastmcp-2.10.6.dist-info\'\n')
    spec_content.append('added_files = [\n')
    spec_content.append('    (\'config.json\', \'.\'),\n')
    spec_content.append('    (\'logo.ico\', \'.\'),\n')
    spec_content.append('    (\'logo.icns\', \'.\'),\n')
    spec_content.append('    (fastmcp_metadata, \'fastmcp-2.10.6.dist-info\'),\n')
    spec_content.append(']\n')
    spec_content.append('\n')
    spec_content.append('# 包含其他Python文件\n')
    spec_content.append('hidden_imports = [\n')
    spec_content.append('    \'main_func\',\n')
    spec_content.append('    \'image_processor\',\n')
    spec_content.append('    \'llm_client\',\n')
    spec_content.append('    \'fastmcp\',\n')
    spec_content.append(']\n')
    spec_content.append('\n')
    spec_content.append('\n')
    spec_content.append('a = Analysis([\'{0}\'],\n'.format(MAIN_SCRIPT))
    spec_content.append('             pathex=[\'{0}\'],\n'.format(PROJECT_ROOT))
    spec_content.append('             binaries=[],\n')
    spec_content.append('             datas=added_files,\n')
    spec_content.append('             hiddenimports=hidden_imports,\n')
    spec_content.append('             hookspath=[],\n')
    spec_content.append('             runtime_hooks=[],\n')
    spec_content.append('             excludes=[],\n')
    spec_content.append('             win_no_prefer_redirects=False,\n')
    spec_content.append('             win_private_assemblies=False,\n')
    spec_content.append('             cipher=block_cipher,\n')
    spec_content.append('             noarchive=False)\n')
    spec_content.append('\n')
    spec_content.append('pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)\n')
    spec_content.append('\n')
    
    # 添加平台特定配置
    if platform.system() == 'Darwin':
        spec_content.append('# macOS应用包配置\n')
        spec_content.append('exe = EXE(pyz,\n')
        spec_content.append('          a.scripts,\n')
        spec_content.append('          a.binaries,\n')
        spec_content.append('          a.zipfiles,\n')
        spec_content.append('          a.datas,\n')
        spec_content.append('          [],\n')
        spec_content.append('          name=\'{0}\',\n'.format(APP_NAME))
        spec_content.append('          debug=False,\n')
        spec_content.append('          bootloader_ignore_signals=False,\n')
        spec_content.append('          strip=False,\n')
        spec_content.append('          upx=True,\n')
        spec_content.append('          upx_exclude=[],\n')
        spec_content.append('          runtime_tmpdir=None,\n')
        spec_content.append('          icon=\'{0}\', bundle=True)\n'.format(ICON_PATH_MAC))
        spec_content.append('\n')
        spec_content.append('# 创建macOS应用包\n')
        spec_content.append('app = BUNDLE(exe,\n')
        spec_content.append('             name=\'{0}.app\',\n'.format(APP_NAME))
        spec_content.append('             icon=\'{0}\',\n'.format(ICON_PATH_MAC))
        spec_content.append('             bundle_identifier=None)\n')
    else:
        spec_content.append('# Windows可执行文件配置\n')
        spec_content.append('exe = EXE(pyz,\n')
        spec_content.append('          a.scripts,\n')
        spec_content.append('          a.binaries,\n')
        spec_content.append('          a.zipfiles,\n')
        spec_content.append('          a.datas,\n')
        spec_content.append('          [],\n')
        spec_content.append('          name=\'{0}\',\n'.format(APP_NAME))
        spec_content.append('          debug=False,\n')
        spec_content.append('          bootloader_ignore_signals=False,\n')
        spec_content.append('          strip=False,\n')
        spec_content.append('          upx=True,\n')
        spec_content.append('          upx_exclude=[],\n')
        spec_content.append('          runtime_tmpdir=None,\n')
        spec_content.append('          icon=\'{0}\'})\n'.format(ICON_PATH))
    
    # 连接所有内容
    spec_content = ''.join(spec_content)
    

    spec_file = os.path.join(PROJECT_ROOT, f'{APP_NAME}.spec')
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print(f'spec文件已创建: {spec_file}')
    return spec_file

# 构建可执行文件
def build_executable():
    print(f'开始构建{APP_NAME}...')
    clean_build()
    spec_file = create_spec_file()

    # 构建命令
    cmd = [
        'pyinstaller',
        spec_file,
        '--noconfirm',
    ]

    # 窗口模式参数已在spec文件中定义，无需在此添加
    
    print(f'执行命令: {cmd}')
    try:
        subprocess.run(cmd, check=True)
        print(f'构建成功! 可执行文件位于: {os.path.join(PROJECT_ROOT, "dist")}')
    except subprocess.CalledProcessError as e:
        print(f'构建失败: {e}')
        sys.exit(1)

# 主函数
if __name__ == '__main__':
    build_executable()