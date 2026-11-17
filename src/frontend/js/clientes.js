// Tela de Clientes PJ — baseada na entrega do subagente clientes.
(() => {
  "use strict";
  const F = window.FT, $ = (id) => document.getElementById(id), e = F.escape;
  const form = $("customerForm"), dialog = $("customerDialog");
  const definitions = [
    ["legal_name","Razão social",160,true,2],["trade_name","Nome fantasia",160,false],
    ["contact_name","Responsável",120,true,2],["phone","Telefone com DDD",30,true,1,"tel"],
    ["email","E-mail",254,true,1,"email"],["postal_code","CEP",9,true],
    ["street","Logradouro",160,true,2],["number","Número (ou s/n)",20,true],
    ["complement","Complemento",100,false],["district","Bairro",100,true,2],
    ["city","Cidade",100,true,2],["state","UF",2,true],["notes","Observações",1000,false]
  ];
  const states = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
  $("clientFields").innerHTML = definitions.map(([key,label,max,required,min=1,type="text"]) => `<div class="field ${key === "notes" ? "full" : ""}"><label for="${key}">${label}${required?" *":""}</label>${key === "state" ? `<select id="state" required><option value="">Selecione</option>${states.map(s=>`<option>${s}</option>`).join("")}</select>` : key === "notes" ? `<textarea id="notes" maxlength="${max}"></textarea>` : `<input id="${key}" type="${type}" maxlength="${max}" minlength="${min}" ${required?"required":""}>`}</div>`).join("");
  let customers = [], editingId = null, lookupToken = "", lookupCnpj = "", generation = 0, consulting = false;
  const canonical = (value) => String(value).replace(/[.\/\-\s]/g, "").toUpperCase();
  function validateCnpj(value) {
    const s = canonical(value);
    if (!/^[A-Z0-9]{12}[0-9]{2}$/.test(s) || /^(\d)\1{13}$/.test(s)) return false;
    const values = [...s.slice(0,12)].map(c=>c.charCodeAt(0)-48);
    for (const weights of [[5,4,3,2,9,8,7,6,5,4,3,2],[6,5,4,3,2,9,8,7,6,5,4,3,2]]) { const r = values.reduce((sum,n,i)=>sum+n*weights[i],0)%11; values.push(r<2?0:11-r); }
    return s.slice(-2) === values.slice(-2).join("");
  }
  function showError(error) { $("clientError").textContent = error.message; $("clientError").hidden = false; F.notify(error.message,true); }
  function render() {
    const q = $("search").value.trim().toLocaleLowerCase("pt-BR"), cq = canonical(q), filter = $("statusFilter").value;
    const shown = customers.filter(c => (filter === "all" || (filter === "active" ? c.active : !c.active)) && (!q || [c.legal_name,c.trade_name,c.contact_name,c.cnpj].join(" ").toLocaleLowerCase("pt-BR").includes(q) || (cq && c.cnpj.includes(cq))));
    $("customerCount").textContent = customers.length; $("activeCount").textContent = customers.filter(c=>c.active).length; $("inactiveCount").textContent = customers.filter(c=>!c.active).length;
    $("emptyState").hidden = shown.length !== 0;
    $("customersBody").innerHTML = shown.map(c=>`<tr><td><b>${e(c.legal_name)}</b><small>${e(c.trade_name)}</small></td><td>${e(F.cnpj(c.cnpj))}</td><td>${e(c.contact_name)}<small>${e(c.phone)}</small></td><td><span class="badge ${c.active?"green":"gray"}">${c.active?"Ativo":"Inativo"}</span></td><td><div class="actions">${[["detail","Detalhes"],["edit","Editar"],["toggle",c.active?"Inativar":"Reativar"],["delete","Excluir"]].map(([a,l])=>`<button class="${a==="delete"?"danger":"secondary"}" data-action="${a}" data-id="${e(c.id)}">${l}</button>`).join("")}</div></td></tr>`).join("");
  }
  async function load() { try { customers = await F.request("/api/customers"); render(); $("listStatus").textContent=`${customers.length} empresa(s) cadastrada(s).`; } catch(error) { $("listStatus").textContent=error.message; F.notify(error.message,true); } }
  function openForm(customer=null) {
    generation++; editingId=customer?.id||null; lookupToken=""; lookupCnpj=""; form.reset(); $("clientError").hidden=true;
    $("formTitle").textContent=customer?"Editar empresa":"Nova empresa"; $("cnpj").value=customer?F.cnpj(customer.cnpj):"";
    $("cnpj").readOnly=Boolean(customer?.proposals?.length); $("lookupCnpj").disabled=consulting;
    for(const [key] of definitions) if(customer) $(key).value=customer[key]||"";
    $("lookupMessage").textContent=customer?.lookup_at?`Consulta: ${F.date(customer.lookup_at)} · ${customer.lookup_source} · ${customer.lookup_status || "situação não informada"}`:"Cadastro manual disponível mesmo sem internet.";
    dialog.showModal(); $("cnpj").focus();
  }
  async function details(id) {
    const c=await F.request(`/api/customers/${encodeURIComponent(id)}`);
    $("detailTitle").textContent=c.legal_name;
    const address=[c.street,c.number,c.complement,c.district,c.city,c.state,c.postal_code].filter(Boolean).join(", ");
    $("customerDetails").innerHTML=`<dl>${[["CNPJ",F.cnpj(c.cnpj)],["Nome fantasia",c.trade_name],["Responsável",c.contact_name],["Telefone / e-mail",`${c.phone} · ${c.email}`],["Endereço",address],["Situação interna",c.active?"Ativo":"Inativo"],["Última consulta",c.lookup_at?`${F.date(c.lookup_at)} · ${c.lookup_source} · ${c.lookup_status}`:"Não consultado"],["Observações",c.notes]].map(([k,v])=>`<div><dt>${e(k)}</dt><dd>${e(v||"—")}</dd></div>`).join("")}</dl>`;
    $("proposalHistory").innerHTML=c.proposals.length?`<div class="table-wrap"><table class="table"><thead><tr><th>Proposta</th><th>Status</th><th>Validade</th><th>Total</th></tr></thead><tbody>${c.proposals.map(p=>`<tr><td><a href="/propostas.html?id=${encodeURIComponent(p.id)}">${e(p.number)}</a></td><td>${e(p.status)}</td><td>${e(F.date(p.valid_until))}</td><td>${F.money(p.total_cents)}</td></tr>`).join("")}</tbody></table></div>`:'<p class="muted">Nenhuma proposta vinculada.</p>';
    $("detailDialog").showModal();
  }
  $("customersBody").addEventListener("click",async(event)=>{
    const b=event.target.closest("[data-action]"); if(!b||b.disabled)return; b.disabled=true;
    try {
      const c=customers.find(c=>c.id===b.dataset.id), url=`/api/customers/${encodeURIComponent(c.id)}`;
      if(b.dataset.action==="detail") await details(c.id);
      if(b.dataset.action==="edit") openForm(await F.request(url));
      if(b.dataset.action==="toggle" && await F.confirm(`${c.active?"Inativar":"Reativar"} ${c.legal_name}? O histórico será preservado.`)) { await F.request(url,{method:"PUT",body:{active:!c.active}}); F.notify("Situação atualizada."); await load(); }
      if(b.dataset.action==="delete" && await F.confirm(`Excluir permanentemente ${c.legal_name}? Empresas com propostas não podem ser excluídas.`)) { await F.request(url,{method:"DELETE"}); F.notify("Empresa excluída."); await load(); }
    } catch(error) { F.notify(error.message,true); } finally { b.disabled=false; }
  });
  $("lookupCnpj").addEventListener("click",async()=>{
    if(consulting)return; const value=canonical($("cnpj").value), gen=generation;
    if(!validateCnpj(value)){showError(new Error("Informe um CNPJ com formato e dígitos válidos."));return;}
    consulting=true; $("lookupCnpj").disabled=true; $("lookupMessage").textContent="Consultando CNPJ…";
    try {
      const r=await F.request(`/api/cnpj/${encodeURIComponent(value)}`);
      if(gen!==generation||!dialog.open||value!==canonical($("cnpj").value))return;
      const keys=definitions.map(([k])=>k).filter(k=>r[k]!==undefined && r[k]!=="");
      const overwrite=keys.some(k=>$(k).value.trim() && $(k).value.trim()!==String(r[k]));
      if(overwrite && !await F.confirm("Substituir os campos já preenchidos pelos dados desta consulta? Revise-os antes de salvar."))return;
      if(gen!==generation||!dialog.open||value!==canonical($("cnpj").value))return;
      keys.forEach(k=>$(k).value=r[k]); lookupToken=r.lookup_token; lookupCnpj=value;
      $("lookupMessage").textContent=`BrasilAPI · ${F.date(r.lookup_at)} · ${r.lookup_status || "situação não informada"}. Revise os dados antes de salvar.`;
      F.notify("Dados recebidos. Revise e complete o responsável antes de salvar.");
    } catch(error){if(gen===generation){$("lookupMessage").textContent=error.message;F.notify(error.message,true);}}
    finally{consulting=false;$("lookupCnpj").disabled=false;}
  });
  form.addEventListener("submit",async(event)=>{
    event.preventDefault(); if(!form.reportValidity())return;
    const payload=Object.fromEntries(definitions.map(([k])=>[k,$(k).value.trim()]));payload.cnpj=canonical($("cnpj").value);
    if(!validateCnpj(payload.cnpj)){showError(new Error("CNPJ inválido. Confira os dígitos verificadores."));return;}
    if(lookupToken&&lookupCnpj===payload.cnpj)payload.lookup_token=lookupToken;
    $("saveCustomer").disabled=true; $("clientError").hidden=true;
    try{await F.request(editingId?`/api/customers/${encodeURIComponent(editingId)}`:"/api/customers",{method:editingId?"PUT":"POST",body:payload});dialog.close();generation++;F.notify("Empresa salva.");await load();}catch(error){showError(error);}finally{$("saveCustomer").disabled=false;}
  });
  $("cnpj").addEventListener("input",()=>{if(lookupCnpj&&lookupCnpj!==canonical($("cnpj").value)){lookupToken="";lookupCnpj="";$("lookupMessage").textContent="CNPJ alterado. Faça nova consulta ou continue manualmente.";}});
  $("newCustomer").addEventListener("click",()=>openForm()); $("reloadCustomers").addEventListener("click",load);
  ["closeForm","cancelForm"].forEach(id=>$(id).addEventListener("click",()=>{dialog.close();generation++;}));
  dialog.addEventListener("cancel",()=>generation++); $("closeDetails").addEventListener("click",()=>$("detailDialog").close());
  $("search").addEventListener("input",render); $("statusFilter").addEventListener("change",render);
  F.renderNav("clientes");load();
})();
