# FasTruck — Requisitos do módulo de pagamentos simulados

Data: 16/11/2026. Status: implementado. Cobertura de aceite e limites no [relatório de validação](VALIDACAO-MODULOS.md).

Este módulo financeiro de propostas é administrativo e exige cookie de sessão válido com papel de administrador em suas páginas e APIs; as mutações também exigem token CSRF. Pagamentos de pedidos criados pela empresa na loja têm fluxo próprio na [área do cliente](REQUISITOS-AREA-CLIENTE.md), com registros separados e igualmente sem valor financeiro.

Documento integrante do [plano dos novos módulos](PLANO-NOVOS-MODULOS.md). Aplicam-se também COM-RNF01 a COM-RNF15. Depende dos módulos de clientes PJ, veículos e propostas.

## 1. Objetivo e escopo

Simular o acompanhamento de um pagamento associado a uma proposta aprovada: criar tentativa, escolher forma de pagamento, registrar resultado e consultar histórico e comprovante de simulação.

O operador escolhe o resultado. O módulo não consulta banco, não processa cartão e não movimenta dinheiro. A indicação “Pagamento simulado — sem valor financeiro” deve aparecer nas telas, no histórico financeiro e na impressão. Essa indicação pertence ao módulo financeiro e não caracteriza o cadastro de veículos como demonstração.

## 2. Dados da tentativa

| Campo | Obrigatoriedade e limite | Regra |
|---|---|---|
| ID | Automático | Identificador estável da tentativa. |
| Referência | Automática e única | Código legível, como `SIM-000001`; não é autenticação bancária. |
| Proposta | Obrigatória | Referência a uma proposta aprovada elegível. |
| Cliente e caminhão | Derivados | Dados congelados da proposta para exibição e comprovante; referências atuais usadas na elegibilidade. |
| Método | Obrigatório | Pix, Boleto ou Cartão, sempre identificados como simulados. |
| Valor | Calculado pelo servidor | Total integral da proposta em centavos; não editável. |
| Status | Automático na criação | Pendente, Aprovado, Recusado ou Cancelado. |
| Motivo de recusa | Obrigatório ao recusar | Cenário escolhido pelo operador, 3 a 500 caracteres; não é resposta de banco. |
| Motivo de cancelamento | Obrigatório ao cancelar | Texto de 3 a 500 caracteres. |
| Chave de idempotência | Obrigatória na criação | UUID gerado pela interface e reutilizado em reenvios da mesma criação; único no banco. |
| Simulado | Automático e imutável | Sempre verdadeiro. |
| Datas | Automáticas | Criação, atualização e resultado; eventos em UTC e exibição no horário de Brasília. |

Não haverá campos para número de cartão, validade, CVV, senha, chave Pix pessoal, conta ou agência. Pix não gera QR code nem código pagável; boleto não gera linha digitável ou código de barras. Cartão é apenas uma escolha de método, sem formulário de credenciais.

## 3. Estados e novas tentativas

| Estado atual | Próximos estados | Condições |
|---|---|---|
| Pendente | Aprovado | Operador confirma; proposta continua Aprovada e vigente, cliente Ativo e caminhão Disponível. |
| Pendente | Recusado | Operador seleciona cenário de recusa e confirma. |
| Pendente | Cancelado | Operador informa motivo e confirma. |
| Aprovado | Nenhum | Estado final; comprovante de simulação disponível. |
| Recusado | Nenhum | Pode criar outra tentativa se a proposta continuar elegível. |
| Cancelado | Nenhum | Pode criar outra tentativa se a proposta continuar elegível. |

Um pagamento pendente não muda automaticamente com a passagem do tempo. Se a proposta vencer ou o cliente/veículo ficar inelegível, sua aprovação é bloqueada, mas ainda pode ser recusado ou cancelado. Nenhum job, webhook ou retorno bancário muda esses estados.

## 4. Requisitos funcionais

