const content = document.getElementById("guide-content");
const season = new URLSearchParams(window.location.search).get("season");
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

function inlineMarkdown(value) {
  let html = escapeHtml(value);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\[([^\]]+)\]\(([^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return html;
}

function renderMarkdown(markdown) {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const output = [];
  let paragraph = [];
  let list = [];
  let table = [];
  const flushParagraph = () => { if (paragraph.length) { output.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`); paragraph = []; } };
  const flushList = () => { if (list.length) { output.push(`<ul>${list.map(item => `<li>${inlineMarkdown(item)}</li>`).join("")}</ul>`); list = []; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter(row => !/^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$/.test(row));
    if (rows.length) {
      const cells = row => row.replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => inlineMarkdown(cell.trim()));
      output.push(`<table><thead><tr>${cells(rows[0]).map(cell => `<th>${cell}</th>`).join("")}</tr></thead><tbody>${rows.slice(1).map(row => `<tr>${cells(row).map(cell => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>`);
    }
    table = [];
  };
  for (const line of lines) {
    if (/^\s*\|.*\|\s*$/.test(line)) { flushParagraph(); flushList(); table.push(line); continue; }
    flushTable();
    if (!line.trim()) { flushParagraph(); flushList(); continue; }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) { flushParagraph(); flushList(); const level = heading[1].length; output.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`); continue; }
    if (/^\s*([-*_])\s*\1\s*\1\s*$/.test(line)) { flushParagraph(); flushList(); output.push("<hr>"); continue; }
    const bullet = line.match(/^\s*[-*+]\s+(.+)$/);
    if (bullet) { flushParagraph(); list.push(bullet[1]); continue; }
    paragraph.push(line.trim());
  }
  flushTable(); flushParagraph(); flushList();
  return output.join("\n");
}

async function start() {
  if (!season) { content.innerHTML = "<p class=\"unavailable\">Stagione non specificata.</p>"; return; }
  const rawUrl = `/api/guide?season=${encodeURIComponent(season)}`;
  document.getElementById("raw-guide").href = rawUrl;
  try {
    const response = await fetch(rawUrl);
    if (!response.ok) throw new Error("Guida d'asta non disponibile per questa stagione.");
    content.innerHTML = renderMarkdown(await response.text());
  } catch (error) { content.innerHTML = `<p class="unavailable">${escapeHtml(error.message)}</p>`; }
}
start();
