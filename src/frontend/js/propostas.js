// Propostas e personalizações — entrega do subagente propostas, integrada ao contrato da API.
(() => {
  "use strict";
  const F=window.FT,$=(id)=>document.getElementById(id),e=F.escape,API="/api/proposals";
  let customers=[],vehicles=[],proposals=[],editing=null,selected=null,base=0,lastVehicle="",busy=false;
  const vehicleName=(v)=>[v.brand,v.model,v.plate].filter(Boolean).join(" · ");
  const expired=(p)=>p.expired ?? (p.valid_until < F.today());
  const price=(v)=>Math.round(Number(v?.price||0)*100);
  const className=(status)=>status==="Aprovada"?"green":status==="Cancelada"?"red":"";
  function options(keep=null){
    $("customerId").innerHTML='<option value="">Selecione a empresa</option>'+customers.filter(c=>c.active||c.id===keep?.customer_id).map(c=>`<option value="${e(c.id)}">${e(c.legal_name)}${c.active?"":" (inativa)"}</option>`).join("");
    $("vehicleId").innerHTML='<option value="">Selecione o caminhão</option>'+vehicles.filter(v=>v.status==="Disponível"||v.id===keep?.vehicle_id).map(v=>`<option value="${e(v.id)}">${e(vehicleName(v))} · ${F.money(price(v))}${v.status==="Disponível"?"":` (${e(v.status)})`}</option>`).join("");
  }
  async function refs(){[customers,vehicles]=await Promise.all([F.request("/api/customers"),F.request("/api/vehicles")]);}
  async function load(){proposals=await F.request(API);render();}
  function render(){
    $("statTotal").textContent=proposals.length;$("statDraft").textContent=proposals.filter(p=>p.status==="Em elaboração").length;$("statSent").textContent=proposals.filter(p=>p.status==="Enviada").length;$("statApproved").textContent=proposals.filter(p=>p.status==="Aprovada").length;
    const q=$("searchProposals").value.toLocaleLowerCase("pt-BR"),status=$("filterStatus").value,val=$("filterValidity").value;
    const rows=proposals.filter(p=>(!status||p.status===status)&&(!val||(val==="expired"?expired(p):!expired(p)))&&[p.number,p.customer.legal_name,p.customer.cnpj,vehicleName(p.vehicle)].join(" ").toLocaleLowerCase("pt-BR").includes(q));
    $("proposalRows").innerHTML=rows.map(p=>`<tr><td class="proposal-table-name"><b>${e(p.number)}</b><small>${e(vehicleName(p.vehicle))}</small><small>${e(F.date(p.valid_until))}${expired(p)?" · Vencida":""}</small></td><td class="proposal-table-name">${e(p.customer.legal_name)}</td><td><span class="badge ${className(p.status)}">${e(p.status)}</span></td><td>${F.money(p.total_cents)}</td><td><button class="secondary" data-open="${e(p.id)}">Detalhes</button></td></tr>`).join("");
    $("proposalListStatus").textContent=rows.length?`${rows.length} proposta(s) exibida(s).`:"Nenhuma proposta encontrada.";
  }
  function decimalCents(value){const m=/^(\d+)(?:\.(\d{1,2}))?$/.exec(String(value));return m?Number(m[1])*100+Number((m[2]||"").padEnd(2,"0")):0;}
  function totals(){let extra=0;$("proposalItems").querySelectorAll(".proposal-item").forEach(r=>extra+=Number(r.querySelector('[name="quantity"]').value||0)*decimalCents(r.querySelector('[name="unit_price"]').value));$("basePriceDisplay").textContent=F.money(base);$("itemsTotalDisplay").textContent=F.money(extra);$("proposalTotalDisplay").textContent=F.money(base+extra);}
  function addItem(item={}){
    if($("proposalItems").children.length>=30){F.notify("O limite é de 30 itens.",true);return;}
    const r=document.createElement("div");r.className="proposal-item";
    r.innerHTML=`<label class="field"><span class="hint">Descrição</span><input name="description" required minlength="2" maxlength="160" aria-label="Descrição da personalização" value="${e(item.description||"")}"></label><label class="field"><span class="hint">Qtd.</span><input name="quantity" type="number" required min="1" max="100" step="1" aria-label="Quantidade" value="${e(item.quantity||1)}"></label><label class="field"><span class="hint">Unitário (R$)</span><input name="unit_price" type="number" required min="0" max="999999.99" step="0.01" aria-label="Preço unitário" value="${((item.unit_price_cents||0)/100).toFixed(2)}"></label><button class="danger" type="button" aria-label="Remover item">×</button>`;
    r.querySelector("button").onclick=()=>{r.remove();totals();};r.addEventListener("input",totals);$("proposalItems").appendChild(r);totals();
  }
  function reset(){editing=null;base=0;lastVehicle="";$("proposalForm").reset();options();$("proposalItems").replaceChildren();$("validUntil").min=F.today();$("validUntil").value=F.today();$("formTitle").textContent="Nova proposta";$("saveProposalButton").textContent="Salvar rascunho";$("cancelEditButton").hidden=true;$("proposalError").hidden=true;totals();}
  function edit(p){editing=p;options(p);$("customerId").value=p.customer_id;$("vehicleId").value=p.vehicle_id;lastVehicle=p.vehicle_id;base=p.base_price_cents;$("validUntil").value=p.valid_until;$("proposalNotes").value=p.notes;$("proposalItems").replaceChildren();p.items.forEach(addItem);$("formTitle").textContent=`Editar ${p.number}`;$("saveProposalButton").textContent="Salvar alterações";$("cancelEditButton").hidden=false;totals();$("proposalEditor").scrollIntoView({behavior:"smooth"});}
  async function open(id){selected=await F.request(`${API}/${encodeURIComponent(id)}`);detail(selected);history.replaceState({},"",`/propostas.html?id=${encodeURIComponent(id)}`);}
  const kv=(label,value)=>`<div><dt>${e(label)}</dt><dd>${e(value||"—")}</dd></div>`;
  function detail(p){
    const canAct=p.customer_active&&p.vehicle_status==="Disponível"&&!expired(p),isDraft=p.status==="Em elaboração",block=p.payments.some(x=>["Pendente","Aprovado"].includes(x.status)),sent=p.events.some(ev=>ev.to_status==="Enviada");
    const action=(a,label,style="secondary")=>`<button class="${style}" data-action="${a}">${label}</button>`;
    $("proposalDetail").innerHTML=`<div class="proposal-detail-head"><div><div class="eyebrow">FasTruck · Proposta comercial</div><h2>${e(p.number)}</h2><span class="badge ${className(p.status)}">${e(p.status)}</span>${expired(p)?'<span class="badge red">Vencida</span>':""}</div><div class="actions no-print">${isDraft?action("edit","Editar")+action("delete","Excluir","danger"):""}${isDraft&&canAct?action("send","Registrar envio","primary"):""}${p.status==="Enviada"&&canAct?action("approve","Registrar aprovação","primary"):""}${p.status!=="Cancelada"&&!block?action("cancel","Cancelar","danger"):""}${p.eligible_for_payment?`<a class="primary" href="/pagamentos.html?proposal_id=${encodeURIComponent(p.id)}">Simular pagamento</a>`:""}${sent?action("print","Imprimir"):""}${action("close","Fechar")}</div></div>
      <p class="hint">Proposta não garante reserva. Envio e aprovação são registros manuais do operador.</p>${!canAct&&p.status!=="Cancelada"?'<p class="notice warning no-print">Ações comerciais dependem de validade vigente, empresa ativa e caminhão Disponível.</p>':""}${block?'<p class="notice warning no-print">Cancelamento bloqueado por pagamento pendente/aprovado.</p>':""}
      <dl class="detail-grid">${kv("Empresa",p.customer.legal_name)}${kv("CNPJ",F.cnpj(p.customer.cnpj))}${kv("Responsável",p.customer.contact_name)}${kv("Contato",[p.customer.email,p.customer.phone].filter(Boolean).join(" · "))}${kv("Endereço",[p.customer.street,p.customer.number,p.customer.complement,p.customer.district,p.customer.city,p.customer.state,p.customer.postal_code].filter(Boolean).join(", "))}${kv("Caminhão",vehicleName(p.vehicle))}${kv("Configuração",[p.vehicle.year,p.vehicle.color,p.vehicle.body,p.vehicle.axles,p.vehicle.fuel].filter(Boolean).join(" · "))}${kv("Validade",F.date(p.valid_until))}</dl>
      <h3>Personalizações adicionais</h3><div class="table-wrap"><table class="table"><thead><tr><th>Descrição</th><th>Qtd.</th><th>Unitário</th><th>Subtotal</th></tr></thead><tbody>${p.items.length?p.items.map(i=>`<tr><td>${e(i.description)}</td><td>${i.quantity}</td><td>${F.money(i.unit_price_cents)}</td><td>${F.money(i.subtotal_cents)}</td></tr>`).join(""):'<tr><td colspan="4">Sem adicionais.</td></tr>'}</tbody></table></div>
      <div class="totals" style="margin-top:18px"><div><span>Preço-base</span><b>${F.money(p.base_price_cents)}</b></div><div><span>Adicionais</span><b>${F.money(p.total_cents-p.base_price_cents)}</b></div><div class="total"><span>Total</span><b>${F.money(p.total_cents)}</b></div></div><p class="proposal-description">${e(p.notes)}</p>
      <section class="no-print"><h3>Histórico</h3><ol class="proposal-events">${p.events.map(ev=>`<li><b>${e(ev.to_status)}</b> · ${e(F.date(ev.created_at))}${ev.reason?`<br>${e(ev.reason)}`:""}</li>`).join("")}</ol><h3>Pagamentos simulados</h3>${p.payments.length?`<ul>${p.payments.map(pay=>`<li><a href="/pagamentos.html?id=${encodeURIComponent(pay.id)}">${e(pay.reference)}</a> · ${e(pay.status)} · ${F.money(pay.amount_cents)}</li>`).join("")}</ul>`:'<p class="muted">Nenhuma tentativa vinculada.</p>'}</section>`;
    $("proposalDetail").hidden=false;$("proposalDetail").scrollIntoView({behavior:"smooth"});
  }
  function askReason(){const d=$("reasonDialog");d.returnValue="";$("reasonInput").value="";d.showModal();return new Promise(resolve=>{d.addEventListener("close",()=>resolve(d.returnValue==="confirm"?$("reasonInput").value.trim():null),{once:true});});}
  async function refresh(){await Promise.all([refs(),load()]);if(selected)await open(selected.id);}
  $("proposalForm").addEventListener("submit",async(event)=>{
    event.preventDefault();if(busy||!$("proposalForm").reportValidity())return;busy=true;$("saveProposalButton").disabled=true;$("proposalError").hidden=true;
    const body={customer_id:$("customerId").value,vehicle_id:$("vehicleId").value,valid_until:$("validUntil").value,notes:$("proposalNotes").value.trim(),items:[...$("proposalItems").children].map(r=>({description:r.querySelector('[name="description"]').value.trim(),quantity:Number(r.querySelector('[name="quantity"]').value),unit_price:r.querySelector('[name="unit_price"]').value}))};
    try{const p=await F.request(editing?`${API}/${encodeURIComponent(editing.id)}`:API,{method:editing?"PUT":"POST",body});F.notify(editing?"Proposta atualizada.":"Proposta criada.");reset();await load();await open(p.id);}catch(error){$("proposalError").textContent=error.message;$("proposalError").hidden=false;F.notify(error.message,true);}finally{busy=false;$("saveProposalButton").disabled=false;}
  });
  $("proposalDetail").addEventListener("click",async(event)=>{
    const b=event.target.closest("[data-action]");if(!b||busy||!selected)return;const a=b.dataset.action;
    if(a==="close"){$("proposalDetail").hidden=true;selected=null;history.replaceState({},"","/propostas.html");return;}
    if(a==="print"){F.print();return;}if(a==="edit"){await refs();edit(selected);return;}
    busy=true;b.disabled=true;
    try{
      if(a==="delete"){if(!await F.confirm("Excluir este rascunho?"))return;await F.request(`${API}/${selected.id}`,{method:"DELETE"});selected=null;$("proposalDetail").hidden=true;history.replaceState({},"","/propostas.html");reset();await load();F.notify("Rascunho excluído.");return;}
      const target={send:"Enviada",approve:"Aprovada",cancel:"Cancelada"}[a];let reason="";
      if(a==="cancel"){reason=await askReason();if(reason===null)return;}else if(!await F.confirm(a==="send"?"Registrar envio e congelar os dados e valores desta proposta? Nenhuma mensagem será enviada automaticamente.":"Registrar aprovação desta proposta?"))return;
      await F.request(`${API}/${selected.id}/status`,{method:"POST",body:{status:target,reason}});F.notify("Status atualizado.");await refresh();
    }catch(error){F.notify(error.message,true);}finally{busy=false;b.disabled=false;}
  });
  $("vehicleId").addEventListener("change",async()=>{const next=$("vehicleId").value;if(editing&&next!==lastVehicle&&!await F.confirm("Trocar caminhão e copiar o preço atual do novo veículo? Os adicionais serão mantidos para revisão.")){$("vehicleId").value=lastVehicle;return;}lastVehicle=next;base=editing&&next===editing.vehicle_id?editing.base_price_cents:price(vehicles.find(v=>v.id===next));totals();});
  $("reasonForm").addEventListener("submit",event=>{event.preventDefault();if($("reasonForm").reportValidity()&&$("reasonInput").value.trim().length>=3)$("reasonDialog").close("confirm");});$("reasonCancel").onclick=()=>$("reasonDialog").close("cancel");
  $("newProposalButton").onclick=async()=>{try{await refs();reset();$("proposalEditor").scrollIntoView({behavior:"smooth"});}catch(error){F.notify(error.message,true);}};
  $("cancelEditButton").onclick=reset;$("addItemButton").onclick=()=>addItem();$("reloadProposals").onclick=()=>refresh().catch(error=>F.notify(error.message,true));
  $("proposalRows").addEventListener("click",event=>{const b=event.target.closest("[data-open]");if(b)open(b.dataset.open).catch(error=>F.notify(error.message,true));});["searchProposals","filterStatus","filterValidity"].forEach(id=>$(id).addEventListener("input",render));
  F.renderNav("propostas");(async()=>{try{await refs();reset();await load();const id=new URLSearchParams(location.search).get("id");if(id)await open(id);}catch(error){$("proposalListStatus").textContent=error.message;F.notify(error.message,true);}})();
})();
