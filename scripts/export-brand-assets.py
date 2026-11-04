"""Export generated icon artwork to native PNG and multi-resolution Windows ICO.

Run from a source checkout using the desktop Python environment. The master
artwork is retained unchanged; Qt only resamples it for platform icon sizes.
"""
import struct
from pathlib import Path
from PySide6.QtCore import QByteArray,QBuffer,QIODevice,Qt
from PySide6.QtGui import QImage

root=Path(__file__).resolve().parent.parent
source=QImage(str(root/'assets/dayframe-icon-master.png'))
if source.isNull():raise SystemExit('Missing DayFrame icon master.')
image=source.scaled(512,512,Qt.KeepAspectRatio,Qt.SmoothTransformation)
for path in (root/'assets/DayFrame.png',root/'dayframe/resources/dayframe-icon.png'):
    if not image.save(str(path)):raise SystemExit(f'Cannot write {path}')
sizes=(16,20,24,32,40,48,64,96,128,256)
chunks=[]
for size in sizes:
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly)
    if not source.scaled(size,size,Qt.KeepAspectRatio,Qt.SmoothTransformation).save(buffer,'PNG'):
        raise SystemExit('Cannot encode icon image.')
    chunks.append(bytes(data))
offset=6+16*len(sizes);entries=[]
for size,chunk in zip(sizes,chunks):
    entries.append(struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(chunk),offset))
    offset+=len(chunk)
(root/'assets/DayFrame.ico').write_bytes(struct.pack('<HHH',0,1,len(sizes))+b''.join(entries)+b''.join(chunks))
print('Exported DayFrame.png, bundled resource and ICO sizes:',sizes)