| ID | Requisito |
|---|---|
| PAG-RF01 | Listar propostas elegíveis para iniciar pagamento simulado e aceitar acesso a partir de uma proposta. |
| PAG-RF02 | Mostrar empresa, caminhão, número, validade e total da proposta antes de criar tentativa. |
| PAG-RF03 | Permitir escolher Pix, Boleto ou Cartão simulado e criar tentativa Pendente pelo valor integral da proposta. |
| PAG-RF04 | Gerar referência e chave de idempotência e tratar repetição da criação sem duplicar registro. |
| PAG-RF05 | Simular aprovação mediante confirmação explícita e revalidação da elegibilidade. |
| PAG-RF06 | Simular recusa mediante escolha de cenário e confirmação. |
| PAG-RF07 | Cancelar tentativa pendente com confirmação e motivo. |
| PAG-RF08 | Oferecer nova tentativa após Recusado/Cancelado, preservando as anteriores. |
| PAG-RF09 | Listar e pesquisar tentativas por referência, proposta e CNPJ/razão social; filtrar por método e status. |
| PAG-RF10 | Exibir detalhes e histórico de cada tentativa com estado, data e motivo quando aplicável. |
| PAG-RF11 | Exibir e imprimir comprovante de simulação para pagamento Aprovado, com rótulo sem valor financeiro. |
| PAG-RF12 | Mostrar pagamentos vinculados na proposta e impedir mais de uma tentativa pendente ou aprovada para ela. |
| PAG-RF13 | Informar erros de estado, vínculo, validade, duplicidade, gravação e conexão sem confirmar resultado não persistido. |
| PAG-RF14 | Persistir pagamentos e eventos e disponibilizar endpoints de criação, consulta e transições; não oferecer exclusão física ou edição livre. |

## 5. Regras de negócio

| ID | Regra |
|---|---|
| PAG-RN01 | Criar e aprovar pagamento exige proposta Aprovada, vigente, cliente Ativo e veículo Disponível. Revalidar no servidor no momento de cada ação. |
| PAG-RN02 | Valor nasce do total congelado da proposta. Rejeitar valor divergente se o cliente HTTP tentar informá-lo; não aceitar cobrança parcial ou valor alterado. |
| PAG-RN03 | Somente Pix, Boleto e Cartão são métodos aceitos; todos simulados, em BRL e pelo valor integral. |
| PAG-RN04 | Nova tentativa nasce Pendente. Método, valor e proposta não podem ser editados depois; para trocar método, cancelar pendente e criar outra tentativa. |
| PAG-RN05 | Permitir no máximo uma tentativa Pendente ou Aprovada por proposta, com restrição no banco além da validação da interface. |
| PAG-RN06 | Recusado e Cancelado são finais para a tentativa, mas permitem nova tentativa se as condições comerciais ainda forem atendidas. |
| PAG-RN07 | Aprovado é final; impede outra tentativa para a proposta. Não há estorno, chargeback ou cancelamento de aprovado nesta etapa. |
| PAG-RN08 | Somente Pendente pode mudar para Aprovado, Recusado ou Cancelado. Exigir confirmação explícita, e motivo para recusa/cancelamento. |
| PAG-RN09 | Criar referência, status e evento inicial juntos. Toda mudança efetiva gera um evento imutável na mesma transação da atualização. |
| PAG-RN10 | Repetir criação com mesma chave e mesmo conteúdo retorna a tentativa existente, mesmo que seu estado já tenha mudado. Mesma chave para outra proposta/método retorna conflito. Reenvio não depende de nova elegibilidade porque não cria tentativa. |
| PAG-RN11 | Repetir a mesma transição concluída retorna o resultado atual sem duplicar evento. Tentar outro resultado em tentativa finalizada retorna conflito. |
| PAG-RN12 | Recusa/cancelamento do pendente permanece permitido se a proposta vencer, o cliente ficar inativo ou o caminhão indisponível. Isso permite encerrar uma tentativa bloqueada sem apagar histórico. |
| PAG-RN13 | Pagamentos e eventos não têm exclusão física pela interface ou API. Valores e datas anteriores não podem ser reescritos pelo operador. |
| PAG-RN14 | O comprovante utiliza dados da proposta congelada e resultado persistido; identifica referência, proposta, empresa/CNPJ, caminhão, método, valor e data do resultado. |
| PAG-RN15 | Somente Aprovado oferece comprovante; consultar ou imprimir novamente não cria pagamento/evento. Outros estados têm tela de detalhe, sem comprovante de aprovação. |
| PAG-RN16 | Todas as telas e impressões financeiras identificam a simulação. Resultado não altera status do veículo, personalizações cadastradas, preço anunciado, estoque, saldo ou indicadores de veículos. |
| PAG-RN17 | Não aceitar nem persistir dados financeiros reais nos campos da API. Uma requisição contendo campos de cartão, senha ou conta fora do contrato deve ser rejeitada. Motivos devem conter apenas informação do cenário simulado. |
| PAG-RN18 | Histórico exibe todas as tentativas sem somar recusa/cancelamento/pendência como receita. Nenhum valor é chamado de faturamento ou recebimento real. |

