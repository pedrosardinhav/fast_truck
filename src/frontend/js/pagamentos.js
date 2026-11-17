// Pagamentos simulados — entrega do subagente pagamentos, integrada à API.
(() => {
  "use strict";
  const F=window.FT,$=(id)=>document.getElementById(id),e=F.escape;
  let payments=[],proposals=[],detail=null,busy=false,target="",memoryIntent=null;
  const STORAGE="fastruck.payment.intent";
  function errorMessage(error){$("paymentError").textContent=error.message;$("paymentError").hidden=false;F.notify(error.message,true);}
  function stored(){try{return JSON.parse(sessionStorage.getItem(STORAGE)||"null")||memoryIntent;}catch(_){return memoryIntent;}}
  function saveIntent(i){memoryIntent=i;try{if(i)sessionStorage.setItem(STORAGE,JSON.stringify(i));else sessionStorage.removeItem(STORAGE);}catch(_){/* A intenção ainda permanece em memória nesta página. */}}
  const badge=(status)=>`<span class="badge ${status==="Aprovado"?"green":status==="Pendente"?"gold":status==="Recusado"?"red":"gray"}">${e(status)}</span>`;
  const eligible=(p)=>p?.eligible_for_payment===true;
  function show(view){["List","Create","Detail"].forEach(v=>$("payment"+v+"View").hidden=v!==view);$("paymentError").hidden=true;}
  function setUrl(params){const u=new URL(location.href);u.search=params;history.replaceState({},"",u);}
  async function load(){const [p,pr]=await Promise.all([F.request("/api/payments"),F.request("/api/proposals")]);payments=p.items;proposals=pr;render();}
  function render(){
    $("statTotal").textContent=payments.length;$("statPending").textContent=payments.filter(p=>p.status==="Pendente").length;$("statApproved").textContent=payments.filter(p=>p.status==="Aprovado").length;
    const q=$("paymentSearch").value.trim().toLocaleLowerCase("pt-BR"),status=$("statusFilter").value,method=$("methodFilter").value;
    const rows=payments.filter(p=>(!status||p.status===status)&&(!method||p.method===method)&&[p.reference,p.proposal_number,p.customer_name,p.cnpj,p.vehicle_plate].join(" ").toLocaleLowerCase("pt-BR").includes(q));
    $("paymentsBody").innerHTML=rows.map(p=>`<tr><td><b>${e(p.reference)}</b><small>${e(F.date(p.created_at))}</small></td><td>${e(p.proposal_number)}<small>${e(p.customer_name)}</small></td><td>${e(p.vehicle_plate)}</td><td>${e(p.method)}</td><td>${F.money(p.amount_cents)}</td><td>${badge(p.status)}</td><td><button class="secondary" data-detail="${e(p.id)}">Detalhes</button></td></tr>`).join("");$("paymentsEmpty").textContent=rows.length?`${rows.length} tentativa(s) exibida(s).`:"Nenhuma tentativa encontrada.";
  }
  function summary(){const p=proposals.find(p=>p.id===$("proposalSelect").value);$("proposalSummary").hidden=!p;$("proposalSummary").innerHTML=p?`<dl class="payment-data"><div><dt>Empresa</dt><dd>${e(p.customer.legal_name)} · ${e(F.cnpj(p.customer.cnpj))}</dd></div><div><dt>Caminhão</dt><dd>${e([p.vehicle.brand,p.vehicle.model,p.vehicle.plate].join(" · "))}</dd></div><div><dt>Total integral</dt><dd><b>${F.money(p.total_cents)}</b></dd></div><div><dt>Validade</dt><dd>${e(F.date(p.valid_until))}</dd></div></dl>`:"";}
  async function openCreate(proposalId=""){
    await load();
    const pending=stored();
    if(pending){const found=payments.find(p=>p.idempotency_key===pending.idempotency_key);if(found){saveIntent(null);F.notify("Recuperamos a tentativa já registrada.");await openDetail(found.id);return;}}
    show("Create");setUrl("?proposal_id="+encodeURIComponent(proposalId));
    $("proposalSelect").innerHTML='<option value="">Selecione uma proposta elegível</option>'+proposals.filter(eligible).map(p=>`<option value="${e(p.id)}">${e(p.number)} · ${e(p.customer.legal_name)} · ${F.money(p.total_cents)}</option>`).join("");
    $("proposalSelect").value=proposalId;$("paymentMethod").value="";summary();
    if(proposalId&&!eligible(proposals.find(p=>p.id===proposalId)))F.notify("Esta proposta não está elegível para uma nova tentativa.",true);
    if(pending&&eligible(proposals.find(p=>p.id===pending.proposal_id))){$("proposalSelect").value=pending.proposal_id;$("paymentMethod").value=pending.method;summary();F.notify("A tentativa anterior não foi confirmada. Os dados foram recuperados para repetir com segurança.");}
  }
  async function openDetail(id){
    detail=await F.request(`/api/payments/${encodeURIComponent(id)}`);show("Detail");setUrl("?id="+encodeURIComponent(id));
    const p=detail.proposal,c=p.customer_snapshot,v=p.vehicle_snapshot;
    $("detailTitle").textContent=detail.reference;
    $("paymentDetailContent").innerHTML=`<p>${badge(detail.status)} <span class="hint">Pagamento simulado — sem valor financeiro.</span></p><dl class="payment-data">${[["Proposta",p.number],["Empresa",c.legal_name],["CNPJ",F.cnpj(c.cnpj)],["Caminhão",[v.brand,v.model,v.plate].filter(Boolean).join(" · ")],["Método simulado",detail.method],["Valor integral simulado",F.money(detail.amount_cents)],["Criado em",F.date(detail.created_at)],["Resultado em",F.date(detail.result_at)],["Validade da proposta",F.date(p.valid_until)],["Motivo",detail.reason||"—"]].map(([k,val])=>`<div><dt>${e(k)}</dt><dd>${e(val)}</dd></div>`).join("")}</dl><h3>Histórico da tentativa</h3><ol class="payment-events">${detail.events.map(ev=>`<li><b>${e(ev.to_status)}</b> · ${e(F.date(ev.created_at))}${ev.reason?`<br>${e(ev.reason)}`:""}</li>`).join("")}</ol>`;
    const current=proposals.find(x=>x.id===detail.proposal_id),actions=$("paymentDetailActions");
    if(detail.status==="Pendente")actions.innerHTML='<button class="primary" data-status="Aprovado">Simular aprovação</button><button class="danger" data-status="Recusado">Simular recusa</button><button class="secondary" data-status="Cancelado">Cancelar tentativa</button>';
    else if(detail.status==="Aprovado")actions.innerHTML='<button class="primary" id="printReceipt">Imprimir comprovante da simulação</button>';
    else actions.innerHTML=eligible(current)?'<button class="primary" id="retryPayment">Nova tentativa</button>':'<p class="muted">A proposta não está elegível para outra tentativa.</p>';
    $("paymentReceipt").innerHTML=detail.status==="Aprovado"?`<h1>FasTruck · Comprovante de simulação</h1><div class="receipt-notice">SEM VALOR FINANCEIRO · PAGAMENTO SIMULADO</div>${[["Referência",detail.reference],["Proposta",p.number],["Empresa",c.legal_name],["CNPJ",F.cnpj(c.cnpj)],["Caminhão",[v.brand,v.model,v.plate].filter(Boolean).join(" · ")],["Método",detail.method],["Valor simulado",F.money(detail.amount_cents)],["Resultado","Aprovado na simulação"],["Data",F.date(detail.result_at)]].map(([k,val])=>`<p><b>${e(k)}:</b> ${e(val)}</p>`).join("")}<p>Este documento registra somente uma simulação. Não comprova cobrança, transferência, quitação ou compra.</p>`:"";
  }
  $("paymentCreateForm").addEventListener("submit",async(event)=>{
    event.preventDefault();if(busy||!$("paymentCreateForm").reportValidity())return;busy=true;$("createPaymentButton").disabled=true;
    try{
      if(!await F.confirm("Criar uma tentativa de pagamento simulado pelo valor integral da proposta?"))return;
      const proposal_id=$("proposalSelect").value,method=$("paymentMethod").value,previous=stored();
      const intent=previous?.proposal_id===proposal_id&&previous?.method===method?previous:{proposal_id,method,idempotency_key:F.makeKey()};saveIntent(intent);
      const result=await F.request("/api/payments",{method:"POST",body:intent});saveIntent(null);await load();await openDetail(result.id);F.notify("Tentativa simulada registrada.");
    }catch(error){errorMessage(error);}finally{busy=false;$("createPaymentButton").disabled=false;}
  });
  async function changeStatus(status,reason=""){
    if(busy)return;busy=true;$("paymentDetailActions").querySelectorAll("button").forEach(b=>b.disabled=true);$("confirmStatus").disabled=true;
    try{const result=await F.request(`/api/payments/${detail.id}/status`,{method:"POST",body:{status,reason}});$("statusModal").close();await load();await openDetail(result.id);F.notify("Resultado simulado registrado.");}
    catch(error){errorMessage(error);if($("statusModal").open)$("statusModal").close();try{await load();await openDetail(detail.id);errorMessage(error);}catch(_){/* Preserva aviso de falha de conexão. */}}
    finally{busy=false;$("confirmStatus").disabled=false;$("paymentDetailActions").querySelectorAll("button").forEach(b=>b.disabled=false);}
  }
  $("paymentDetailActions").addEventListener("click",async(event)=>{
    const b=event.target.closest("button");if(!b||busy)return;
    if(b.id==="printReceipt"){if(detail.status==="Aprovado")F.print();return;}
    if(b.id==="retryPayment"){saveIntent(null);await openCreate(detail.proposal_id).catch(errorMessage);return;}
    target=b.dataset.status;
    if(target==="Aprovado"){b.disabled=true;try{if(await F.confirm("Confirmar aprovação simulada? Nenhum dinheiro será movimentado."))await changeStatus(target);}finally{b.disabled=false;}return;}
    if(target){$("statusModalTitle").textContent=target==="Recusado"?"Simular recusa":"Cancelar tentativa";$("refusalReasonField").hidden=target!=="Recusado";$("cancelReasonField").hidden=target!=="Cancelado";$("refusalReason").required=target==="Recusado";$("cancelReason").required=target==="Cancelado";$("refusalReason").value="";$("cancelReason").value="";$("statusModal").showModal();}
  });
  $("statusForm").addEventListener("submit",event=>{event.preventDefault();const reason=target==="Recusado"?$("refusalReason").value:$("cancelReason").value.trim();if(reason.length<3||reason.length>500){F.notify("Informe um motivo de 3 a 500 caracteres.",true);return;}changeStatus(target,reason);});
  $("closeStatusModal").onclick=()=>$("statusModal").close();$("proposalSelect").onchange=summary;
  $("newPayment").onclick=()=>openCreate().catch(errorMessage);$("reloadPayments").onclick=()=>load().catch(errorMessage);
  document.querySelectorAll("[data-back]").forEach(b=>b.onclick=async()=>{show("List");setUrl("");await load().catch(errorMessage);});
  $("paymentsBody").addEventListener("click",event=>{const b=event.target.closest("[data-detail]");if(b)openDetail(b.dataset.detail).catch(errorMessage);});
  ["paymentSearch","statusFilter","methodFilter"].forEach(id=>$(id).addEventListener("input",render));
  F.renderNav("pagamentos");(async()=>{try{await load();const params=new URLSearchParams(location.search);if(params.get("id"))await openDetail(params.get("id"));else if(params.has("proposal_id"))await openCreate(params.get("proposal_id"));}catch(error){errorMessage(error);$("paymentsEmpty").textContent="Não foi possível carregar as tentativas.";}})();
})();
