"""Enrich current KBO snapshot with reliable player positions and profile images.
Uses KBO defense records for exact field positions, falling back to player profile position.
"""
from html.parser import HTMLParser
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from pathlib import Path
import json, re, time

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'dist'/'kbo-data.json'
DEFENSE_URL='https://www.koreabaseball.com/Record/Player/Defense/Basic.aspx'
DETAIL='https://www.koreabaseball.com/Record/Player/HitterDetail/Basic.aspx?playerId='
UA={'User-Agent':'HitPick/1.0 (public KBO statistics reader)'}

class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.fields={}; self.select=None; self.table=False; self.cell=None; self.row=[]; self.rows=[]; self.anchor=None; self.pages={}; self.player_ids={}; self.row_player_id=None
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='input' and a.get('type')=='hidden' and a.get('name'): self.fields[a['name']]=a.get('value','')
        if tag=='select': self.select=a.get('name'); self.fields.setdefault(self.select,'')
        if tag=='option' and self.select and 'selected' in a: self.fields[self.select]=a.get('value','')
        if tag=='table' and 'tData01' in a.get('class',''): self.table=True
        if self.table and tag=='tr': self.row=[]; self.row_player_id=None
        if self.table and tag=='a':
            m=re.search(r'playerId=(\d+)',a.get('href',''))
            if m: self.row_player_id=m.group(1)
        if self.table and tag in ('td','th'): self.cell=[]
        if tag=='a' and 'ucPager_btnNo' in a.get('id',''): self.anchor=[a.get('href',''),[]]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
        if self.anchor is not None:self.anchor[1].append(data)
    def handle_endtag(self,tag):
        if tag=='select':self.select=None
        if tag in ('td','th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip());self.cell=None
        if tag=='tr' and self.table and self.row:
            self.rows.append(self.row)
            if self.row_player_id:self.player_ids[len(self.rows)-1]=self.row_player_id
        if tag=='table':self.table=False
        if tag=='a' and self.anchor is not None:
            href,parts=self.anchor;label=''.join(parts).strip();m=re.search(r"__doPostBack\('([^']+)'",href)
            if label.isdigit() and m:self.pages[int(label)]=m.group(1)
            self.anchor=None

def fetch_pages():
    opener=build_opener(HTTPCookieProcessor())
    def fetch(fields=None):
        req=Request(DEFENSE_URL,data=urlencode(fields).encode() if fields else None,headers={**UA,'Referer':DEFENSE_URL})
        with opener.open(req,timeout=45) as r:return Page(r.read().decode('utf-8-sig'))
    first=fetch(); pages=[first]; visited={1}; current=first; pending=first.pages.copy()
    while set(pending)-visited:
        n=min(set(pending)-visited); fields=current.fields.copy(); fields.update(__EVENTTARGET=pending[n],__EVENTARGUMENT=''); time.sleep(.5)
        current=fetch(fields); pages.append(current); visited.add(n); pending.update(current.pages)
    return pages

def defense_maps():
    exact={'포수','1루수','2루수','3루수','유격수','좌익수','중견수','우익수'}
    by_id={};by_name={}
    for page in fetch_pages():
        if not page.rows or page.rows[0][:4]!=['순위','선수명','팀명','POS']: continue
        for idx,r in enumerate(page.rows[1:],1):
            if len(r)<4 or r[3] not in exact: continue
            name,team,pos=r[1],r[2],r[3]; pid=page.player_ids.get(idx)
            by_name[(name,team)]=pos
            if pid:by_id[pid]=pos
    return by_id,by_name

def profile(player):
    url=DETAIL+player['player_id'];time.sleep(.25)
    req=Request(url,headers=UA)
    with build_opener().open(req,timeout=45) as r:html=r.read().decode('utf-8-sig')
    pos=None
    m=re.search(r'포지션:\s*</[^>]+>?\s*([^<(]+)',html)
    if not m:m=re.search(r'포지션:\s*([^<(<]+)',re.sub(r'<[^>]+>',' ',html))
    if m:pos=m.group(1).strip()
    image=None
    patterns=[r'<img[^>]+src="([^"]+)"[^>]+alt="'+re.escape(player['name'])+r'"',r'<img[^>]+alt="'+re.escape(player['name'])+r'"[^>]+src="([^"]+)"']
    for pat in patterns:
        m=re.search(pat,html,re.I)
        if m:image=m.group(1);break
    if image and image.startswith('//'):image='https:'+image
    return pos,image

def main():
    data=json.loads(DATA.read_text())
    by_id,by_name=defense_maps(); exact_count=0; photo_count=0
    for p in data['players']:
        exact=by_id.get(p['player_id']) or by_name.get((p['name'],p['team']))
        broad,image=profile(p)
        p['position']=exact or broad
        p['position_exact']=bool(exact)
        if exact:exact_count+=1
        if image:p['profile_image']=image;photo_count+=1
    data['position_source_url']=DEFENSE_URL
    data['profile_source']='KBO player detail pages'
    temp=DATA.with_suffix('.enriched.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2));temp.replace(DATA)
    print(json.dumps({'players':len(data['players']),'exact_positions':exact_count,'profile_images':photo_count},ensure_ascii=False))

if __name__=='__main__':main()
