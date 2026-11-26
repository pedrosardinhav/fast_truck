(() => {
  "use strict";
  const F = window.FT, e = F.escape, $ = (id) => document.getElementById(id);
  let orders = [], selected = null, refreshTimer = null;
  F.renderNav("pedidos");

  const statusClass = (status) => {
    const value = String(status || "").toLocaleLowerCase("pt-BR");
    if (value.includes("aprovado")) return "green";
    if (value.includes("cancelado") || value.includes("recusado")) return "red";
    if (value.includes("aguardando") || value.includes("processando")) return "gold";
    return "";
  };
  const plural = (count) => count === 1 ? "pedido exibido" : "pedidos exibidos";
  function filteredOrders() {
    const query = $("searchOrders").value.trim().toLocaleLowerCase("pt-BR");
    return orders.filter((order) => [
      order.number, order.customer?.legal_name, order.customer?.cnpj,
      order.vehicle?.plate, order.vehicle?.brand, order.vehicle?.model
    ].join(" ").toLocaleLowerCase("pt-BR").includes(query));
  }
  function render() {
    const shown = filteredOrders();
    $("statTotal").textContent = orders.length;
    $("statPending").textContent = orders.filter((o) => o.status === "Aguardando pagamento").length;
    $("statApproved").textContent = orders.filter((o) => o.status === "Pagamento aprovado").length;
    $("statCanceled").textContent = orders.filter((o) => o.status === "Cancelado").length;
    $("orderRows").innerHTML = shown.map((order) => `<tr>
      <td><b>${e(order.number)}</b><small>${e(F.date(order.created_at))}</small></td>
      <td>${e(order.customer?.legal_name || "—")}<small>${e(F.cnpj(order.customer?.cnpj))}</small></td>
      <td>${e([order.vehicle?.brand, order.vehicle?.model].filter(Boolean).join(" ") || "—")}<small>${e(order.vehicle?.plate || "—")}</small></td>
      <td><span class="badge ${statusClass(order.status)}">${e(order.status)}</span></td>
      <td><b>${F.money(order.total_cents)}</b></td>
      <td><button class="secondary" type="button" data-order="${e(order.id)}">Detalhes</button></td>
    </tr>`).join("");
    $("ordersEmpty").hidden = shown.length !== 0;
    $("orderStatus").textContent = `${shown.length} ${plural(shown.length)}`;
  }
  function detail(id) {
    selected = id;
    const order = orders.find((item) => String(item.id) === String(id));
    if (!order) { $("orderDetail").hidden = true; return; }
    const customer = order.customer || {}, vehicle = order.vehicle || {};
    const items = order.items || [], payments = order.payments || [];
    const paymentMarkup = payments.length ? `<ul class="payment-list">${payments.map((payment) => `<li>
      <div class="payment-row"><div><b>${e(payment.method || "Pagamento")}</b><div class="payment-meta">${e(F.date(payment.created_at))} · ${e(payment.reference || payment.id || "—")}</div></div><div><span class="badge ${statusClass(payment.status || payment.result)}">${e(payment.status || payment.result || "Pendente")}</span><div class="payment-meta">${F.money(payment.amount_cents || order.total_cents)}</div></div></div>
      ${payment.reason ? `<div class="payment-meta">${e(payment.reason)}</div>` : ""}
    </li>`).join("")}</ul>` : '<p class="muted">Nenhum pagamento registrado.</p>';
    $("orderDetail").innerHTML = `
      <div class="order-detail-head">
        <div><div class="eyebrow">Detalhes do pedido</div><h2>${e(order.number || order.id)}</h2><span class="badge ${statusClass(order.status)}">${e(order.status)}</span></div>
        <div class="order-detail-total"><small class="muted">Total do pedido</small><strong>${F.money(order.total_cents)}</strong><small class="muted">${e(F.date(order.created_at))}</small></div>
      </div>
      <div class="order-detail-grid">
        <div class="order-section">
          <h3>Compra</h3>
          <div class="order-info">
            <div class="info-card"><small>Empresa</small><strong>${e(customer.legal_name || "—")}</strong><span>${e(F.cnpj(customer.cnpj))}</span></div>
            <div class="info-card"><small>Responsável</small><strong>${e(customer.contact_name || "—")}</strong><span>${e(customer.email || "")}</span></div>
            <div class="info-card"><small>Caminhão</small><strong>${e([vehicle.brand, vehicle.model].filter(Boolean).join(" ") || "—")}</strong><span>${e(vehicle.plate || "—")}</span></div>
            <div class="info-card"><small>Retirada</small><strong>${e(order.pickup_location || "Loja FasTruck")}</strong>${order.reservation_expires_at && order.status === "Aguardando pagamento" ? `<span>Reserva até ${e(F.date(order.reservation_expires_at))}</span>` : ""}</div>
          </div>
          <h3 style="margin-top:22px">Itens e personalizações</h3>
          ${items.length ? `<ul class="item-list">${items.map((item) => `<li><div class="item-row"><span>${e(item.quantity)} × ${e(item.description)}</span><b>${F.money(item.subtotal_cents)}</b></div></li>`).join("")}</ul>` : '<p class="muted">Sem itens adicionais.</p>'}
          ${order.notes ? `<div class="order-notes"><b>Observações</b><br>${e(order.notes)}</div>` : ""}
          ${order.cancel_reason ? `<div class="order-notes"><b>Motivo do cancelamento</b><br>${e(order.cancel_reason)}</div>` : ""}
        </div>
        <div class="order-section"><h3>Pagamentos</h3>${paymentMarkup}</div>
      </div>`;
    $("orderDetail").hidden = false;
  }
  async function load({ quiet = false } = {}) {
    if (!quiet) $("refreshOrders").disabled = true;
    try {
      orders = await F.request("/api/shop/admin/orders");
      render();
      if (selected) detail(selected);
    } catch (error) {
      $("orderStatus").textContent = "Não foi possível carregar";
      if (!quiet) F.notify(error.message, true);
    } finally {
      $("refreshOrders").disabled = false;
    }
  }
  $("searchOrders").addEventListener("input", render);
  $("refreshOrders").addEventListener("click", () => load());
  $("orderRows").addEventListener("click", (event) => {
    const button = event.target.closest("[data-order]");
    if (!button) return;
    detail(button.dataset.order);
    $("orderDetail").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  load();
  refreshTimer = setInterval(() => load({ quiet: true }), 5000);
  window.addEventListener("pagehide", () => clearInterval(refreshTimer), { once: true });
})();
