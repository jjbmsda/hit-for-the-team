"""Read the public monthly schedule feed used by KBO Schedule.aspx."""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from datetime import datetime
from zoneinfo import ZoneInfo
import calendar, json, re

SOURCE='https://www.koreabaseball.com/Schedule/Schedule.aspx'
ENDPOINT='https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList'
TEAMS={'KIA','KT','LG','NC','SSG','두산','롯데','삼성','키움','한화'}
class Text(HTMLParser):
    def __init__(self,s):
        super().__init__();self.parts=[];self.feed(s)
    def handle_data(self,s): self.parts.append(s)
def plain(s): return ' '.join(Text(s).parts).strip()

def parse_schedule(data,year,month):
    assert isinstance(data,dict) and isinstance(data.get('rows'),list), 'Schedule response layout changed'
    day=None;games=[]
    for entry in data['rows']:
        cells=entry['row']; byclass={c['Class']:c['Text'] for c in cells if c.get('Class')}
        if 'day' in byclass:
            match=re.match(r'(\d{2})\.(\d{2})\(',plain(byclass['day']))
            assert match and int(match[1])==month, 'Schedule month mismatch'
            day=f'{year}-{month:02}-{int(match[2]):02}'
            datetime.strptime(day,'%Y-%m-%d')
        assert day and 'play' in byclass and 'time' in byclass, 'Incomplete schedule row'
        parts=Text(byclass['play']).parts;teams=[s.strip() for s in parts if s.strip() in TEAMS]
        assert len(teams)==2 and teams[0]!=teams[1], 'Unknown matchup'
        note=plain(cells[-1]['Text']);relay=byclass.get('relay','')
        status='cancelled' if any(word in note for word in ['취소','연기']) else 'completed' if 'REVIEW' in relay else 'live' if 'LIVE' in relay else 'scheduled'
        game_id=re.search(r'gameId=([A-Za-z0-9]+)',relay)
        source_date=re.search(r'gameDate=(\d{8})',relay)
        if source_date: assert source_date[1]==day.replace('-',''), 'Schedule row/link date mismatch'
        games.append(dict(date=day,away=teams[0],home=teams[1],time=plain(byclass['time']),
                          status=status,note=note,venue=plain(cells[-2]['Text']),game_id=game_id[1] if game_id else None))
    return dict(source_url=SOURCE,endpoint=ENDPOINT,start_date=f'{year}-{month:02}-01',
                end_date=f'{year}-{month:02}-{calendar.monthrange(year,month)[1]}',games=games)

def fetch_schedule():
    now=datetime.now(ZoneInfo('Asia/Seoul'));year,month=now.year,now.month
    fields=dict(leId=1,srIdList='0,9,6',seasonId=year,gameMonth=f'{month:02}',teamId='')
    req=Request(ENDPOINT,data=urlencode(fields).encode(),headers={'Referer':SOURCE,'User-Agent':'HitPick/1.0 (daily public KBO statistics reader)'})
    with urlopen(req,timeout=45) as response:
        assert response.status==200
        result=parse_schedule(json.loads(response.read().decode('utf-8-sig')),year,month)
    result['fetched_at']=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')
    return result
