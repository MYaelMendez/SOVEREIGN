import importlib.util
from pathlib import Path
from PIL import Image, ImageDraw
s=importlib.util.spec_from_file_location('n','C:/æ/mp4-factory/neon_asimov.py')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
ctx=m.build()
ids=[0,16,32,48,64,80,96,111]
sheet=Image.new('RGB',(4*288,2*512),(0,0,0))
for i,n in enumerate(ids):
 im,_=m.frame(n,ctx); im.thumbnail((288,512))
 sheet.paste(im,((i%4)*288,(i//4)*512))
 ImageDraw.Draw(sheet).text(((i%4)*288+4,(i//4)*512+4),'frame '+str(n),fill=(255,255,0))
p=Path('C:/æ/mp4-factory/neon-asimov-fixed-camera-board.png');sheet.save(p)
print(p,p.stat().st_size)
