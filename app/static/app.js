const $ = (s, el = document) => el.querySelector(s);
const api = async (url, opts) => {
  const r = await fetch(url, opts);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || "Error");
  return j;
};
const money = v => (v == null ? "—" : (v < 0 ? "−" : "") + Math.abs(v).toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const cls = v => (v > 0 ? "pos" : v < 0 ? "neg" : "");
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let instruments = [], accounts = [], tradesCache = [], periodKind = "week", pendingShots = [], editingShots = [];

function qs() {
  const p = new URLSearchParams();
  if ($("#f-inst").value) p.set("instrument", $("#f-inst").value);
  if ($("#f-acc").value) p.set("account", $("#f-acc").value);
  if ($("#f-from").value) p.set("from", $("#f-from").value);
  if ($("#f-to").value) p.set("to", $("#f-to").value);
  return p.toString();
}

// ---------- pestañas ----------
function show(tab) {
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
  document.querySelectorAll("main > section").forEach(s => (s.hidden = s.id !== "tab-" + tab));
  $("#filters").hidden = !["resumen", "periodos", "analisis", "trackrecord", "operaciones"].includes(tab);
}
$("#tabs").addEventListener("click", e => e.target.dataset.tab && show(e.target.dataset.tab));
["#f-inst", "#f-acc", "#f-from", "#f-to"].forEach(s => $(s).addEventListener("change", refresh));
$("#f-clear").onclick = () => { $("#f-inst").value = $("#f-acc").value = $("#f-from").value = $("#f-to").value = ""; refresh(); };

// ---------- resumen ----------
function kpi(label, value, c = "") { return `<div class="kpi"><span>${label}</span><b class="${c}">${value}</b></div>`; }

function bars(el, data, fmt = money) {
  const keys = Object.keys(data);
  if (!keys.length) { el.innerHTML = '<p class="muted">Sin datos</p>'; return; }
  const max = Math.max(...keys.map(k => Math.abs(data[k].net)), 1);
  el.innerHTML = keys.map(k => {
    const d = data[k];
    return `<div class="bar"><em title="${esc(k)}">${esc(k)}</em><i class="${d.net >= 0 ? "pos" : "neg"}" style="width:${Math.abs(d.net) / max * 55}%;background:currentColor"></i><span class="${cls(d.net)}">${fmt(d.net)}</span> <span class="muted">· ${d.n} op · ${Math.round(d.wins / d.n * 100)}%</span></div>`;
  }).join("");
}

function equityChart(el, pts, start) {
  if (pts.length < 2) { el.innerHTML = '<p class="muted">Se necesitan al menos 2 operaciones cerradas.</p>'; return; }
  const W = 900, H = 240, L = 60, B = 24, T = 10, R = 10;
  const ys = pts.map(p => p.equity).concat(start), min = Math.min(...ys), max = Math.max(...ys), span = max - min || 1;
  const x = i => L + i / (pts.length - 1) * (W - L - R), y = v => T + (1 - (v - min) / span) * (H - T - B);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.equity).toFixed(1)}`).join("");
  const end = pts[pts.length - 1].equity, color = end >= start ? "var(--pos)" : "var(--neg)";
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Curva de capital">
    <line x1="${L}" x2="${W - R}" y1="${y(start)}" y2="${y(start)}" stroke="var(--line)" stroke-dasharray="4 4"/>
    <text x="${L - 6}" y="${y(max) + 4}" text-anchor="end">${money(max)}</text>
    <text x="${L - 6}" y="${y(min) + 4}" text-anchor="end">${money(min)}</text>
    <text x="${L}" y="${H - 6}">${pts[0].t.slice(0, 10)}</text><text x="${W - R}" y="${H - 6}" text-anchor="end">${pts[pts.length - 1].t.slice(0, 10)}</text>
    <path d="${path}" fill="none" stroke="${color}" stroke-width="2"/></svg>`;
}

