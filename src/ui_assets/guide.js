const content = document.getElementById("guide-content");
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

function inlineMarkdown(value) {
  let html = escapeHtml(value);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\[([^\]]+)\]\(([^\s)]+)\)/g, (_, label, href) => {
    const local = !/^[a-z][a-z0-9+.-]*:/i.test(href) && href.toLowerCase().endsWith(".md");
    const target = local ? `/document.html?path=${encodeURIComponent(href)}` : href;
    return `<a href="${target}" target="_blank" rel="noopener">${label}</a>`;
  });
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return html;
}

function renderMarkdown(markdown) {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const output = [];
  let paragraph = [], list = [], table = [];
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
  const path = new URLSearchParams(window.location.search).get("path");
  try {
    if (!path) {
      const response = await fetch("/api/docs");
      if (!response.ok) throw new Error("I documenti non sono disponibili.");
      const documents = await response.json();
      content.innerHTML = `<ul class="document-list">${documents.map(doc => `<li><a href="/document.html?path=${encodeURIComponent(doc.path)}" target="_blank" rel="noopener">${escapeHtml(doc.name)}</a></li>`).join("")}</ul>`;
      return;
    }
    const response = await fetch(`/api/doc?path=${encodeURIComponent(path)}`);
    if (!response.ok) throw new Error("Documento non disponibile.");
    const doc = await response.json();
    document.title = `Fantastat — ${doc.name}`;
    document.getElementById("document-title").textContent = doc.name;
    content.innerHTML = doc.name.toLowerCase().endsWith(".md") ? renderMarkdown(doc.content) : `<pre>${escapeHtml(doc.content)}</pre>`;
  } catch (error) { content.innerHTML = `<p class="unavailable">${escapeHtml(error.message)}</p>`; }
}
start();