## 6. Requisitos não funcionais específicos

| ID | Requisito |
|---|---|
| PAG-RNF01 | Toda simulação funciona sem internet e sem SDK financeiro, segredo, token, webhook ou serviço externo. |
| PAG-RNF02 | Aprovação/recusa/cancelamento executam validação e gravação transacional; requisições concorrentes não produzem dois estados finais ou dois pagamentos ativos para a mesma proposta. |
| PAG-RNF03 | A interface desabilita a ação enquanto aguarda resposta e mantém a chave da criação em caso de falha de rede; o backend garante a idempotência mesmo quando a interface é contornada. |
| PAG-RNF04 | Ao perder a resposta após envio de resultado, permitir recarregar o detalhe para descobrir o estado persistido; não indicar aprovação antes da confirmação do servidor. |
| PAG-RNF05 | O layout de impressão contém aviso de simulação legível e omite controles da aplicação; não usa logotipos bancários ou aparência de comprovante de instituição financeira. |

## 7. Premissas

- Propostas e clientes já foram implementados e possuem identificadores persistidos. A loja mantém pedidos e pagamentos próprios, separados deste módulo administrativo.
- Operador escolhe o resultado para exercitar regras e fluxos; não existe confirmação independente do cliente ou do banco.
- Cada tentativa representa o valor integral; sem parcelamento, entrada ou divisão entre métodos.
- O estado aprovado da simulação é preservado para consulta, sem transformar o caminhão em vendido.

## 8. Restrições

- Sem gateway, credenciais financeiras reais, Pix pagável, boleto bancário, processamento de cartão ou antifraude.
- Sem juros, parcelas, vencimento próprio do pagamento, reembolso, estorno, conciliação, nota fiscal ou relatórios de receita real.
- Sem exclusão/edição de tentativas e eventos, nem mudança de método ou valor de tentativa existente.
- Sem expiração automática de pendência. A validade da proposta bloqueia aprovação, mantendo recusa/cancelamento disponíveis.
- Comprovante é uma impressão de simulação; não serve como quitação ou comprovação de compra.

## 9. Riscos e respostas

| ID | Risco | Resposta nesta etapa |
|---|---|---|
| PAG-RIS01 | Operador interpretar aprovação como cobrança real | Aviso consistente e ausência de qualquer dado/código pagável; estoque não muda. |
| PAG-RIS02 | Clique repetido criar tentativas ou resultados duplicados | Chave única de idempotência, transações, índice de unicidade e bloqueio visual temporário. |
| PAG-RIS03 | Total ser alterado no navegador | Valor calculado pelo servidor a partir da proposta aprovada. |
| PAG-RIS04 | Aprovar tentativa quando condição comercial mudou | Revalidar proposta, prazo, cliente e caminhão na aprovação. |
| PAG-RIS05 | Perder rastreabilidade de recusa ou cancelamento | Eventos imutáveis, motivos obrigatórios e ausência de exclusão. |
| PAG-RIS06 | Falha de rede deixar resultado incerto | Consultar estado persistido e permitir repetição idempotente da ação. |
| PAG-RIS07 | Capturar dados financeiros reais por engano | Não criar campos para esses dados e rejeitar propriedades fora do contrato financeiro. |