function calendar(el, daily) {
  const days = Object.keys(daily).sort();
  if (!days.length) { el.innerHTML = '<p class="muted">Sin datos</p>'; return; }
  const max = Math.max(...days.map(d => Math.abs(daily[d])), 1);
  const first = new Date(days[0].slice(0, 7) + "-01T00:00"), last = new Date(days[days.length - 1] + "T00:00");
  let html = "";
  for (let m = new Date(first); m <= last; m = new Date(m.getFullYear(), m.getMonth() + 1, 1)) {
    const y = m.getFullYear(), mo = m.getMonth(), nd = new Date(y, mo + 1, 0).getDate();
    let tot = 0, cells = "<div style='border:0'></div>".repeat((m.getDay() + 6) % 7);
    for (let d = 1; d <= nd; d++) {
      const key = `${y}-${String(mo + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`, v = daily[key];
      if (v != null) tot += v;
      const a = v == null ? 0 : 0.12 + 0.3 * Math.abs(v) / max;
      cells += `<div style="${v != null ? `background:color-mix(in srgb, var(${v >= 0 ? "--pos" : "--neg"}) ${a * 100}%, transparent)` : ""}"><b>${d}</b>${v != null ? money(v) : ""}</div>`;
    }
    html += `<h3>${m.toLocaleDateString("es-ES", { month: "long", year: "numeric" })} · <span class="${cls(tot)}">${money(tot)}</span></h3><div class="cal">${cells}</div>`;
  }
  el.innerHTML = html;
}

async function loadSummary() {
  const m = await api("/api/metrics?" + qs());
  $("#kpis").innerHTML = [
    kpi("Balance", money(m.balance)),
    kpi("P&L neto (USD)", money(m.total_net), cls(m.total_net)),
    kpi("Retorno TWR", `${m.twr.twr_pct} %`, cls(m.twr.twr_pct)),
    kpi("Ganancia absoluta", m.twr.abs_gain_pct == null ? "—" : `${m.twr.abs_gain_pct} %`, cls(m.twr.abs_gain_pct)),
    kpi("Operaciones", `${m.n}${m.open ? ` (+${m.open} abiertas)` : ""}`),
    kpi("Win rate", m.win_rate + " %"),
    kpi("Profit factor", m.profit_factor ?? "—"),
    kpi("Expectancy", money(m.expectancy), cls(m.expectancy)),
    kpi("Payoff", m.payoff ?? "—"),
    kpi("R medio", m.avg_r == null ? "—" : m.avg_r + " R"),
    kpi("Máx. drawdown", `${money(m.max_drawdown)} (${m.max_drawdown_pct} %)`, m.max_drawdown ? "neg" : ""),
    kpi("Mejor / peor", `${money(m.best)} / ${money(m.worst)}`),
    kpi("Rachas (G/P)", `${m.max_win_streak} / ${m.max_loss_streak}`),
    kpi("Tiempo medio", m.avg_hold_min == null ? "—" : m.avg_hold_min + " min"),
  ].join("");
  equityChart($("#equity"), m.equity, m.starting_balance);
  bars($("#g-instrument"), m.by_instrument); bars($("#g-setup"), m.by_setup);
  bars($("#g-weekday"), m.by_weekday); bars($("#g-hour"), m.by_hour); bars($("#g-mistake"), m.by_mistake);
  calendar($("#calendar"), m.daily);
}

// ---------- operaciones ----------
async function loadTrades() {
  tradesCache = await api("/api/trades?" + qs());
  const head = "<tr><th>Salida</th><th>Instr.</th><th>Lado</th><th class=n>Vol</th><th class=n>Entrada</th><th class=n>Salida</th><th class=n>Neto</th><th class=n>R</th><th>Setup</th><th>Plan</th><th></th></tr>";
  $("#trades").innerHTML = head + tradesCache.map(t => `<tr>
    <td>${esc((t.exit_time || t.entry_time).slice(0, 16))}${t.exit_time ? "" : " <span class=muted>(abierta)</span>"}</td><td>${t.instrument}</td><td>${t.side === "buy" ? "Compra" : "Venta"}</td>
    <td class=n>${t.volume}</td><td class=n>${t.entry_price}</td><td class=n>${t.exit_price ?? "—"}</td>
    <td class="n ${cls(t.net)}">${money(t.net)}</td><td class=n>${t.r ?? "—"}</td><td>${esc(t.setup)}</td><td>${esc(t.plan_grade)}</td>
    <td><span class="thumbs">${t.shots.map(sh => `<a href="/shots/${sh.file}" target="_blank"><img src="/shots/${sh.file}" alt="captura"></a>`).join("")}</span> <button class="small ghost" data-edit="${t.id}">Editar</button> <button class="small ghost" data-del="${t.id}">✕</button></td></tr>`).join("");
  const uniq = k => [...new Set(tradesCache.map(t => t[k]).filter(Boolean))].map(v => `<option value="${esc(v)}">`).join("");
  $("#setups").innerHTML = uniq("setup"); $("#mistakes").innerHTML = uniq("mistake");
}
$("#trades").addEventListener("click", async e => {
  if (e.target.dataset.del && confirm("¿Borrar esta operación?")) { await api("/api/trades/" + e.target.dataset.del, { method: "DELETE" }); refresh(); }
  if (e.target.dataset.edit) editTrade(tradesCache.find(t => t.id == e.target.dataset.edit));
});

