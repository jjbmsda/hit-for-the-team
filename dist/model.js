/* Transparent heuristic ranking, not a calibrated probability model. */
(function(root){
  const weights={base:.5,recent:.3,opponent:.2};
  function evaluate(player,opponent){
    const base=player.hits/player.at_bats;
    const recent=player.recent10;
    const split=player.opponents.teams[opponent]??null;
    const recentAdjusted=(recent.hits+20*base)/(recent.at_bats+20);
    const opponentAdjusted=split?(split.hits+30*base)/(split.at_bats+30):base;
    return {base,recentAdjusted,opponentAdjusted,split,
      score:100*(weights.base*base+weights.recent*recentAdjusted+weights.opponent*opponentAdjusted)};
  }
  function rowsFor(players,schedule,date){
    const games=(schedule?.games??[]).filter(g=>g.date===date);
    return players.flatMap(player=>{
      const own=player.manual_opponent?[{away:player.team,home:player.manual_opponent,status:'scheduled',time:'입력 기록'}]:games.filter(g=>g.away===player.team||g.home===player.team);
      const active=own.filter(g=>!['cancelled','completed'].includes(g.status));
      const opponents=[...new Set(active.map(g=>g.away===player.team?g.home:g.away))];
      if(!opponents.length){
        const reason=own.length?(own.every(g=>g.status==='cancelled')?'경기 취소':'경기 종료'):'경기 없음';
        return [{player,key:player.player_id,eligible:false,reason,opponent:null,score:null,games:own}];
      }
      return opponents.map(opponent=>({player,key:player.player_id+'|'+opponent,opponent,eligible:true,
        games:active.filter(g=>g.away===opponent||g.home===opponent),...evaluate(player,opponent)}));
    }).sort((a,b)=>Number(b.eligible)-Number(a.eligible)||(b.score??0)-(a.score??0)||a.player.name.localeCompare(b.player.name,'ko'));
  }
  root.HitModel={weights,evaluate,rowsFor};
  if(typeof module!=='undefined')module.exports=root.HitModel;
})(globalThis);
