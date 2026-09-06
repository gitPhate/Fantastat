/* All catalogue search, filtering, and sorting happens on the season array. */
const state = { players: [], selected: null, sort: "expected_points", descending: true };
const $ = id => document.getElementById(id);
const missing = value => value === null || value === undefined || value === "";
const text = value => missing(value) ? "—" : String(value);
const roundedText = value => missing(value) ? "—" : String(Math.round(value));
const expectedPointsText = value => roundedText(value);
const predictedAppearancesText = value => roundedText(value);
const escaped = value => text(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function request(url) { const res = await fetch(url); const body = await res.json(); if (!res.ok) throw Error(body.error); return body; }
function options(id, values, label) { const select=$(id), previous=select.value; select.innerHTML=`<option value="">${label}</option>` + (id === "fascia" ? '<option value="__missing__">Senza guida</option>' : "") + values.map(v=>`<option>${escaped(v)}</option>`).join(""); select.value=previous; }
function filtered() {
  const needle=$("search").value.trim().toLocaleLowerCase(), role=$("role").value, club=$("club").value, tier=$("fascia").value;
  const score = p => !needle ? 3 : p.name.toLocaleLowerCase() === needle ? 0 : p.name.toLocaleLowerCase().startsWith(needle) ? 1 : 2;
  return state.players.filter(p => (!needle || p.name.toLocaleLowerCase().includes(needle)) && (!role || p.role===role) && (!club || p.club===club) && (!tier || (tier === "__missing__" ? missing(p.tier) : p.tier===tier))).sort((a,b) => {
    const match=score(a)-score(b); if (needle && match) return match;
    const av=a[state.sort], bv=b[state.sort]; let result;
    if (state.sort === "expected_points" && missing(av) !== missing(bv)) return missing(av) ? 1 : -1;
    if (missing(av) !== missing(bv)) result=missing(av)?1:-1;
    else if (typeof av === "number" && typeof bv === "number") result=av-bv;
    else result=String(av??"").localeCompare(String(bv??""), "it", {sensitivity:"base"});
    return (state.descending ? -result : result) || a.name.localeCompare(b.name,"it",{sensitivity:"base"}) || a.id-b.id;
  }).map(p => ({p, score:score(p)}));
}
function hasInjuries(player) { return !missing(player.injuries) && String(player.injuries).trim() !== ""; }
function render() { const rows=filtered(); $("count").textContent=`${rows.length} giocatori`; $("players").innerHTML=rows.map(({p})=>`<tr data-id="${p.id}" class="${state.selected===p.id?"selected":""}"><td>${escaped(p.name)}${hasInjuries(p)?' <span class="injury-alert" data-tooltip="Infortunato" aria-label="Infortunato" tabindex="0">⚠</span>':''}</td><td>${escaped(p.role)}</td><td>${escaped(p.club)}</td><td>${text(p.quotation)}</td><td>${text(p.fvm)}</td><td>${expectedPointsText(p.expected_points)}</td><td>${predictedAppearancesText(p.predicted_appearances)}</td><td>${text(p.predicted_fantasy_average)}</td><td>${escaped(p.tier)}</td></tr>`).join(""); document.querySelectorAll("#players tr").forEach(row=>row.onclick=()=>showPlayer(+row.dataset.id)); document.querySelectorAll("#players .injury-alert").forEach(icon=>{ icon.addEventListener("mouseenter",()=>showColumnTooltip(icon)); icon.addEventListener("mouseleave",hideColumnTooltip); icon.addEventListener("focus",()=>showColumnTooltip(icon)); icon.addEventListener("blur",hideColumnTooltip); }); }
function definition(label, value) { return `<dt>${label}</dt><dd class="${missing(value)?"unavailable":""}">${missing(value)?"Non disponibile":escaped(value)}</dd>`; }
function chart(history, field, color) { const points=history.filter(r=>r.has_statistics && !missing(r[field])); if (!points.length) return '<p class="unavailable">Non disponibile</p>'; const max=Math.max(...points.map(r=>r[field])), min=Math.min(...points.map(r=>r[field])), span=max-min||1; const coords=points.map((r,i)=>`${i*100/Math.max(points.length-1,1)},${94-(r[field]-min)*82/span}`).join(" "); return `<svg class="chart" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline fill="none" stroke="${color}" stroke-width="2" points="${coords}"/></svg>`; }
async function showPlayer(id) { state.selected=id; render(); try { const detail=await request(`/api/player?season=${$("season").value}&id=${id}`), p=detail.player, h=detail.history; $("detail").innerHTML=`<h2>${escaped(p.name)}</h2><p>ID Fantacalcio: ${p.id}</p><h3>Listone</h3><dl>${definition("Ruolo",p.role)}${definition("Squadra",p.club)}${definition("Quotazione",p.quotation)}${definition("FVM",p.fvm)}${definition("Indice di titolarità",p.starting_index)}${definition("Età",p.age)}</dl><h3>Ranking</h3><dl>${definition("Rank",p.rank)}${definition("Presenze previste",p.predicted_appearances)}${definition("FM prevista",p.predicted_fantasy_average)}${definition("Punti attesi",p.expected_points)}${definition("Validazione",p.validation_status)}</dl><h3>Guida unificata</h3><dl>${definition("Fascia",p.tier)}${definition("Funzione",p.function)}${definition("Note",p.notes)}${definition("Infortuni",p.injuries)}${definition("Rischi",p.risks)}${definition("Piazzati",p.set_pieces)}${definition("Gerarchia",p.hierarchy)}</dl><h3>Storico</h3>${h.length?`<table class="history"><tr><th>Stagione</th><th>Squadra</th><th>Pv</th><th>FM</th><th>Rank</th><th>Pt. attesi</th></tr>${h.map(r=>`<tr><td>${r.label}</td><td>${r.has_statistics?escaped(r.club):"—"}</td><td>${r.has_statistics?text(r.appearances):"—"}</td><td>${r.has_statistics?text(r.fantasy_average):"—"}</td><td>${r.has_ranking?text(r.rank):"—"}</td><td>${r.has_ranking?text(r.expected_points):"—"}</td></tr>`).join("")}</table><h4>Presenze</h4>${chart(h,"appearances","#60a5fa")}<h4>Fantamedia</h4>${chart(h,"fantasy_average","#fbbf24")}`:'<p class="unavailable">Nessuna evidenza storica disponibile.</p>'}`; } catch(e) { $("detail").innerHTML=`<p class="unavailable">${escaped(e.message)}</p>`; } }
async function loadSeason() { state.selected=null; state.sort="expected_points"; state.descending=true; $("search").value=""; $("role").value=""; $("club").value=""; $("fascia").value=""; state.players=await request(`/api/catalogue?season=${$("season").value}`); options("club", [...new Set(state.players.map(p=>p.club))].sort(), "Tutte le squadre"); options("fascia", [...new Set(state.players.map(p=>p.tier).filter(Boolean))].sort(), "Tutte le fasce"); $("guide").href=`/guide.html?season=${$("season").value}`; render(); $("detail").innerHTML="<p>Seleziona un giocatore per vedere le evidenze dell'asta.</p>"; }
async function start() { try { const boot=await request("/api/bootstrap"); $("season").innerHTML=boot.seasons.map(s=>`<option value="${s.season_start}">${s.label}</option>`).join(""); $("season").value=boot.selected_season; await loadSeason(); } catch(e) { document.body.innerHTML=`<main><aside><h1>Snapshot non disponibile</h1><p>${escaped(e.message)}</p></aside></main>`; } }
["search","role","club","fascia"].forEach(id=>$(id).addEventListener("input",render)); $("role").addEventListener("change",()=>{ const role=$("role").value; const valid=state.players.filter(p=>!role||p.role===role).map(p=>p.tier).filter(Boolean); options("fascia", [...new Set(valid)].sort(), "Tutte le fasce"); render(); }); $("season").addEventListener("change",loadSeason); document.querySelectorAll("th[data-key]").forEach(th=>th.onclick=()=>{ const key=th.dataset.key; state.descending=state.sort===key?!state.descending:key!=="name"; state.sort=key; render(); });
const columnTooltip = document.createElement("div");
columnTooltip.className = "column-tooltip";
columnTooltip.style.display = "none";
document.body.appendChild(columnTooltip);
function showColumnTooltip(header) {
  const bounds = header.getBoundingClientRect();
  columnTooltip.textContent = header.dataset.tooltip;
  columnTooltip.style.left = `${bounds.left + bounds.width / 2}px`;
  const above = bounds.top > 48;
  columnTooltip.style.top = `${above ? bounds.top - 4 : bounds.bottom + 4}px`;
  columnTooltip.style.transform = above ? "translate(-50%, -100%)" : "translateX(-50%)";
  columnTooltip.style.display = "block";
}
function hideColumnTooltip() { columnTooltip.style.display = "none"; }
document.querySelectorAll("th[data-tooltip]").forEach(header => {
  header.addEventListener("mouseenter", () => showColumnTooltip(header));
  header.addEventListener("mouseleave", hideColumnTooltip);
  header.addEventListener("focus", () => showColumnTooltip(header));
  header.addEventListener("blur", hideColumnTooltip);
});
start();