// ---------- formulario ----------
const form = $("#trade-form");
const toLocal = s => (s ? s.replace(" ", "T").slice(0, 19) : "");
function editTrade(t) {
  form.reset();
  for (const [k, v] of Object.entries(t)) if (form.elements[k] && form.elements[k].type !== "file") form.elements[k].value = k.endsWith("_time") ? toLocal(v) : (v ?? "");
  $("#form-title").textContent = "Editar operación #" + t.id;
  editingShots = t.shots.slice(); pendingShots = []; renderShots();
  show("nueva");
}
function resetForm() { pendingShots = []; editingShots = []; renderShots(); form.reset(); form.elements.id.value = ""; $("#form-title").textContent = "Nueva operación"; $("#form-msg").textContent = ""; }
$("#cancel-edit").onclick = () => { resetForm(); show("operaciones"); };
form.onsubmit = async e => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(form));
  const id = d.id; delete d.id;
  for (const k of ["entry_time", "exit_time"]) if (d[k]) d[k] = d[k].replace("T", " ").padEnd(19, ":00").slice(0, 19);
  const inst = instruments.find(i => i.code === d.instrument);
  if (d.exit_time && d.exit_price && d.profit === "" && inst) {
    d.profit = ((d.exit_price - d.entry_price) * (d.side === "buy" ? 1 : -1) * d.volume * inst.contract_size).toFixed(2);
  }
  try {
    const res = id ? (await api("/api/trades/" + id, put(d)), { id }) : await api("/api/trades", post(d));
    for (const f of pendingShots) { const fd = new FormData(); fd.append("file", f); await api(`/api/trades/${res.id}/shots`, { method: "POST", body: fd }); }
    resetForm(); await refresh(); show("operaciones");
  } catch (err) { $("#form-msg").textContent = err.message; }
};
const post = d => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(d) });
const put = d => ({ ...post(d), method: "PUT" });

// ---------- capturas ----------
function renderShots() {
  $("#shot-list").innerHTML = editingShots.map(sh => `<figure><img src="/shots/${sh.file}"><button type="button" class="small" data-rm-saved="${sh.id}">✕</button></figure>`).join("")
    + pendingShots.map((f, i) => `<figure><img src="${URL.createObjectURL(f)}"><button type="button" class="small" data-rm-new="${i}">✕</button></figure>`).join("");
}
$("#shot").onchange = e => { pendingShots.push(...e.target.files); e.target.value = ""; renderShots(); };
$("#paste-zone").addEventListener("paste", e => {
  for (const it of e.clipboardData.items) if (it.type.startsWith("image/")) { const f = it.getAsFile(); pendingShots.push(new File([f], `captura.${it.type.split("/")[1]}`, { type: it.type })); }
  renderShots(); e.preventDefault();
});
$("#shot-list").addEventListener("click", async e => {
  if (e.target.dataset.rmNew != null) { pendingShots.splice(+e.target.dataset.rmNew, 1); renderShots(); }
  if (e.target.dataset.rmSaved) {
    await api("/api/shots/" + e.target.dataset.rmSaved, { method: "DELETE" });
    editingShots = editingShots.filter(sh => sh.id != e.target.dataset.rmSaved); renderShots();
  }
});