## 10. Casos de uso

Os casos abaixo são executados por um administrador autenticado. Sem sessão válida, a API responde 401; com papel insuficiente ou falha de CSRF/origem, responde 403.

### PAG-UC01 — Criar tentativa de pagamento simulado

**Ator:** operador. **Pré-condições:** proposta Aprovada e vigente, cliente Ativo, veículo Disponível e ausência de tentativa Pendente/Aprovada.

1. Abrir “Simular pagamento” na proposta ou escolher proposta elegível no módulo.
2. Conferir empresa, caminhão e total, escolher método simulado e confirmar.
3. A interface envia proposta, método e chave de idempotência.
4. O servidor verifica repetição, revalida elegibilidade e grava tentativa Pendente com referência, valor integral e evento inicial.
5. A tela mostra o resultado persistido e as ações de simulação.

**Alternativas:** vínculo inválido, valor divergente ou tentativa ativa bloqueiam criação. Mesma chave/conteúdo retorna existente; mesma chave/conteúdo diferente retorna conflito. Falha não confirma registro; reenvio usa a mesma chave.

**Pós-condição:** uma única tentativa pendente, ou consulta da já criada. **Vínculos:** PAG-RF01–04, PAG-RF12–14; PAG-RN01–05, PAG-RN09–10, PAG-RN16–17; PAG-RNF01–04; PAG-RIS01–03, PAG-RIS06–07.

### PAG-UC02 — Simular aprovação

**Ator:** operador. **Pré-condições:** tentativa Pendente e condições comerciais ainda válidas.

1. Acionar “Simular aprovação” e confirmar o resultado desejado.
2. O servidor revalida elegibilidade e grava Aprovado, data e evento na mesma transação.
3. A interface exibe aprovação simulada e libera o comprovante.

**Alternativas:** condição comercial inválida bloqueia aprovação; mantém recusa/cancelamento. Repetir aprovação concluída retorna resultado sem novo evento; resultado final diferente retorna conflito. Se perder a resposta, consultar o detalhe antes de nova ação.

**Pós-condição:** tentativa finalizada e novas tentativas bloqueadas; caminhão não muda de status. **Vínculos:** PAG-RF05, PAG-RF11–14; PAG-RN01–02, PAG-RN05, PAG-RN07–09, PAG-RN11–12, PAG-RN14–16; PAG-RNF02–05; PAG-RIS01–04, PAG-RIS06.

### PAG-UC03 — Recusar ou cancelar tentativa

**Ator:** operador. **Pré-condição:** tentativa Pendente.

**Recusa:** escolher “Simular recusa” → selecionar cenário → confirmar → gravar Recusado, motivo, data e evento.

**Cancelamento:** escolher “Cancelar tentativa” → informar motivo → confirmar → gravar Cancelado, motivo, data e evento.

**Alternativas:** cancelar confirmação mantém Pendente; motivo ausente impede transição; tentativa já finalizada segue idempotência/conflito. Pode recusar/cancelar mesmo após vencimento ou inativação do cliente.

**Pós-condição:** tentativa encerrada e preservada. **Vínculos:** PAG-RF06–07, PAG-RF10, PAG-RF13–14; PAG-RN06–13, PAG-RN16–18; PAG-RIS05–07.

### PAG-UC04 — Tentar novamente após recusa ou cancelamento

**Ator:** operador. **Pré-condições:** tentativa anterior Recusada/Cancelada e proposta ainda elegível, sem pagamento ativo.

**Fluxo:** abrir histórico → nova tentativa → escolher método → gerar nova chave → executar PAG-UC01 → manter tentativa anterior intacta.

