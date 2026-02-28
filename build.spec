# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 - 翻译校验工具"""

import os
import certifi
import customtkinter

# CustomTkinter 资源路径
ctk_path = os.path.dirname(customtkinter.__file__)
# SSL 证书路径（确保打包后 HTTPS 请求正常工作）
certifi_ca_bundle = certifi.where()

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # config.json 不打包，首次运行时由程序自动在 exe 目录生成
        (ctk_path, 'customtkinter/'),
        # SSL 证书，确保 requests 库打包后 HTTPS 正常工作
        (certifi_ca_bundle, 'certifi/'),
    ],
    hiddenimports=[
        'customtkinter',
        'darkdetect',
        'openpyxl',
        'et_xmlfile',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TranslationChecker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TranslationChecker',
)