// ---------- semanas y meses ----------
async function loadPeriods() {
  const rows = await api(`/api/periods?kind=${periodKind}&` + qs());
  if (!rows.length) { $("#periods").innerHTML = '<div class="card"><p class="muted">Sin operaciones cerradas.</p></div>'; return; }
  $("#periods").innerHTML = rows.map(p => {
    const small = p.n < 20 ? `<span class="warn"> · muestra pequeña (n=${p.n}): léelo como diario, no como estadística</span>` : "";
    const title = periodKind === "week" ? `Semana ${p.period} <span class="muted">(desde ${p.label})</span>` : p.label;
    return `<div class="card period"><h3>${title}${small}</h3>
      <div class="kpis">${[
        kpi("P&L neto", money(p.net), cls(p.net)),
        kpi("vs periodo anterior", p.vs_prev_net == null ? "—" : money(p.vs_prev_net), cls(p.vs_prev_net)),
        kpi("Operaciones", p.n),
        kpi("Win rate", `${p.win_rate} %<span class="ci"> [${p.win_rate_ci.join("–")}]</span>`),
        kpi("Profit factor", p.profit_factor ?? "—"),
        kpi("Expectancy", money(p.expectancy), cls(p.expectancy)),
        kpi("R medio", p.avg_r ?? "—"),
        kpi("Cumplió plan (A/B)", p.plan_adherence == null ? "—" : `${p.plan_adherence} % <span class="ci">de ${p.graded}</span>`),
        kpi("Con error anotado", p.mistakes),
        kpi("Emoción media", p.avg_emotion ?? "—"),
      ].join("")}</div>
      <div class="cols">
        <label>Qué salió bien<textarea data-rv="${p.period}" data-f="went_well" rows="2">${esc(p.review.went_well)}</textarea></label>
        <label>Qué mejorar (errores)<textarea data-rv="${p.period}" data-f="to_improve" rows="2">${esc(p.review.to_improve)}</textarea></label>
        <label>Objetivo de conducta próximo periodo<textarea data-rv="${p.period}" data-f="next_goal" rows="2">${esc(p.review.next_goal)}</textarea></label>
      </div></div>`;
  }).join("");
}
$("#periods").addEventListener("change", async e => {
  const per = e.target.dataset.rv; if (!per) return;
  const body = {}; document.querySelectorAll(`[data-rv="${per}"]`).forEach(t => (body[t.dataset.f] = t.value));
  await api("/api/reviews/" + per, put(body));
});
document.querySelectorAll(".kind").forEach(b => (b.onclick = () => {
  periodKind = b.dataset.kind;
  document.querySelectorAll(".kind").forEach(x => x.classList.toggle("ghost", x !== b));
  loadPeriods();
}));

// ---------- análisis por tramos ----------
function bucketTable(el, list) {
  if (!list.length) { el.innerHTML = '<p class="muted">Sin datos</p>'; return; }
  el.innerHTML = "<table><tr><th></th><th class=n>n</th><th class=n>Neto</th><th class=n>Win rate [IC 95%]</th><th class=n>PF</th><th class=n>Expectancy</th><th class=n>R</th></tr>" +
    list.map(b => `<tr class="${b.reliable ? "" : "warn"}"><td>${esc(b.key)}</td><td class=n>${b.n}</td><td class="n ${cls(b.net)}">${money(b.net)}</td>
      <td class=n>${b.win_rate} % <span class="ci">[${b.win_rate_ci.join("–")}]</span></td><td class=n>${b.profit_factor ?? "—"}</td>
      <td class="n ${cls(b.expectancy)}">${money(b.expectancy)}</td><td class=n>${b.avg_r ?? "—"}</td></tr>`).join("") + "</table>";
}
async function loadAnalysis() {
  const a = await api("/api/analysis?" + qs());
  $("#analysis-note").innerHTML = `<b>Cómo leerlo.</b> Las filas en cursiva tienen menos de ${a.min_n} operaciones: no son fiables. El intervalo del win rate (Wilson 95 %) muestra cuánto puede variar por azar; si es muy ancho, no hay conclusión. Cada vez que cortas los datos (24 horas × días × setups) aumentas la probabilidad de ver un "mejor tramo" que es solo suerte: con 24 franjas hay cerca de un 70 % de que alguna parezca significativa sin serlo. Úsalo para formular hipótesis y compruébalas en operaciones nuevas, no para cambiar tu operativa por una sola franja.`;
  bucketTable($("#a-hour"), a.by_hour); bucketTable($("#a-weekday"), a.by_weekday);
  bucketTable($("#a-volume"), a.by_volume); bucketTable($("#a-setup"), a.by_setup);
}

