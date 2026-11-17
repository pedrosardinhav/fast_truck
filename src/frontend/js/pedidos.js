(() => {
  const F=window.FT, e=F.escape, $=id=>document.getElementById(id);
  let orders=[];
  F.renderNav("pedidos");
  function render(){
    const q=$("searchOrders").value.trim().toLocaleLowerCase("pt-BR");
    const shown=orders.filter(p=>[p.number,p.customer.legal_name,p.customer.cnpj,p.vehicle.plate].join(" ").toLocaleLowerCase("pt-BR").includes(q));
    $("orderRows").innerHTML=shown.map(p=>`<tr><td><b>${e(p.number)}</b><br><small>${e(F.date(p.created_at))}</small></td><td>${e(p.customer.legal_name)}<br><small>${e(F.cnpj(p.customer.cnpj))}</small></td><td>${e(p.vehicle.brand)} ${e(p.vehicle.model)}<br><small>${e(p.vehicle.plate)}</small></td><td><span class="badge">${e(p.status)}</span></td><td>${F.money(p.total_cents)}</td><td><button class="secondary" type="button" data-order="${e(p.id)}">Detalhes</button></td></tr>`).join("");
    $("orderStatus").textContent=`${shown.length} pedido(s) exibido(s).`;
  }
  function detail(id){
    const p=orders.find(p=>p.id===id); if(!p)return;
    $("orderDetail").innerHTML=`<h2>${e(p.number)}</h2><p>${e(p.customer.legal_name)} · ${e(F.cnpj(p.customer.cnpj))}</p><p>${e(p.customer.contact_name)} · ${e(p.customer.email)} · ${e(p.customer.phone)}</p><p>${e(p.vehicle.brand)} ${e(p.vehicle.model)} · ${e(p.vehicle.plate)}</p><p><b>${e(p.status)}</b> · Total: <b>${F.money(p.total_cents)}</b></p><h3>Personalizações</h3>${p.items.length?`<ul>${p.items.map(i=>`<li>${i.quantity} × ${e(i.description)} · ${F.money(i.subtotal_cents)}</li>`).join("")}</ul>`:"<p>Sem adicionais.</p>"}<p>${e(p.notes)}</p><h3>Pagamentos simulados</h3>${p.payments.length?`<ul>${p.payments.map(t=>`<li>${e(t.method)} · ${e(t.result)} · ${F.money(t.amount_cents)} · ${e(F.date(t.created_at))}</li>`).join("")}</ul>`:"<p>Nenhuma tentativa.</p>"}`;
    $("orderDetail").hidden=false;$("orderDetail").scrollIntoView({behavior:"smooth"});
  }
  async function load(){try{orders=await F.request("/api/shop/admin/orders");render();$("orderDetail").hidden=true;}catch(error){$("orderStatus").textContent=error.message;}}
  $("searchOrders").addEventListener("input",render);
  $("refreshOrders").addEventListener("click",load);
  $("orderRows").addEventListener("click",event=>{const button=event.target.closest("[data-order]");if(button)detail(button.dataset.order);});
  load();
})();
