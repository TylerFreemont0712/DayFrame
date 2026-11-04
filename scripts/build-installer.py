"""Compile a per-user installer; uninstall removes only manifest-listed app files."""
import argparse
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
    files=sorted(p for p in bundle.rglob("*") if p.is_file())
    dirs=sorted((p for p in bundle.rglob("*") if p.is_dir()),key=lambda p:len(p.parts),reverse=True)
    commands=['Delete "$INSTDIR\\'+str(p.relative_to(bundle)).replace("/","\\")+'"' for p in files]
    commands+=['RMDir "$INSTDIR\\'+str(p.relative_to(bundle)).replace("/","\\")+'"' for p in dirs]
    (root/"scripts"/"uninstall-files.nsh").write_text("\n".join(commands)+"\n",encoding="utf-8")
    subprocess.run([args.makensis,"/V2",str(root/"scripts"/"installer.nsi")],cwd=root,check=True)

if __name__=="__main__":main()
