function portrait(p){
  const fallback=`https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2026/${encodeURIComponent(p.player_id)}.jpg`;
  const src=p.profile_image||fallback;
  return `<span class="portrait-shell" style="--team:${teamColors[p.team]||'#1d6b4f'}"><img class="field-avatar" src="${esc(src)}" alt="${esc(p.name)}" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span class="avatar-fallback" hidden>${esc(p.name.slice(-1))}</span></span>`;
}
