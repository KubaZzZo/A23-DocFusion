# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 - DocFusion"""

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

a = Analysis(
    ['main.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # FastAPI / Uvicorn
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # SQLAlchemy
        'sqlalchemy.dialects.sqlite',
        # 文档处理
        'docx',
        'openpyxl',
        'markdown',
        'fitz',
        # 网络
        'httpx',
        'httpx._transports',
        'httpx._transports.default',
        'openai',
        # 爬虫
        'bs4',
        'lxml',
        'lxml.etree',
        # Pydantic
        'pydantic',
        'pydantic.deprecated',
        'pydantic.deprecated.decorator',
        # 其他
        'aiofiles',
        'multipart',
        'email_validator',
        # 图表
        'matplotlib',
        'matplotlib.backends.backend_qtagg',
        # OCR
        'pytesseract',
        'PIL',
        'PIL.Image',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DocFusion',
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
    icon=None,  # 可替换为 icon='assets/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DocFusion',
)
