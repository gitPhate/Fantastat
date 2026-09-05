const content = document.getElementById("guide-content");
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const back = document.getElementById("back");

back.addEventListener("click", () => {
  if (window.history.length > 1) window.history.back();
  else window.location.href = back.dataset.fallback || "/index.html";
});

marked.use({
  walkTokens(token) {
    if (token.type !== "link") return;
    const href = token.href || "";
    const local = !/^[a-z][a-z0-9+.-]*:/i.test(href) && href.toLowerCase().endsWith(".md");
    if (local) token.href = `/document.html?path=${encodeURIComponent(href)}`;
  }
});

async function start() {
  const path = new URLSearchParams(window.location.search).get("path");
  try {
    if (!path) {
      const response = await fetch("/api/docs");
      if (!response.ok) throw new Error("I documenti non sono disponibili.");
      const documents = await response.json();
      content.innerHTML = `<ul class="document-list">${documents.map(doc => `<li><a href="/document.html?path=${encodeURIComponent(doc.path)}">${escapeHtml(doc.name)}</a></li>`).join("")}</ul>`;
      return;
    }
    const response = await fetch(`/api/doc?path=${encodeURIComponent(path)}`);
    if (!response.ok) throw new Error("Documento non disponibile.");
    const doc = await response.json();
    document.title = `Fantastat — ${doc.name}`;
    document.getElementById("document-title").textContent = doc.name;
    content.innerHTML = doc.name.toLowerCase().endsWith(".md") ? marked.parse(doc.content) : `<pre>${escapeHtml(doc.content)}</pre>`;
  } catch (error) { content.innerHTML = `<p class="unavailable">${escapeHtml(error.message)}</p>`; }
}
start();
