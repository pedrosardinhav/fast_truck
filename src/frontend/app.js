(() => {
  const $ = (id) => document.getElementById(id);
  const form = $("truckForm");
  const rows = $("truckRows");
  let trucks = [];
  let editId = null;
  let deleteId = null;
  let toastTimer;

  async function request(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Não foi possível concluir a operação.");
    return result;
  }

  const money = (value) => Number(value || 0).toLocaleString("pt-BR", {
    style: "currency", currency: "BRL", maximumFractionDigits: 0,
  });
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
  const truckIcon = '<svg viewBox="0 0 42 30" fill="none" aria-hidden="true"><path d="M2 4h24v17H2zM26 10h8l7 7v4H26z" fill="currentColor" opacity=".12"/><path d="M2 4h24v17H2zM26 10h8l7 7v4H26z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="10" cy="23" r="3" fill="white" stroke="currentColor" stroke-width="1.8"/><circle cx="33" cy="23" r="3" fill="white" stroke="currentColor" stroke-width="1.8"/><path d="M29 11v6h9" stroke="currentColor" stroke-width="1.5"/></svg>';

  function notify(message) {
    const toast = $("toast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 3000);
  }

  function render() {
    const query = $("search").value.trim().toLocaleLowerCase("pt-BR");
    const filter = $("filter").value;
    const shown = trucks.filter((truck) => (
      (filter === "todos" || truck.status === filter)
      && [truck.plate, truck.brand, truck.model].some((value) => (
        String(value || "").toLocaleLowerCase("pt-BR").includes(query)
      ))
    ));

    rows.innerHTML = shown.map((truck) => `
      <tr>
        <td><div class="truck-name"><span class="truck-thumb">${truckIcon}</span><span><b>${escape(truck.brand)}</b><small>${escape(truck.model)} · ${escape(truck.color)}</small></span></div></td>
        <td class="plate">${escape(truck.plate)}</td>
        <td>${escape(truck.year)}</td>
        <td>${truck.customized === "sim" ? '<span class="status disponivel">Personalizado</span>' : '<span style="color:#929b93;font-size:10px">Original</span>'}</td>
        <td><span class="status ${truck.status.toLocaleLowerCase("pt-BR")}">${escape(truck.status)}</span></td>
        <td class="price">${money(truck.price)}</td>
        <td><div class="actions">
          <button class="icon-btn" data-edit="${escape(truck.id)}" aria-label="Editar ${escape(truck.brand)} ${escape(truck.model)}" title="Editar"><svg viewBox="0 0 24 24" fill="none"><path d="m14 5 5 5M4 20l4.2-.8L19 8.4 15.6 5 4.8 15.8 4 20Z" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
          <button class="icon-btn danger" data-delete="${escape(truck.id)}" aria-label="Excluir ${escape(truck.brand)} ${escape(truck.model)}" title="Excluir"><svg viewBox="0 0 24 24" fill="none"><path d="M4 7h16M10 11v6m4-6v6M6 7l1 13h10l1-13M9 7V4h6v3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
        </div></td>
      </tr>`).join("");

    $("empty").hidden = shown.length !== 0;
    $("count").textContent = `${trucks.length} ${trucks.length === 1 ? "veículo" : "veículos"}`;
    $("statTotal").textContent = trucks.length;
    $("statAvailable").textContent = trucks.filter((truck) => truck.status === "Disponível").length;
    $("statCustom").textContent = trucks.filter((truck) => truck.customized === "sim").length;
    $("statValue").textContent = money(trucks.reduce((sum, truck) => sum + Number(truck.price || 0), 0));
  }

  function resetForm() {
    form.reset();
    editId = null;
    $("formHeading").textContent = "Novo caminhão";
    $("saveBtn").textContent = "Cadastrar caminhão";
    $("cancelEdit").hidden = true;
  }

  function startEdit(id) {
    const truck = trucks.find((item) => item.id === id);
    if (!truck) return;
    editId = id;
    for (const [key, value] of Object.entries(truck)) {
      const field = form.elements[key];
      if (field) field.value = value ?? "";
    }
    $("formHeading").textContent = "Editar caminhão";
    $("saveBtn").textContent = "Salvar alterações";
    $("cancelEdit").hidden = false;
    $("formPanel").scrollIntoView({ behavior: "smooth", block: "start" });
    $("plate").focus({ preventScroll: true });
  }

  function formatPlate(value) {
    const plate = value.toLocaleUpperCase("pt-BR").replace(/[^A-Z0-9]/g, "").slice(0, 7);
    return plate.length > 3 ? `${plate.slice(0, 3)}-${plate.slice(3)}` : plate;
  }

  $("plate").addEventListener("input", (event) => {
    event.target.value = formatPlate(event.target.value);
  });
  $("year").addEventListener("input", (event) => {
    event.target.value = event.target.value.replace(/[^0-9/ ]/g, "").slice(0, 9);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const data = Object.fromEntries(new FormData(form).entries());
    data.plate = formatPlate(data.plate);
    if (!/^[A-Z]{3}-[0-9][A-Z0-9][0-9]{2}$/.test(data.plate)) {
      notify("Informe uma placa válida no padrão atual ou antigo.");
      $("plate").focus();
      return;
    }
    data.price = Number(data.price);
    data.km = Number(data.km || 0);
    const duplicate = trucks.some((truck) => truck.plate === data.plate && truck.id !== editId);
    if (duplicate) {
      notify("Já existe um caminhão cadastrado com essa placa.");
      $("plate").focus();
      return;
    }

    const saveButton = $("saveBtn");
    saveButton.disabled = true;
    try {
      const saved = editId
        ? await request(`/api/vehicles/${encodeURIComponent(editId)}`, { method: "PUT", body: JSON.stringify(data) })
        : await request("/api/vehicles", { method: "POST", body: JSON.stringify(data) });
      if (editId) trucks = trucks.map((truck) => truck.id === editId ? saved : truck);
      else trucks.unshift(saved);
      render();
      const wasEditing = Boolean(editId);
      resetForm();
      notify(wasEditing ? "Caminhão atualizado com sucesso." : "Caminhão cadastrado com sucesso.");
    } catch (error) {
      notify(error.message || "Não foi possível salvar. Confira se o servidor está ativo.");
    } finally {
      saveButton.disabled = false;
    }
  });

  rows.addEventListener("click", (event) => {
    const editButton = event.target.closest("[data-edit]");
    const deleteButton = event.target.closest("[data-delete]");
    if (editButton) startEdit(editButton.dataset.edit);
    if (deleteButton) {
      deleteId = deleteButton.dataset.delete;
      $("confirmDialog").classList.add("open");
      $("keepTruck").focus();
    }
  });

  $("deleteTruck").addEventListener("click", async () => {
    if (!deleteId) return;
    const confirmButton = $("deleteTruck");
    confirmButton.disabled = true;
    try {
      await request(`/api/vehicles/${encodeURIComponent(deleteId)}`, { method: "DELETE" });
      trucks = trucks.filter((truck) => truck.id !== deleteId);
      render();
      $("confirmDialog").classList.remove("open");
      notify("Caminhão removido do cadastro.");
      deleteId = null;
    } catch (error) {
      notify(error.message || "Não foi possível excluir o caminhão.");
    } finally {
      confirmButton.disabled = false;
    }
  });

  $("keepTruck").addEventListener("click", () => $("confirmDialog").classList.remove("open"));
  $("confirmDialog").addEventListener("click", (event) => {
    if (event.target === $("confirmDialog")) $("confirmDialog").classList.remove("open");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") $("confirmDialog").classList.remove("open");
  });
  $("newTruck").addEventListener("click", () => {
    resetForm();
    $("formPanel").scrollIntoView({ behavior: "smooth", block: "start" });
    $("plate").focus({ preventScroll: true });
  });
  $("cancelEdit").addEventListener("click", resetForm);
  $("search").addEventListener("input", render);
  $("filter").addEventListener("change", render);

  request("/api/vehicles")
    .then((items) => { trucks = items; render(); })
    .catch(() => {
      render();
      $("empty").hidden = false;
      $("empty").innerHTML = "<strong>Servidor indisponível</strong><span>Inicie o servidor Python para carregar os caminhões.</span>";
      notify("Não foi possível conectar ao banco de dados local.");
    });
})();
