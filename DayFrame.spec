# Build the native desktop with: python -m PyInstaller DayFrame.spec --noconfirm
from PyInstaller.utils.hooks import collect_data_files,copy_metadata
from pathlib import Path
import sys
import os
if sys.platform=="win32":
    # Exclude unrelated developer tools from DLL discovery. Qt uses Windows ICU;
    # a Poppler/Conda ICU with the same filename exports incompatible symbols.
    system=Path(os.environ["WINDIR"])
    os.environ["PATH"]=os.pathsep.join(str(p) for p in (Path(sys.executable).parent,Path(sys.base_prefix),system/"System32",system))
datas=collect_data_files("qtawesome")+collect_data_files("tzdata")
for distribution in ("PySide6-Essentials","shiboken6","QtAwesome","QtPy","keyring","cryptography","tzdata"):
    datas+=copy_metadata(distribution)
python_license=Path(sys.base_prefix)/"LICENSE.txt"
if python_license.exists():datas.append((str(python_license),"licenses/python"))
datas.append(("docs/operations/THIRD_PARTY.md","licenses"))
datas += [(str(p),"dayframe/resources") for p in Path("dayframe/resources").iterdir() if p.suffix in (".svg", ".png")]
datas += [("dayframe/data/schema.sql","dayframe/data"),("dayframe/data/schema_definitions.json","dayframe/data")]
a=Analysis(["app.py"],pathex=[],binaries=[],datas=datas,
           hiddenimports=["keyring.backends.Windows","keyring.backends.SecretService","PySide6.QtSvg"],
           excludes=["PySide6.QtWebEngineCore","PySide6.QtWebEngineWidgets","PySide6.QtQml","PySide6.QtQuick"],
           noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name="DayFrame",debug=False,
        bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon="assets/DayFrame.ico")
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name="DayFrame")