**Alternativas:** proposta vencida/cancelada, cliente inativo, caminhão indisponível ou pagamento aprovado bloqueiam nova tentativa.

**Pós-condição:** nova tentativa com novo ID e mesma proposta, sem apagar a anterior. **Vínculos:** PAG-RF08, PAG-RF12–14; PAG-RN01–07, PAG-RN09–10, PAG-RN13, PAG-RN18; PAG-RIS02, PAG-RIS04–05.

### PAG-UC05 — Consultar histórico e imprimir comprovante de simulação

**Ator:** operador. **Pré-condição:** tentativa existente.

**Fluxo:** pesquisar/filtrar → abrir detalhes → consultar eventos e motivos → se Aprovado, abrir comprovante e imprimir pelo navegador.

**Alternativas:** outros estados não oferecem comprovante de aprovação; repetição de impressão não gera registro. Tentativas antigas continuam disponíveis quando cliente/veículo mudam de dados ou status.

**Pós-condição:** consulta sem efeito financeiro ou mudança de dados. **Vínculos:** PAG-RF09–11, PAG-RF14; PAG-RN13–16, PAG-RN18; PAG-RNF05; PAG-RIS01, PAG-RIS05.

## 11. Endpoints previstos

| Método e rota | Finalidade |
|---|---|
| `GET /api/payments` | Listar tentativas e dados para pesquisa/filtro. |
| `POST /api/payments` | Criar tentativa a partir de `proposal_id`, `method` e `idempotency_key`; retornar 201 na criação e 200 na repetição. |
| `GET /api/payments/{id}` | Detalhar tentativa, dados comerciais e eventos. |
| `POST /api/payments/{id}/status` | Aprovar, recusar ou cancelar conforme transições permitidas. |

Todas as rotas desta API exigem cookie de sessão válido com papel `admin`. Obter o token CSRF por `GET /api/shop/session` e enviá-lo em `X-CSRF-Token` nos métodos `POST`, `PUT` e `DELETE`. A API retorna 401 sem sessão válida, 403 para papel insuficiente, token CSRF inválido ou origem recusada, e 405 para método não permitido. Não oferecer PUT/PATCH para edição livre nem DELETE para pagamentos. O comprovante usa o detalhe já persistido. Contrato de criação permite somente os campos definidos; valor, status, datas e indicador de simulação pertencem ao servidor. Aplicar erros COM-RNF10, inclusive 409 para conflito de estado, chave reutilizada com conteúdo diferente ou tentativa ativa duplicada.

## 12. Critérios de aceite

- Criar tentativa em cada método sem pedir dados reais, gerar QR code, código pagável ou comunicação financeira externa.
- Rejeitar proposta que não esteja Aprovada/vigente ou cujo cliente/veículo seja inelegível, inclusive via API direta.
- Usar valor integral congelado e impedir divergência enviada pelo navegador.
- Repetir criação com mesma chave/conteúdo e obter o mesmo ID; chave com outro conteúdo retorna conflito.
- Tentar duas criações simultâneas com chaves diferentes para a mesma proposta e obter no máximo uma tentativa Pendente/Aprovada.
- Aprovar e repetir a aprovação sem gerar segundo evento; bloquear recusa/cancelamento de tentativa Aprovada.
- Recusar/cancelar com motivo, manter eventos anteriores e permitir nova tentativa elegível com outro ID.
- Bloquear aprovação após vencimento, inativação do cliente ou indisponibilidade do caminhão; ainda permitir recusa/cancelamento.
- Consultar resultado após perda de resposta sem duplicar tentativa; nunca mostrar sucesso apenas por clique local.
- Gerar comprovante somente de Aprovado, com identificação explícita de simulação e sem valor financeiro.
- Manter caminhão e indicadores de estoque inalterados por todas as ações de simulação.
- Preservar histórico após reinício e impedir exclusão/edição livre de tentativa, proposta com pagamento e eventos.
