const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const avg=(h,ab)=>ab>0?(h/ab).toFixed(3):'—';
const koreanDate=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const when=s=>new Date(s).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false});
let players=[],snapshot=null,selected='',manualSource='';
$('date').value=koreanDate();
function teams(){
  const prev=$('team').value;
  $('team').innerHTML='<option value="">전체 팀</option>'+[...new Set(players.map(p=>p.team))].sort().map(t=>`<option>${esc(t)}</option>`).join('');
  if(players.some(p=>p.team===prev))$('team').value=prev;
}
function status(row){
  if(!row.eligible)return row.reason;
  return `${row.player.team} vs ${row.opponent} · ${row.games.map(g=>g.time).join(' / ')}${row.games.some(g=>g.status==='live')?' · 진행 중':''}`;
}
function datasetUsable(){
  if(!snapshot)return true;
  const d=$('date').value;
  return d>=koreanDate()&&d>=snapshot.schedule.start_date&&d<=snapshot.schedule.end_date;
}
function summary(){
  $('nextGame').hidden=true;
  if(!snapshot){$('mode').textContent=players.length?'입력 기록':'기록 불러오는 중';$('notice').textContent=players.length?`출처: ${manualSource} · 사용자 입력 기록을 분석합니다.`:'KBO 공식 기록을 불러옵니다.';return;}
  const age=Date.now()-Date.parse(snapshot.fetched_at);
  $('mode').textContent=age>26*3600000?'갱신 지연':'KBO 실제 기록';
  $('notice').textContent=`${snapshot.season} 정규시즌 · ${players.length}명 · 시즌·최근 수집 ${when(snapshot.fetched_at)} · 일정 수집 ${when(snapshot.schedule.fetched_at)} (한국시간). ${age>26*3600000?'갱신이 지연되어 마지막 성공 기록을 표시합니다. ':''}경기 취소·변경은 수집 시점 기준입니다.`;
  const date=$('date').value;
  const games=snapshot.schedule.games.filter(g=>g.date===date);
  if(!datasetUsable()){$('scheduleNote').textContent='오늘부터 수집된 일정의 마지막 날짜까지만 분석할 수 있습니다. 날짜를 변경해 주세요.';return;}
  const active=games.filter(g=>!['completed','cancelled'].includes(g.status));
  $('scheduleNote').textContent=active.length?`${date} · ${active.length}경기 · ${active.map(g=>`${g.away} vs ${g.home}`).join(' / ')}${date!==koreanDate()?' · 현재 수집 기록으로 계산한 예정 경기 순위입니다.':''}`:`${date} · ${games.length?'예정·진행 중인 경기가 없습니다.':'등록된 경기가 없습니다.'} 당일 추천 순위는 표시하지 않습니다.`;
  if(!active.length){
    const next=snapshot.schedule.games.filter(g=>g.date>date&&!['completed','cancelled'].includes(g.status)).map(g=>g.date).sort()[0];
    if(next){$('nextGame').hidden=false;$('nextGame').textContent=`다음 경기일 (${next.slice(5)}) 보기`;$('nextGame').onclick=()=>{$('date').value=next;render();};}
  }
}
function render(){
  summary();
  const all=datasetUsable()?HitModel.rowsFor(players,snapshot?.schedule,$('date').value):[];
  const rows=all.filter(r=>(!$('team').value||r.player.team===$('team').value));
  const ranked=rows.filter(r=>r.eligible);
  if(!rows.some(r=>r.key===selected))selected=rows[0]?.key??'';
  $('count').textContent=`${ranked.length}명 추천 / ${rows.length}명 조회`;
  $('leaders').innerHTML=ranked.slice(0,3).map((r,i)=>`<button class="leader ${r.key===selected?'active':''}" data-key="${esc(r.key)}"><div class="rank">PICK 0${i+1}</div><h3>${esc(r.player.name)}</h3><div class="meta">${esc(r.player.team)} vs ${esc(r.opponent)}</div><div class="pct">${r.score.toFixed(1)}<small>점</small></div><div class="hint meta">세 가지 타율 종합점수</div><div class="track"><span style="width:${r.score}%"></span></div></button>`).join('')||'<div class="empty">추천 대상 경기가 없거나 조회 조건에 맞는 선수가 없습니다.</div>';
  let rank=0;
  $('rows').innerHTML=rows.map(r=>{
    const p=r.player,n=r.eligible?String(++rank).padStart(2,'0'):'—';
    const opp=r.eligible?`${avg(r.split?.hits,r.split?.at_bats)}<small class="cellmeta">vs ${esc(r.opponent)} · ${r.split?.at_bats??0}타수</small>`:esc(r.reason);
    return `<tr><td><button data-key="${esc(r.key)}"><span class="num">${n}</span><b>${esc(p.name)}</b><small>${esc(p.team)}</small></button></td><td>${avg(p.hits,p.at_bats)}</td><td>${avg(p.recent10.hits,p.recent10.at_bats)}</td><td>${opp}</td><td>${r.eligible?r.score.toFixed(1)+'점':'—'}</td></tr>`;
  }).join('');
  const row=rows.find(r=>r.key===selected);renderDetail(row);
  document.querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>{selected=b.dataset.key;render();});
}
function renderDetail(r){
  if(!r){$('detail').innerHTML='<h2>분석할 선수가 없습니다</h2><p>날짜 또는 조회 조건을 변경해 주세요.</p>';return;}
  const p=r.player,recent=p.recent10;
  const opp=r.split;
  $('detail').innerHTML=`<div class="eyelabel">PLAYER INSIGHT</div><h2>${esc(p.name)}</h2><div class="meta">${esc(status(r))}</div><div class="result">${r.eligible?r.score.toFixed(1):'—'}<small>${r.eligible?'점':''}</small></div><p>${r.eligible?'종합점수 · 안타 확률이 아닌 비교 지표':r.reason+' · 당일 순위 제외'}</p>
  <div class="stat"><span>기본타율</span><b>${avg(p.hits,p.at_bats)}</b></div><p class="footnote">${p.at_bats}타수 ${p.hits}안타 · 이번 시즌</p>
  <div class="stat"><span>최근타율(10경기)</span><b>${avg(recent.hits,recent.at_bats)}</b></div><p class="footnote">${recent.at_bats}타수 ${recent.hits}안타${recent.start_date?`<br>${esc(recent.start_date)} ~ ${esc(recent.end_date)} · ${recent.games}경기`:''}</p>
  <div class="stat"><span>상대팀 상대 타율</span><b>${r.eligible?avg(opp?.hits,opp?.at_bats):'—'}</b></div><p class="footnote">${r.eligible?`${esc(r.opponent)} 상대 · ${opp?.at_bats??0}타수 ${opp?.hits??0}안타 · 이번 시즌${!opp?.at_bats?' · 상대 전적이 없어 순위 계산에는 기본타율을 사용합니다.':''}`:'당일 상대팀 없음'}${p.opponents.fetched_at?`<br>상대 기록 수집 ${when(p.opponents.fetched_at)}`:''}</p>
  ${r.eligible?`<div class="explain">기본타율 50% + 최근 10경기 30% + 상대팀 20%<br>계산값: ${r.base.toFixed(3)} / ${r.recentAdjusted.toFixed(3)} / ${r.opponentAdjusted.toFixed(3)}<br>최근·상대 기록은 표본을 보정합니다.</div>`:'<div class="explain">경기가 있는 날짜를 선택하면 상대팀 기록과 종합점수를 확인할 수 있습니다.</div>'}`;
}
$('team').onchange=render;$('date').onchange=render;
$('openData').onclick=()=>{
  const rows=HitModel.rowsFor(players,snapshot?.schedule,$('date').value).filter(r=>r.eligible);
  $('dataText').value=rows.map(r=>[r.player.name,r.player.team,r.player.at_bats,r.player.hits,r.player.recent10.at_bats,r.player.recent10.hits,r.opponent,r.split?.at_bats??0,r.split?.hits??0,r.player.confirmed?1:0].join(',')).join('\n');
  $('error').textContent='';$('dataDialog').showModal();
};
$('closeData').onclick=()=>$('dataDialog').close();
$('dataForm').onsubmit=e=>{
  e.preventDefault();
  try{
    const source=$('source').value.trim();if(!source)throw Error('기록 출처를 입력해 주세요.');
    const next=$('dataText').value.trim().split(/\r?\n/).map((line,i)=>{
      const a=line.split(',').map(s=>s.trim());
      if(a.length!==10||a.some(x=>!x))throw Error(`${i+1}행: 10개 항목을 빠짐없이 입력해 주세요.`);
      const [ab,h,rab,rh,oab,oh,confirmed]=[2,3,4,5,7,8,9].map(n=>Number(a[n]));
      if([ab,h,rab,rh,oab,oh,confirmed].some(n=>!Number.isInteger(n)||n<0)||ab<=0||h>ab||rh>rab||oh>oab||rab>ab||oab>ab||rh>h||oh>h||rab-rh>ab-h||oab-oh>ab-h||![0,1].includes(confirmed)||a[1]===a[6])throw Error(`${i+1}행: 타수·안타 또는 상대팀을 확인하세요.`);
      return {player_id:'manual-'+i,name:a[0],team:a[1],at_bats:ab,hits:h,recent10:{games:10,at_bats:rab,hits:rh},opponents:{teams:{[a[6]]:{at_bats:oab,hits:oh}}},manual_opponent:a[6],confirmed:!!confirmed};
    });
    const ids=next.map(p=>p.name+'|'+p.team+'|'+p.manual_opponent);
    if(new Set(ids).size!==ids.length)throw Error('같은 선수와 상대팀이 중복되었습니다.');
    players=next;snapshot=null;manualSource=source;$('scheduleNote').textContent='입력한 상대팀 기준으로 순위를 계산합니다.';teams();render();$('dataDialog').close();
  }catch(error){$('error').textContent=error.message;}
};
async function load(){
  try{
    const response=await fetch('kbo-data.json',{cache:'no-store'});if(!response.ok)throw Error('기록을 불러올 수 없습니다.');
    const data=await response.json();
    if(data.schema_version!==2||!Array.isArray(data.players)||!data.players.length||!Array.isArray(data.schedule?.games)||!Number.isFinite(Date.parse(data.fetched_at)))throw Error('기록 형식을 확인할 수 없습니다.');
    for(const p of data.players){
      if(!p.player_id||!p.name||!p.team||!Number.isInteger(p.at_bats)||!Number.isInteger(p.hits)||p.at_bats<=0||p.hits<0||p.hits>p.at_bats||!p.recent10||!p.opponents?.teams)throw Error('선수 기록이 올바르지 않습니다.');
      for(const r of [p.recent10,...Object.values(p.opponents.teams)])if(!Number.isInteger(r.at_bats)||!Number.isInteger(r.hits)||r.at_bats<0||r.hits<0||r.hits>r.at_bats)throw Error('세부 기록이 올바르지 않습니다.');
    }
    snapshot=data;players=data.players;$('date').min=koreanDate();$('date').max=data.schedule.end_date;teams();render();
  }catch(error){players=[];snapshot=null;render();$('mode').textContent='기록 로딩 실패';$('notice').textContent=error.message+' 새로고침하거나 기록을 직접 입력해 주세요.';}
}
render();load();