// ---------- importar ----------
$("#import-btn").onclick = async () => {
  const f = $("#import-file").files[0];
  if (!f) return;
  const fd = new FormData(); fd.append("file", f); fd.append("account_id", $("#import-acc").value);
  try {
    const r = await api("/api/import", { method: "POST", body: fd });
    const sk = Object.entries(r.skipped_symbols).map(([s, n]) => `${s} (${n})`).join(", ");
    $("#import-msg").textContent = (r.already_imported ? "Este archivo ya se había importado antes. " : "") + `Leídas ${r.read} · nuevas ${r.added} · duplicadas ${r.duplicates}` + (sk ? ` · símbolos no reconocidos y omitidos: ${sk}` : "");
    refresh();
  } catch (err) { $("#import-msg").textContent = err.message; }
};

// ---------- ajustes ----------
async function loadSettings() {
  [instruments, accounts] = await Promise.all([api("/api/instruments"), api("/api/accounts")]);
  const opts = instruments.map(i => `<option value="${i.code}">${i.name}</option>`).join("");
  $("#f-inst").innerHTML = '<option value="">Todos los instrumentos</option>' + opts;
  form.elements.instrument.innerHTML = opts;
  const accOpts = accounts.filter(x => x.active).map(x => `<option value="${x.id}">${esc(x.name)} (${x.kind})</option>`).join("");
  const keep = $("#f-acc").value;
  $("#f-acc").innerHTML = '<option value="">Todas las cuentas</option>' + accOpts; $("#f-acc").value = keep;
  form.elements.account_id.innerHTML = accOpts; $("#import-acc").innerHTML = accOpts; $("#mv-acc").innerHTML = accOpts;
  $("#inst-table").innerHTML = "<tr><th>Instrumento</th><th>Tamaño de contrato</th><th>Tick</th><th></th></tr>" + instruments.map(i =>
    `<tr><td>${i.name}</td><td><input data-c="${i.code}" data-f="contract_size" type="number" step="any" value="${i.contract_size}"></td>
     <td><input data-c="${i.code}" data-f="tick_size" type="number" step="any" value="${i.tick_size}"></td>
     <td><button class="small" data-save="${i.code}">Guardar</button></td></tr>`).join("");
  const sel = (v, list) => list.map(([k, t]) => `<option value="${k}" ${v === k ? "selected" : ""}>${t}</option>`).join("");
  $("#acc-table").innerHTML = accounts.map(x => `<div class="acc ${x.active ? "" : "archived"}" data-acc="${x.id}">
    <div class="cols">
      <label>Nombre<input data-f="name" value="${esc(x.name)}"></label>
      <label>Tipo<select data-f="kind">${sel(x.kind, [["real", "Real"], ["demo", "Demo"], ["fondeo", "Fondeo"]])}</select></label>
      <label>Bróker<input data-f="broker" value="${esc(x.broker)}"></label>
      <label>Balance inicial<input data-f="starting_balance" type="number" step="any" value="${x.starting_balance}"></label>
      <label>Unidad<select data-f="money_scale">${sel(String(x.money_scale), [["1", "USD (normal)"], ["0.01", "USC (cuenta cent)"]])}</select></label>
      <label>Hora del servidor MT5<select data-f="server_mode">${sel(x.server_mode, [["utc", "UTC (GMT+0)"], ["ny_close", "Cierre NY (GMT+2/+3)"], ["fixed", "Fija (desfase)"]])}</select></label>
      <label>Desfase fijo (h vs UTC)<input data-f="server_offset" type="number" step="any" value="${x.server_offset}"></label>
    </div>
    <p class="muted">Dep./retiros ${money(x.movements)} · P&amp;L <span class="${cls(x.net)}">${money(x.net)}</span> · Balance <b>${money(x.balance)}</b>${x.money_scale !== 1 ? ` (≈ ${money(x.balance_usd)} USD)` : ""} · ${x.n_trades} operaciones${x.active ? "" : " · archivada"}</p>
    <div class="actions"><button class="small" data-save-acc="${x.id}">Guardar cambios</button>
      <button class="small ghost" data-toggle="${x.id}">${x.active ? "Archivar" : "Reactivar"}</button>
      <button class="small ghost danger" data-del-acc="${x.id}">Eliminar</button></div></div>`).join("");
  const mv = await api("/api/movements");
  $("#mv-table").innerHTML = mv.length ? "<tr><th>Cuenta</th><th>Fecha</th><th>Importe</th><th>Nota</th><th></th></tr>" + mv.map(m =>
    `<tr data-mv="${m.id}"><td>${esc(m.account)}</td><td><input data-f="date" type="date" value="${m.date}"></td><td><input data-f="amount" type="number" step="any" value="${m.amount}"></td><td><input data-f="note" value="${esc(m.note)}"></td><td><button class="small" data-mvsave="${m.id}">Guardar</button> <button class="small ghost" data-mvdel="${m.id}">✕</button></td></tr>`).join("") : "";
}
$("#inst-table").addEventListener("click", async e => {
  const c = e.target.dataset.save; if (!c) return;
  const g = f => $(`input[data-c="${c}"][data-f="${f}"]`).value;
  await api("/api/instruments/" + c, put({ contract_size: g("contract_size"), tick_size: g("tick_size") }));
  await loadSettings(); refresh();
});
$("#acc-add").onclick = async () => {
  try {
    await api("/api/accounts", post({ name: $("#acc-name").value, kind: $("#acc-kind").value, broker: $("#acc-broker").value, starting_balance: $("#acc-start").value, money_scale: $("#acc-unit").value, server_mode: $("#acc-smode").value, server_offset: $("#acc-soff").value }));
    $("#acc-name").value = ""; $("#acc-msg").textContent = ""; await loadSettings();
  } catch (err) { $("#acc-msg").textContent = err.message; }
};
const fields = el => Object.fromEntries([...el.querySelectorAll("[data-f]")].map(i => [i.dataset.f, i.value]));
$("#acc-table").addEventListener("click", async e => {
  const del = e.target.dataset.delAcc;
  if (del) {
    const x = accounts.find(a => a.id == del);
    if (!confirm(`¿Eliminar la cuenta "${x.name}"? No se puede deshacer.`)) return;
    let r = await fetch("/api/accounts/" + del, { method: "DELETE" }), j = await r.json();
    if (r.status === 409) {
      if (!confirm(`La cuenta tiene ${j.n_trades} operaciones. Se borrarán también sus operaciones, capturas, movimientos e importaciones.\n\n¿Eliminar todo de todos modos? (Para conservar los datos usa Archivar.)`)) return;
      r = await fetch("/api/accounts/" + del + "?force=1", { method: "DELETE" }); j = await r.json();
    }
    $("#acc-msg").textContent = r.ok ? "Cuenta eliminada" : j.error;
    await loadSettings(); refresh();
    return;
  }
  const id = e.target.dataset.saveAcc || e.target.dataset.toggle; if (!id) return;
  const x = accounts.find(a => a.id == id), box = e.target.closest("[data-acc]");
  const body = e.target.dataset.saveAcc ? { ...x, ...fields(box) } : { ...x, active: x.active ? 0 : 1 };
  try {
    await api("/api/accounts/" + id, put(body));
    $("#acc-msg").textContent = e.target.dataset.saveAcc ? "Cuenta guardada" : "";
    await loadSettings(); refresh();
  } catch (err) { $("#acc-msg").textContent = err.message; }
});
$("#mv-add").onclick = async () => {
  if (!$("#mv-date").value || !$("#mv-amount").value) return;
  await api("/api/movements", post({ account_id: $("#mv-acc").value, date: $("#mv-date").value, amount: $("#mv-amount").value, note: $("#mv-note").value }));
  $("#mv-amount").value = $("#mv-note").value = ""; await loadSettings(); refresh();
};
$("#mv-table").addEventListener("click", async e => {
  if (e.target.dataset.mvsave) {
    await api("/api/movements/" + e.target.dataset.mvsave, put(fields(e.target.closest("[data-mv]"))));
    await loadSettings(); refresh(); return;
  }
  if (e.target.dataset.mvdel) { await api("/api/movements/" + e.target.dataset.mvdel, { method: "DELETE" }); await loadSettings(); refresh(); }
});
$("#dataset-link").addEventListener("click", e => { e.currentTarget.href = "/api/export/dataset.csv?" + qs(); });
$("#backup").onclick = async () => { const r = await api("/api/backup", { method: "POST" }); $("#data-msg").textContent = "Copia creada: " + r.path; };

