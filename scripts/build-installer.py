"""Compile a per-user installer; uninstall removes only manifest-listed app files."""
import argparse
import os
import shutil
import subprocess
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("makensis",help="Path to the NSIS compiler")
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    bundle=root/"dist"/"DayFrame"
    if not (bundle/"DayFrame.exe").is_file():
        raise SystemExit("Build the PyInstaller bundle first.")
    compiler=Path(args.makensis).resolve()
    nsis_root=next((p for p in (compiler.parent,compiler.parent.parent) if (p/"COPYING").is_file()),None)
    if nsis_root is None:
        raise SystemExit("The NSIS compiler must include its COPYING notice.")
    notices=bundle/"_internal"/"licenses"/"nsis";notices.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(nsis_root/"COPYING",notices/"COPYING")
    files=sorted(p for p in bundle.rglob("*") if p.is_file())
    dirs=sorted((p for p in bundle.rglob("*") if p.is_dir()),key=lambda p:len(p.parts),reverse=True)
    commands=['Delete "$INSTDIR\\'+str(p.relative_to(bundle)).replace("/","\\")+'"' for p in files]
    commands+=['RMDir "$INSTDIR\\'+str(p.relative_to(bundle)).replace("/","\\")+'"' for p in dirs]
    (root/"scripts"/"uninstall-files.nsh").write_text("\n".join(commands)+"\n",encoding="utf-8")
    # Portable compilers need the resource root even when makensis is outside Bin/.
    env={**os.environ,"NSISDIR":str(nsis_root)}
    subprocess.run([str(compiler),"/V2",str(root/"scripts"/"installer.nsi")],cwd=root,env=env,check=True)

if __name__=="__main__":main()
