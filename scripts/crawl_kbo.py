"""Refresh KBO's default regular-season batting leaderboard, atomically.
No third-party dependencies. Fail closed: never replace a valid snapshot on errors.
"""
from html.parser import HTMLParser
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import json, re, time, sys
from concurrent.futures import ThreadPoolExecutor
from kbo_schedule import fetch_schedule

URL='https://www.koreabaseball.com/Record/Player/HitterBasic/Basic1.aspx'
ROOT=Path(__file__).resolve().parents[1]
class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.fields={}; self.select=None; self.option=None; self.table=False; self.cell=None; self.row=[]; self.rows=[]; self.anchor=None; self.pages={}; self.season=None; self.player_ids={}; self.row_player_id=None
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='input' and a.get('type')=='hidden' and a.get('name'): self.fields[a['name']]=a.get('value','')
        if tag=='select': self.select=a.get('name'); self.fields.setdefault(self.select,'')
        if tag=='option' and self.select and 'selected' in a:
            self.fields[self.select]=a.get('value','')
            if self.select.endswith('$ddlSeason$ddlSeason'): self.season=int(a['value'])
        if tag=='table' and ('tData01' in a.get('class','') or '최근 10경기' in a.get('summary','') or '상대팀별 기록' in a.get('summary','')): self.table=True
        if self.table and tag=='tr': self.row=[]; self.row_player_id=None
        if self.table and tag=='a':
            match=re.search(r'playerId=(\d+)',a.get('href',''))
            if match: self.row_player_id=match[1]
        if self.table and tag in ('td','th'): self.cell=[]
        if tag=='a' and 'ucPager_btnNo' in a.get('id',''): self.anchor=[a.get('href',''),[]]
    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)
        if self.anchor is not None: self.anchor[1].append(data)
    def handle_endtag(self, tag):
        if tag=='select': self.select=None
        if tag in ('td','th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip()); self.cell=None
        if tag=='tr' and self.table and self.row:
            self.rows.append(self.row)
            if self.row_player_id: self.player_ids[self.row[0]]=self.row_player_id
        if tag=='table': self.table=False
        if tag=='a' and self.anchor is not None:
            href,parts=self.anchor; label=''.join(parts).strip(); match=re.search(r"__doPostBack\('([^']+)'",href)
            if label.isdigit() and match: self.pages[int(label)]=match[1]
            self.anchor=None

def parse_players(page):
    assert page.rows and page.rows[0][:4]==['순위','선수명','팀명','AVG'], 'KBO table layout changed'
    assert page.rows[0][4:9]==['G','PA','AB','R','H'], 'Unexpected statistics columns'
    out=[]
    for r in page.rows[1:]:
        assert len(r)==16, 'Unexpected row width'
        rank,name,team=int(r[0]),r[1],r[2]
        games,pa,ab,h=int(r[4]),int(r[5]),int(r[6]),int(r[8])
        assert games>0 and 0<=h<=ab<=pa and ab>0
        assert abs(float(r[3])-h/ab)<=.00051, 'AVG does not agree with H/AB'
        out.append(dict(player_id=page.player_ids[str(rank)],rank=rank,name=name,team=team,games=games,plate_appearances=pa,at_bats=ab,hits=h,average=float(r[3])))
    assert out, 'Empty leaderboard'
    return out

def parse_recent(html, player, season):
    assert re.search(r'<h6>\s*'+str(season)+r'\s*성적\s*</h6>',html), 'Unexpected player season'
    page=Page(html)
    assert page.rows and page.rows[0][:8]==['일자','구분','상대','AVG','PA','AB','R','H'], 'Recent table layout changed'
    rows=[r for r in page.rows if re.fullmatch(r'\d{2}\.\d{2}',r[0])]
    expected=min(10,player['games'])
    assert len(rows)==expected, f"Expected {expected} recent games, got {len(rows)}"
    games=[]
    for r in rows:
        assert len(r)==18, 'Recent game column count changed'
        ab,h,pa=int(r[5]),int(r[7]),int(r[4])
        assert 0<=h<=ab<=pa
        if ab: assert abs(float(r[3])-h/ab)<=.00051, 'Game AVG mismatch'
        date=f"{season}-{r[0].replace('.','-')}"
        datetime.strptime(date,'%Y-%m-%d')
        games.append(dict(date=date,opponent=r[2],venue=r[1],at_bats=ab,hits=h))
    # Preserve distinct doubleheader appearances even when their dates match.
    ab=sum(g['at_bats'] for g in games); h=sum(g['hits'] for g in games)
    totals=[r for r in page.rows if r[0]=='합계']
    assert len(totals)==1 and len(totals[0])==16, 'Recent total missing'
    total=totals[0]
    assert int(total[3])==ab and int(total[5])==h, 'Recent totals disagree with game rows'
    if ab: assert abs(float(total[1])-h/ab)<=.00051, 'Recent AVG mismatch'
    assert ab<=player['at_bats'] and h<=player['hits'], 'Recent exceeds season'
    return dict(games=len(games),at_bats=ab,hits=h,average=h/ab if ab else None,
                start_date=min(g['date'] for g in games),end_date=max(g['date'] for g in games),game_log=games)

def fetch_recent(player, season):
    url='https://www.koreabaseball.com/Record/Player/HitterDetail/Basic.aspx?playerId='+player['player_id']
    time.sleep(1)
    req=Request(url,headers={'User-Agent':'HitPick/1.0 (daily public KBO statistics reader)'})
    with build_opener().open(req,timeout=45) as response:
        assert response.status==200
        html=response.read().decode('utf-8-sig')
    recent=parse_recent(html,player,season); recent['source_url']=url
    print(f"Recent 10: {player['name']} {recent['at_bats']} AB / {recent['hits']} H",flush=True)
    return recent

TEAMS={'KIA','KT','LG','NC','SSG','두산','롯데','삼성','키움','한화'}

def parse_opponents(html, player, season):
    assert re.search(r'<h6>\s*'+str(season)+r'\s*경기별 성적\s*</h6>',html), 'Opponent season mismatch'
    rows=Page(html).rows
    assert rows and rows[0][:7]==['구분','G','AVG','PA','AB','R','H'], 'Opponent table header changed'
    result={}
    for r in rows[1:]:
        assert len(r)==17 and r[0] in TEAMS and r[0] not in result, 'Opponent row changed'
        games,pa,ab,h=int(r[1]),int(r[3]),int(r[4]),int(r[6])
        assert 0<=h<=ab<=pa and games>=0
        if ab: assert abs(float(r[2])-h/ab)<=.00051, 'Opponent AVG mismatch'
        result[r[0]]=dict(games=games,at_bats=ab,hits=h,average=h/ab if ab else None)
    assert result, 'Opponent rows missing'
    assert sum(r['at_bats'] for r in result.values())==player['at_bats'], 'Opponent AB sum differs from season'
    assert sum(r['hits'] for r in result.values())==player['hits'], 'Opponent H sum differs from season'
    return result

def fetch_opponents(player, season):
    url='https://www.koreabaseball.com/Record/Player/HitterDetail/Game.aspx?playerId='+player['player_id']
    time.sleep(1)
    req=Request(url,headers={'User-Agent':'HitPick/1.0 (daily public KBO statistics reader)'})
    with build_opener().open(req,timeout=45) as response:
        assert response.status==200
        result=parse_opponents(response.read().decode('utf-8-sig'),player,season)
    print('Opponent splits: '+player['name'],flush=True)
    return dict(teams=result,source_url=url,fetched_at=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'))

def main():
    opener=build_opener(HTTPCookieProcessor())
    def fetch(fields=None):
        req=Request(URL,data=urlencode(fields).encode() if fields is not None else None,headers={'User-Agent':'HitPick/1.0 (daily public KBO statistics reader)','Referer':URL})
        with opener.open(req,timeout=45) as response:
            assert response.status==200
            return Page(response.read().decode('utf-8-sig'))
    page=fetch(); season=page.season
    assert season==datetime.now(ZoneInfo('Asia/Seoul')).year, 'Unexpected season; preserve old data'
    players=parse_players(page); visited={1}; pending=page.pages.copy()
    while set(pending)-visited:
        n=min(set(pending)-visited)
        assert n<=100, 'Pagination limit exceeded'
        fields=page.fields.copy(); fields.update(__EVENTTARGET=pending[n],__EVENTARGUMENT='')
        time.sleep(1)
        page=fetch(fields)
        assert page.season==season
        page_number=next((v for k,v in page.fields.items() if k.endswith('$hfPage')),None)
        assert page_number==str(n), 'Server did not advance page'
        players.extend(parse_players(page)); visited.add(n); pending.update(page.pages)
    ranks=[p['rank'] for p in players]
    assert len(set(ranks))==len(ranks), 'Duplicate page data'
    assert ranks==list(range(1,len(players)+1)), 'Missing leaderboard rows'
    assert len(players)>=10, 'Unexpectedly small leaderboard; needs review'
    with ThreadPoolExecutor(max_workers=3) as pool:
        recent=list(pool.map(lambda player: fetch_recent(player,season),players))
    for player,record in zip(players,recent): player['recent10']=record
    with ThreadPoolExecutor(max_workers=3) as pool:
        splits=list(pool.map(lambda player: fetch_opponents(player,season),players))
    for player,record in zip(players,splits): player['opponents']=record
    schedule=fetch_schedule()
    now=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')
    result=dict(schema_version=2,schedule=schedule,source_url=URL,season=season,series='KBO 정규시즌',scope='KBO 기본 타자기록의 기본 조회 대상 · 전체 페이지',fetched_at=now,record_cutoff=None,pages=len(visited),players=players)
    dest=ROOT/'dist'/'kbo-data.json'; temp=dest.with_suffix('.tmp'); temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)); temp.replace(dest)
    print(json.dumps({'players':len(players),'pages':len(visited),'season':season,'fetched_at':now},ensure_ascii=False))
if __name__=='__main__':
    try: main()
    except Exception as e:
        print('KBO refresh failed; previous snapshot preserved: '+str(e),file=sys.stderr); sys.exit(1)
