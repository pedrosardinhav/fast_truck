(() => {
  let access;
  async function sessionAccess() {
    if (!access) access = fetch("/api/shop/session").then((r) => r.json());
    return access;
  }
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  async function request(url, options = {}) {
    let response;
    try {
      const body = options.body && typeof options.body === "object" ? JSON.stringify(options.body) : options.body;
      const method = (options.method || "GET").toUpperCase();
      const csrf = method !== "GET" ? (await sessionAccess()).csrf_token : null;
      response = await fetch(url, { ...options, body, headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}), ...(options.headers || {}) } });
    } catch (_) {
      throw new Error("Sem conexão com o servidor. Confira se o Python está iniciado e tente novamente.");
    }
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error("O servidor não retornou os dados esperados. Tente novamente."); }
    if (!response.ok) { if (response.status === 401) location.assign("/loja.html#entrar"); const error = new Error(data.error || "Não foi possível concluir a operação."); error.status = response.status; throw error; }
    return data;
  }
  function notify(message, error = false) {
    let toast = document.getElementById("ftToast");
    if (!toast) { toast = document.createElement("div"); toast.id = "ftToast"; toast.className = "toast"; toast.setAttribute("role", "status"); toast.setAttribute("aria-live", "polite"); document.body.appendChild(toast); }
    toast.textContent = message; toast.classList.toggle("error", error); toast.classList.add("show");
    clearTimeout(notify.timer); notify.timer = setTimeout(() => toast.classList.remove("show"), error ? 8000 : 4500);
  }
  async function confirmAction(message) {
    const old = document.activeElement;
    const dialog = document.createElement("dialog"); dialog.className = "ft-confirm";
    dialog.setAttribute("aria-label", "Confirmar ação");
    const title = document.createElement("h2"); title.textContent = "Confirmar ação";
    const text = document.createElement("p"); text.textContent = message;
    const buttons = document.createElement("div"); buttons.className = "form-actions";
    const cancel = document.createElement("button"); cancel.type = "button"; cancel.className = "secondary"; cancel.textContent = "Cancelar";
    const accept = document.createElement("button"); accept.type = "button"; accept.className = "primary"; accept.textContent = "Confirmar";
    buttons.append(cancel, accept); dialog.append(title, text, buttons); document.body.appendChild(dialog);
    return new Promise((resolve) => {
      let chosen = false;
      accept.addEventListener("click", () => { chosen = true; dialog.close(); });
      cancel.addEventListener("click", () => dialog.close());
      dialog.addEventListener("click", (event) => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
      dialog.addEventListener("close", () => { dialog.remove(); old?.focus(); resolve(chosen); }, { once: true });
      dialog.showModal(); cancel.focus();
    });
  }
  function renderNav(active) {
    const nav = document.getElementById("moduleNav"); if (!nav) return;
    nav.classList.add("module-nav"); nav.setAttribute("aria-label", "Módulos FasTruck");
    nav.innerHTML = [["veiculos", "/admin", "Veículos"], ["clientes", "/clientes.html", "Clientes PJ"], ["pedidos", "/pedidos.html", "Pedidos da loja"], ["loja", "/", "Ver loja"]].map(([key, url, label]) => `<a href="${url}" ${key === active ? 'class="active" aria-current="page"' : ""}>${label}</a>`).join("") + '<button class="secondary" type="button" id="adminLogout">Sair</button>';
    document.getElementById("adminLogout").addEventListener("click", async () => {
      try { await request("/api/shop/logout", { method: "POST", body: {} }); location.assign("/"); }
      catch (error) { notify(error.message, true); }
    });
  }
  const money = (cents) => (Number(cents || 0) / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const date = (value) => {
    if (!value) return "—";
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value.split("-").reverse().join("/");
    const d = new Date(value); return Number.isNaN(d.valueOf()) ? "—" : d.toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });
  };
  const cnpj = (value) => {
    const v = String(value || "").replace(/[^A-Za-z0-9]/g, "").toUpperCase();
    return v.length === 14 ? `${v.slice(0, 2)}.${v.slice(2, 5)}.${v.slice(5, 8)}/${v.slice(8, 12)}-${v.slice(12)}` : v;
  };
  function makeKey() {
    if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16)); bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, (v) => v.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
  }
  function today() {
    const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  }
  window.FT = { request, escape, money, date, today, notify, confirm: confirmAction, renderNav, cnpj, makeKey, print: () => window.print() };
})();
