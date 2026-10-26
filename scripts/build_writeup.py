"""Build the final GLP1R report with exact sequences, metrics and dedicated structure pages."""
from pathlib import Path
import re,html,json,hashlib,argparse
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,Preformatted,KeepTogether,Image as PDFImage
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import letter
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package',type=Path,default=ROOT/'reports/2026-10-25_glp1r-final20')
parser.add_argument('--output',type=Path)
parser.add_argument('--font-dir',type=Path,default=Path('/usr/share/fonts/truetype/dejavu'))
args=parser.parse_args()
PACKAGE=args.package.resolve();OUT=PACKAGE;OUT.mkdir(parents=True,exist_ok=True)
FONT=args.font_dir
for name,file in [('DejaVu','DejaVuSans.ttf'),('DejaVu-Bold','DejaVuSans-Bold.ttf'),('DejaVu-Oblique','DejaVuSans.ttf'),('DejaVuMono','DejaVuSansMono.ttf')]:pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
pdfmetrics.registerFontFamily('DejaVu',normal='DejaVu',bold='DejaVu-Bold',italic='DejaVu-Oblique',boldItalic='DejaVu-Bold')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyReview',fontName='DejaVu',fontSize=9.2,leading=13.4,spaceAfter=7))
styles.add(ParagraphStyle(name='Candidate',fontName='DejaVu',fontSize=9,leading=11.4,spaceAfter=7))
styles.add(ParagraphStyle(name='TitleReview',fontName='DejaVu-Bold',fontSize=21,leading=27,textColor=colors.HexColor('#14394a'),spaceAfter=15))
styles.add(ParagraphStyle(name='H2Review',fontName='DejaVu-Bold',fontSize=13,leading=17,spaceBefore=12,spaceAfter=9,keepWithNext=True,textColor=colors.HexColor('#14394a')))
styles.add(ParagraphStyle(name='H3Review',fontName='DejaVu-Bold',fontSize=10,leading=13,spaceBefore=8,spaceAfter=6,keepWithNext=True))
styles.add(ParagraphStyle(name='CellReview',fontName='DejaVu',fontSize=7,leading=9.5,spaceAfter=0))
styles.add(ParagraphStyle(name='ReferenceReview',fontName='DejaVu',fontSize=7.8,leading=10.5,spaceAfter=5))
styles.add(ParagraphStyle(name='CodeReview',fontName='DejaVuMono',fontSize=7.5,leading=10,spaceBefore=4,spaceAfter=12))
W=528
source=(PACKAGE/'manuscript.md').read_text()
# Normalize only display punctuation, retaining scientific letters and values.
source=source.replace('→',' -> ').replace('–','-').replace('—','-').replace('‑','-')
def inline(s):
 s=html.escape(s)
 s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
 s=re.sub(r'`([^`]+)`',r'\1',s)
 s=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<link href="\2" color="#1d627d">\1</link>',s)
 return s
lines=source.splitlines();story=[];i=0;candidate=False
while i<len(lines):
 line=lines[i]
 if not line.strip():i+=1;continue
 if line.startswith('!['):
  paths=[]
  while i<len(lines) and (lines[i].startswith('![') or not lines[i].strip()):
   if lines[i].startswith('!['):paths.append(re.search(r'\]\((.+)\)',lines[i]).group(1))
   i+=1
  assert len(paths)==2
  from PIL import Image as PILImage
  ims=[]
  for name in paths:
   path=PACKAGE/name
   with PILImage.open(path) as im:width,height=im.size
   scale=min(250/width,330/height)
   ims.append(PDFImage(str(path),width=width*scale,height=height*scale))
  plate=Table([ims],colWidths=[264,264],hAlign='CENTER')
  plate.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),12)]))
  story.append(plate)
  continue
 if line.startswith('```'):
  block=[];i+=1
  while i<len(lines) and not lines[i].startswith('```'):block.append(lines[i]);i+=1
  story.append(Preformatted('\n'.join(block),styles['CodeReview']));i+=1;continue
 if line.startswith('|'):
  raw=[]
  while i<len(lines) and lines[i].startswith('|'):
   row=[c.strip() for c in lines[i].strip('|').split('|')]
   if not all(re.fullmatch(r'[:\- ]+',c) for c in row):raw.append(row)
   i+=1
  cols=len(raw[0]); widths={8:[25,91,43,25,44,49,68,83],3:[175,200,153]}.get(cols,[W/cols]*cols)
  widths=[v*W/sum(widths) for v in widths]
  cells=[[Paragraph(('<b>'+inline(c)+'</b>') if ri==0 else inline(c),styles['CellReview']) for c in row] for ri,row in enumerate(raw)]
  t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
  t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e5eef2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),0.7,colors.HexColor('#6d8d9a')),('LINEBELOW',(0,1),(-1,-1),0.3,colors.HexColor('#d4dfe3')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
  story.extend([t,Spacer(1,10)]);continue
 if line.startswith('# '):story.append(Paragraph(inline(line[2:]),styles['TitleReview']));i+=1;continue
 if line.startswith('## '):
  heading=line[3:]
  if re.match(r'5\.\d\d ',heading):story.append(PageBreak());candidate=True
  elif heading.startswith('6  '):story.append(PageBreak());candidate=False
  story.append(Paragraph(inline(heading),styles['H2Review']));i+=1;continue
 if line.startswith('### '):story.append(Paragraph(inline(line[4:]),styles['H3Review']));i+=1;continue
 block=[line];i+=1
 while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```')):block.append(lines[i]);i+=1
 story.append(Paragraph(inline(' '.join(block)),styles['ReferenceReview'] if re.match(r'^\[\d+\]',block[0]) else (styles['Candidate'] if candidate else styles['BodyReview'])))
def footer(canvas,document):
 canvas.saveState();canvas.setStrokeColor(colors.HexColor('#ccd9df'));canvas.line(42,38,570,38);canvas.setFont('DejaVu',7)
 canvas.setFillColor(colors.HexColor('#506a76'));canvas.drawString(42,25,'GLP1R selected 20 | Final computational report | 25 October 2026')
 canvas.drawRightString(570,25,str(document.page));canvas.restoreState()
pdf=args.output or OUT/'GLP1R_Week3_Final20_Final_Writeup.pdf'
SimpleDocTemplate(str(pdf),pagesize=letter,leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=49,title='Human GLP1R designs: the selected 20 - final computational report',author='',pageCompression=1).build(story,onFirstPage=footer,onLaterPages=footer)
print(pdf)
