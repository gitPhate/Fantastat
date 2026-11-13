/* Minimal UI i18n: English default, Italian selectable; the choice persists in localStorage. */
const I18N = {
  en: {
    "season": "Season", "documents": "Documents", "back": "Back", "document": "Document",
    "loading.docs": "Loading documents…", "loading.doc": "Loading document…",
    "docs.unavailable": "Documents are not available.", "doc.unavailable": "Document not available.",
    "title.app": "Fantastat — Offline auction", "title.docs": "Fantastat — Documents", "title.doc": "Fantastat — Document",
    "search": "Search a player", "all.roles": "All roles", "all.clubs": "All clubs", "all.tiers": "All tiers", "no.guide": "No guide",
    "col.name": "Name", "col.role": "R", "col.club": "Club", "col.quotation": "Cost", "col.fvm": "FVM", "col.points": "Pts.", "col.apps": "Apps", "col.fm": "FM", "col.tier": "Tier",
    "tip.name": "Player name", "tip.role": "Player role", "tip.club": "Current club", "tip.quotation": "Current quotation", "tip.fvm": "Average fantasy value", "tip.points": "Expected points", "tip.apps": "Predicted appearances", "tip.fm": "Predicted fantasy average", "tip.tier": "Tier in the unified auction guide",
    "players": "{n} players", "injured": "Injured", "select.player": "Select a player to see the auction evidence.",
    "n/a": "Not available", "player.id": "Fantacalcio ID",
    "h.list": "Player list", "h.ranking": "Ranking", "h.guide": "Unified guide", "h.history": "History", "h.apps": "Appearances", "h.fm": "Fantasy average",
    "f.role": "Role", "f.club": "Club", "f.quotation": "Quotation", "f.fvm": "FVM", "f.starting": "Starting index", "f.age": "Age",
    "f.rank": "Rank", "f.apps": "Predicted appearances", "f.fm": "Predicted FM", "f.points": "Expected points", "f.validation": "Validation",
    "f.tier": "Tier", "f.function": "Function", "f.notes": "Notes", "f.injuries": "Injuries", "f.risks": "Risks", "f.setpieces": "Set pieces", "f.hierarchy": "Hierarchy",
    "hist.season": "Season", "hist.club": "Club", "hist.apps": "Apps", "hist.fm": "FM", "hist.rank": "Rank", "hist.points": "Exp. pts",
    "no.history": "No historical evidence available.", "snapshot.unavailable": "Snapshot unavailable",
  },
  it: {
    "season": "Stagione", "documents": "Documenti", "back": "Indietro", "document": "Documento",
    "loading.docs": "Caricamento documenti…", "loading.doc": "Caricamento documento…",
    "docs.unavailable": "I documenti non sono disponibili.", "doc.unavailable": "Documento non disponibile.",
    "title.app": "Fantastat — Asta offline", "title.docs": "Fantastat — Documenti", "title.doc": "Fantastat — Documento",
    "search": "Cerca un giocatore", "all.roles": "Tutti i ruoli", "all.clubs": "Tutte le squadre", "all.tiers": "Tutte le fasce", "no.guide": "Senza guida",
    "col.name": "Nome", "col.role": "R", "col.club": "Squadra", "col.quotation": "Qt.", "col.fvm": "FVM", "col.points": "Pt.", "col.apps": "Pres.", "col.fm": "FM", "col.tier": "Fascia",
    "tip.name": "Nome del giocatore", "tip.role": "Ruolo del giocatore", "tip.club": "Squadra di appartenenza", "tip.quotation": "Quotazione attuale", "tip.fvm": "Fantavalore medio", "tip.points": "Punti attesi", "tip.apps": "Presenze previste", "tip.fm": "Fantamedia prevista", "tip.tier": "Fascia nella guida d'asta unificata",
    "players": "{n} giocatori", "injured": "Infortunato", "select.player": "Seleziona un giocatore per vedere le evidenze dell'asta.",
    "n/a": "Non disponibile", "player.id": "ID Fantacalcio",
    "h.list": "Listone", "h.ranking": "Ranking", "h.guide": "Guida unificata", "h.history": "Storico", "h.apps": "Presenze", "h.fm": "Fantamedia",
    "f.role": "Ruolo", "f.club": "Squadra", "f.quotation": "Quotazione", "f.fvm": "FVM", "f.starting": "Indice di titolarità", "f.age": "Età",
    "f.rank": "Rank", "f.apps": "Presenze previste", "f.fm": "FM prevista", "f.points": "Punti attesi", "f.validation": "Validazione",
    "f.tier": "Fascia", "f.function": "Funzione", "f.notes": "Note", "f.injuries": "Infortuni", "f.risks": "Rischi", "f.setpieces": "Piazzati", "f.hierarchy": "Gerarchia",
    "hist.season": "Stagione", "hist.club": "Squadra", "hist.apps": "Pv", "hist.fm": "FM", "hist.rank": "Rank", "hist.points": "Pt. attesi",
    "no.history": "Nessuna evidenza storica disponibile.", "snapshot.unavailable": "Snapshot non disponibile",
    // Server error messages are English; these are their Italian renderings.
    "The snapshot contains no selectable seasons. Run python src/build_snapshot.py after generating the season artifacts.": "Lo snapshot non contiene stagioni selezionabili. Esegui python src/build_snapshot.py dopo avere generato gli artefatti stagionali.",
    "Snapshot missing. Run: python src/build_snapshot.py": "Snapshot mancante. Esegui: python src/build_snapshot.py",
    "Snapshot incompatible. Rebuild it with: python src/build_snapshot.py": "Snapshot incompatibile. Rigeneralo con: python src/build_snapshot.py",
    "Season not found in the snapshot. Choose a season from the selector.": "Stagione non presente nello snapshot. Scegli una stagione dal selettore.",
    "The docs directory is not available.": "La directory docs non è disponibile.",
    "Invalid document.": "Documento non valido.", "Document not found.": "Documento non trovato.", "The document cannot be read.": "Il documento non può essere letto.",
    "Player not found in the selected season.": "Giocatore non presente nella stagione selezionata.",
    "Endpoint not found.": "Endpoint non trovato.", "The application is read-only.": "L'applicazione è in sola lettura.",
  },
};
let lang = localStorage.getItem("lang") === "it" ? "it" : "en";
function t(key, vars) {
  let s = I18N[lang][key] ?? I18N.en[key] ?? key;
  for (const k in vars || {}) s = s.replace(`{${k}}`, vars[k]);
  return s;
}
function tError(message) {
  const m = /^Auction guide not available for season (.+)\.$/.exec(message);
  if (m && lang === "it") return `Guida d'asta non disponibile per la stagione ${m[1]}.`;
  return t(message);
}
function applyI18n() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach(e => { e.textContent = t(e.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(e => { e.placeholder = t(e.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-i18n-tooltip]").forEach(e => { e.dataset.tooltip = t(e.dataset.i18nTooltip); });
  const title = document.querySelector("[data-i18n-title]"); if (title) document.title = t(title.dataset.i18nTitle);
  const picker = document.getElementById("lang"); if (picker) picker.value = lang;
}
function setLang(next) { lang = next; localStorage.setItem("lang", next); applyI18n(); document.dispatchEvent(new Event("langchange")); }
const langPicker = document.getElementById("lang");
if (langPicker) langPicker.addEventListener("change", () => setLang(langPicker.value));
applyI18n();