$("#quit").onclick = async () => {
  if (!confirm("¿Cerrar el diario? Tus datos quedan guardados.")) return;
  try { await api("/api/shutdown", { method: "POST" }); } catch (e) { /* el servidor se cierra */ }
  document.body.innerHTML = '<p style="padding:40px;font:16px system-ui">Diario cerrado. Puedes cerrar esta pestaña.</p>';
};
api("/api/version").then(v => ($("#data-where").textContent = `Versión ${v.version} · datos en ${v.data_dir}`));

// ---------- track record ----------
function lineChart(el, pts, key, fmt) {
  if (pts.length < 2) { el.innerHTML = '<p class="muted">Se necesitan al menos 2 operaciones cerradas.</p>'; return; }
  const W = 900, H = 220, L = 60, B = 24, T = 10, R = 10;
  const ys = pts.map(p => p[key]).concat(0), min = Math.min(...ys), max = Math.max(...ys), span = max - min || 1;
  const x = i => L + i / (pts.length - 1) * (W - L - R), y = v => T + (1 - (v - min) / span) * (H - T - B);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");
  const color = pts[pts.length - 1][key] >= 0 ? "var(--pos)" : "var(--neg)";
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Curva TWR">
    <line x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}" stroke="var(--line)" stroke-dasharray="4 4"/>
    <text x="${L - 6}" y="${y(max) + 4}" text-anchor="end">${fmt(max)}</text><text x="${L - 6}" y="${y(min) + 4}" text-anchor="end">${fmt(min)}</text>
    <text x="${L}" y="${H - 6}">${pts[0].t.slice(0, 10)}</text><text x="${W - R}" y="${H - 6}" text-anchor="end">${pts[pts.length - 1].t.slice(0, 10)}</text>
    <path d="${path}" fill="none" stroke="${color}" stroke-width="2"/></svg>`;
}
async function loadTrackRecord() {
  const t = await api("/api/trackrecord?" + (qs().match(/account=\d+/) || [""])[0]);
  $("#tr-kpis").innerHTML = [
    kpi("Periodo", t.period_start ? `${t.period_start} → ${t.period_end || "—"}` : "—"),
    kpi("Retorno TWR", `${t.twr_pct} %`, cls(t.twr_pct)),
    kpi("Ganancia absoluta", t.abs_gain_pct == null ? "—" : `${t.abs_gain_pct} %`, cls(t.abs_gain_pct)),
    kpi("Beneficio (USD)", money(t.profit_usd), cls(t.profit_usd)),
    kpi("Capital aportado (USD)", money(t.net_deposits_usd)),
    kpi("Máx. drawdown", `${t.max_drawdown_pct} %`, t.max_drawdown_pct ? "neg" : ""),
    kpi("Operaciones", `${t.n_trades}${t.n_open ? ` (+${t.n_open} abiertas)` : ""}`),
    kpi("Importadas del bróker", t.imported_pct == null ? "—" : `${t.imported_pct} %`),
  ].join("");
  lineChart($("#tr-chart"), t.twr_curve, "twr", v => v.toFixed(1) + " %");
  $("#tr-imports").innerHTML = t.imports.length
    ? "<tr><th>Fecha</th><th>Cuenta</th><th>Archivo</th><th class=n>Leídas</th><th class=n>Nuevas</th><th>SHA-256</th></tr>" + t.imports.map(i =>
      `<tr><td>${i.imported_at}</td><td>${esc(i.account)}</td><td>${esc(i.filename)}</td><td class=n>${i.n_read}</td><td class=n>${i.n_added}</td><td title="${i.sha256}"><code>${i.sha256.slice(0, 16)}…</code></td></tr>`).join("")
    : '<tr><td class="muted">Todavía no hay importaciones.</td></tr>';
}

async function refresh() { await Promise.all([loadSummary(), loadTrades(), loadPeriods(), loadAnalysis(), loadTrackRecord()]); }
loadSettings().then(refresh);
