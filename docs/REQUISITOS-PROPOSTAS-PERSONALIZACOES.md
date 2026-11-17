# FasTruck — Requisitos de propostas e personalizações

Data: 16/11/2026. Status: implementado. Cobertura de aceite e limites no [relatório de validação](VALIDACAO-MODULOS.md).

Este módulo é administrativo e exige cookie de sessão válido com papel de administrador em suas páginas e APIs; as mutações também exigem token CSRF. Os pedidos feitos pela empresa na loja seguem fluxo próprio na [área do cliente](REQUISITOS-AREA-CLIENTE.md), com registros e pagamentos separados. Um pedido da loja não cria nem altera uma proposta administrativa.

Documento integrante do [plano dos novos módulos](PLANO-NOVOS-MODULOS.md). Aplicam-se também COM-RNF01 a COM-RNF15. Depende do cadastro de veículos existente e do módulo de clientes PJ.

## 1. Objetivo e escopo

Permitir ao administrador montar uma proposta para uma empresa e um caminhão, incluir serviços/acessórios de personalização, calcular o total e acompanhar o estado da negociação. Propostas são registros administrativos e não são pedidos da loja.

O operador registra envio e aprovação manualmente. Esses registros não enviam mensagens, geram assinatura ou concluem compra. A proposta não garante reserva do caminhão.

## 2. Dados da proposta

| Campo | Obrigatoriedade e limite | Regra |
|---|---|---|
| ID | Automático | Identificador estável. |
| Número | Automático e único | Código legível, como `PROP-000001`, gerado sem repetição pelo servidor. |
| Cliente | Obrigatório | Referência a uma empresa cadastrada. |
| Caminhão | Obrigatório | Uma referência ao cadastro de veículos. |
| Preço-base | Automático na criação | Cópia do preço do caminhão em centavos; não é editado diretamente. |
| Itens | Opcionais; no máximo 30 | Personalizações com descrição, quantidade e preço unitário. |
| Descrição do item | Obrigatória por item, 2 a 160 caracteres | Ex.: pintura azul-marinho, rodas, bancos ou iluminação. |
| Quantidade | Obrigatória por item, inteiro de 1 a 100 | Sem quantidade fracionária nesta etapa. |
| Valor unitário | Obrigatório por item, de R$ 0,00 a R$ 999.999,99 | Até duas casas decimais; zero permite item sem custo adicional. |
| Subtotal de item / adicionais | Calculados | Quantidade × preço unitário; adicionais somam todos os itens. |
| Total | Calculado | Preço-base + adicionais; maior que zero e até R$ 999.999.999,99. |
| Validade | Obrigatória, data de Brasília | Último dia para registrar envio/aprovação e criar/aprovar pagamento, inclusive até 23:59:59 do horário de Brasília. |
| Observações | Opcionais, até 2.000 caracteres | Condições comerciais e descrição complementar. |
| Status | Automático na criação | Em elaboração, Enviada, Aprovada ou Cancelada. |
| Motivo de cancelamento | Obrigatório ao cancelar, 3 a 500 caracteres | Preservado no evento. |
| Cópia dos dados enviados | Automática no envio | CNPJ, razão social, contato/endereço e identificação/configuração comercial do caminhão; itens e valores são os da proposta. |
| Datas | Automáticas | Criação, atualização e eventos de envio/aprovação/cancelamento. |

Preço-base numérico inválido no registro legado impede criação, com mensagem para corrigir o cadastro do caminhão. Não converter entradas monetárias com mais de duas casas silenciosamente; rejeitar e orientar correção.

## 3. Estados e validade

| Estado atual | Ações de mudança permitidas | Condições |
|---|---|---|
| Em elaboração | Enviar ou Cancelar | Editável; enviar exige cadastro completo, total positivo, validade vigente, cliente ativo e veículo Disponível. |
| Enviada | Aprovar ou Cancelar | Dados comerciais congelados. Aprovar exige validade vigente, cliente ativo e veículo Disponível. |
| Aprovada | Cancelar | Pode receber pagamento simulado; cancelar exige ausência de pagamento Pendente ou Aprovado. |
| Cancelada | Nenhuma | Histórico disponível, sem edição ou reabertura. |

“Vencida” é um indicador calculado para a proposta cuja validade passou; não é um quinto estado gravado. Uma proposta vencida pode ser consultada ou cancelada, mas não enviada/aprovada nem gerar/aprovar tentativa de pagamento. A elaboração pode ter a validade corrigida antes do envio. Propostas enviadas/aprovadas não têm validade prorrogada: cancelar quando permitido e criar outra.

Não há retorno de Enviada para Em elaboração nesta versão. Repetir a mesma mudança de status retorna o estado atual, sem duplicar eventos; transição proibida retorna conflito.

## 4. Requisitos funcionais

| ID | Requisito |
|---|---|
| PRO-RF01 | Criar proposta em elaboração selecionando empresa ativa e caminhão Disponível. |
| PRO-RF02 | Gerar número único e copiar o preço-base do caminhão automaticamente. |
| PRO-RF03 | Adicionar, editar e remover itens de personalização dentro da proposta em elaboração. |
| PRO-RF04 | Exibir preço-base, subtotais, adicionais e total durante a edição e recalculá-los no backend ao salvar/enviar. |
| PRO-RF05 | Registrar validade e observações da negociação. |
| PRO-RF06 | Listar e pesquisar por número, CNPJ/razão social, placa/marca/modelo; filtrar por status e validade vencida/vigente. |
| PRO-RF07 | Exibir detalhes, itens, total, validade e histórico de mudanças de estado. |
| PRO-RF08 | Editar proposta em elaboração; trocar cliente/caminhão somente nesse estado, recopiando o preço-base ao trocar caminhão. |
| PRO-RF09 | Registrar envio após confirmação e congelar os dados comerciais. |
| PRO-RF10 | Registrar aprovação de proposta enviada após confirmação e validação das condições. |
| PRO-RF11 | Cancelar proposta permitida com confirmação e motivo. |
| PRO-RF12 | Excluir fisicamente proposta em elaboração sem pagamentos, após confirmação, removendo itens/eventos juntos. |
| PRO-RF13 | Oferecer visualização de impressão de proposta enviada/aprovada/cancelada que chegou a ser enviada, com dados congelados. |
| PRO-RF14 | Mostrar tentativas de pagamento vinculadas e permitir iniciar simulação se elegível, abrindo o módulo de pagamentos. |
| PRO-RF15 | Informar bloqueios por cliente inativo, caminhão indisponível, validade, dados inválidos, vínculo ou status; preservar edição em falhas. |
| PRO-RF16 | Persistir proposta, itens e eventos e fornecer endpoints para operações permitidas. |

## 5. Regras de negócio

| ID | Regra |
|---|---|
| PRO-RN01 | Cada proposta possui exatamente um cliente PJ e um caminhão existentes; propostas podem ter zero itens de personalização. |
| PRO-RN02 | Criar, enviar e aprovar exige cliente Ativo e veículo com status Disponível; Reservado e Vendido bloqueiam essas ações. |
| PRO-RN19 | Na edição de rascunho, trocar cliente exige que o novo cliente esteja ativo; trocar caminhão exige que o novo caminhão esteja Disponível. Dados de um vínculo mantido podem ser editados mesmo se ele ficou inelegível; envio/aprovação continuam bloqueados até regularização. |
| PRO-RN03 | Pode haver várias propostas para um mesmo caminhão. Nenhuma reserva, vende, altera preço nem grava personalização no cadastro do veículo automaticamente. |
| PRO-RN04 | O preço-base é copiado na criação. Alterar o preço anunciado do veículo não altera essa cópia. Trocar caminhão em elaboração copia o preço atual do novo caminhão, com confirmação, mantendo os itens para revisão. |
| PRO-RN05 | Itens são específicos da proposta. A descrição deve indicar o adicional; personalizações já incluídas no preço-base não são cobradas novamente automaticamente. |
| PRO-RN06 | Quantidade é inteira de 1 a 100, preço unitário não negativo e limitado; preço-base não pode ser negativo. Total deve ser positivo para envio/aprovação/pagamento. |
| PRO-RN07 | Calcular cada subtotal e o total no servidor, em centavos, e ignorar valores de subtotal/total adulterados enviados pelo navegador. |
| PRO-RN08 | Não aplicar descontos, impostos, frete, juros ou parcelas nesta etapa. O total é exatamente preço-base + itens. |
| PRO-RN09 | Respeitar estados e transições da seção 3. Somente Em elaboração permite mudar cliente, caminhão, itens, validade e observações. |
| PRO-RN10 | Validade na criação deve ser hoje ou data futura. Após vencer, bloquear envio/aprovação, criação e aprovação de pagamento. |
| PRO-RN11 | No envio, congelar dados comerciais do cliente/caminhão, valores e itens; detalhes e impressão usam essa versão depois. Histórico continua vinculado aos IDs originais. |
| PRO-RN12 | Mudanças futuras no cadastro do cliente ou veículo não reescrevem dados congelados. Revalidar status atual para ações novas, mesmo quando os dados exibidos são da proposta enviada. |
| PRO-RN13 | Somente proposta Aprovada, vigente e com cliente/veículo elegíveis pode originar tentativa de pagamento; o módulo financeiro revalida as condições. |
| PRO-RN14 | Não cancelar proposta com pagamento Pendente ou Aprovado. Tentativa pendente deve ser cancelada primeiro; sem estorno, resultado aprovado impede cancelamento da proposta nesta etapa. |
| PRO-RN15 | Excluir somente Em elaboração sem qualquer pagamento vinculado. Enviada, Aprovada e Cancelada são preservadas. |
| PRO-RN16 | Cada transição grava data e estados anterior/novo; cancelamento exige motivo. Não permitir editar ou excluir eventos pela interface/API. |
| PRO-RN17 | A existência de proposta bloqueia a exclusão física de cliente e caminhão, inclusive se a proposta estiver Cancelada. |
| PRO-RN18 | Envio/aprovação são declarações manuais do operador; não comprovam recebimento, assinatura, consentimento ou transação financeira. |

## 6. Requisitos não funcionais específicos

| ID | Requisito |
|---|---|
| PRO-RNF01 | Gravar proposta, itens, total e evento de status atomicamente; não deixar proposta com apenas parte dos itens após erro. |
| PRO-RNF02 | Converter preço legado para centavos usando Decimal a partir de sua representação textual, arredondando meio para cima apenas na conversão; novos preços aceitam no máximo duas casas e não usam float. |
| PRO-RNF03 | Tela e impressão devem mostrar os mesmos valores congelados. Layout de impressão oculta menus/botões e permite impressão pelo navegador sem serviço externo ou biblioteca PDF obrigatória. |
| PRO-RNF04 | Verificações de vínculo, status e validade ocorrem na transação da ação. Requisição atrasada ou repetida não pode modificar proposta que já saiu de Em elaboração. |
| PRO-RNF05 | Guardar eventos em UTC; interpretar a data de validade no fuso comercial America/Sao_Paulo, com regra equivalente disponível no Windows e sem depender do relógio do navegador. |

## 7. Premissas

- Empresa e caminhão já foram cadastrados e o operador tem informações dos adicionais para orçar.
- Preço-base já inclui o caminhão e suas características cadastradas; itens são custos adicionais negociados.
- O administrador registra a negociação e a aprovação recebida por outros meios; o cliente não participa deste fluxo. O cliente pode, separadamente, criar pedidos pela área da loja.
- O volume e a disponibilidade de personalizações são declarados pelo operador; não existe estoque de acessórios.
- Status do veículo continua administrado manualmente; a proposta não garante exclusividade sobre o caminhão.

## 8. Restrições

- Um cliente e um caminhão por proposta, somente BRL, pagamento integral e itens com quantidade inteira.
- Sem catálogo separado, cálculo automático de compatibilidade de acessórios, descontos, tributos, frete ou financiamento.
- Sem envio de e-mail/WhatsApp, assinatura digital, cópia automática de proposta, revisões de documento enviado ou prorrogação após envio.
- Impressão pelo navegador; geração de PDF próprio, anexos e layout de contrato ficam fora da etapa.
- Aprovada não significa venda concluída; status de pagamento é mostrado separadamente do status de negociação.

## 9. Riscos e respostas

| ID | Risco | Resposta nesta etapa |
|---|---|---|
| PRO-RIS01 | Valor antigo mudar junto com o cadastro | Copiar preço-base e congelar os dados enviados. |
| PRO-RIS02 | Cobrar adicional duas vezes | Mostrar preço-base e itens separados; não importar automaticamente observações de personalização como cobrança. |
| PRO-RIS03 | Erro de arredondamento ou manipulação do total | Centavos inteiros, Decimal na conversão e recálculo do servidor. |
| PRO-RIS04 | Proposta ser aprovada para cliente inativo, veículo indisponível ou após prazo | Revalidar as três condições na transação. |
| PRO-RIS05 | Perder histórico por exclusão de vínculo | Restringir exclusão e manter dados congelados. |
| PRO-RIS06 | Duas propostas parecerem duas reservas garantidas | Indicar ausência de reserva automática e verificar disponibilidade nas ações comerciais. |
| PRO-RIS07 | Simulação aprovada e proposta cancelada deixarem estado contraditório | Bloquear cancelamento com pagamento Pendente/Aprovado. |

## 10. Casos de uso

Os casos abaixo são executados por um administrador autenticado. Sem sessão válida, a API responde 401; com papel insuficiente ou falha de CSRF/origem, responde 403.

### PRO-UC01 — Montar proposta com personalizações

**Ator:** operador. **Pré-condições:** empresa ativa e veículo Disponível cadastrados.

1. Acionar “Nova proposta” e selecionar empresa e caminhão.
2. O sistema mostra preço-base copiado e informações comerciais.
3. Informar validade e observações; adicionar itens com descrição, quantidade e valor unitário.
4. Conferir subtotais e total e salvar.
5. O backend valida referências, calcula valores e grava proposta Em elaboração e itens.

**Alternativas:** nenhum adicional é permitido; campos inválidos, limite de itens/valor ou vínculo inelegível impedem gravação. Falha de item desfaz a operação inteira.

**Pós-condição:** rascunho persistido com número único. **Vínculos:** PRO-RF01–05, PRO-RF15–16; PRO-RN01–08, PRO-RN10; PRO-RNF01–02; PRO-RIS02–04.

### PRO-UC02 — Editar ou excluir rascunho

**Ator:** operador. **Pré-condição:** proposta Em elaboração sem pagamentos.

**Edição:** abrir → alterar campos/itens → ao trocar caminhão confirmar novo preço-base → salvar → recalcular no servidor.

**Exclusão:** solicitar excluir → confirmar → servidor revalida status/vínculos → remover proposta, itens e eventos na mesma transação.

**Alternativas:** estado já alterado por outra requisição bloqueia edição/exclusão; cancelar confirmação mantém dados. Para Enviada/Aprovada/Cancelada, oferecer consulta ou cancelamento permitido, sem exclusão física.

**Pós-condição:** rascunho atualizado ou removido. **Vínculos:** PRO-RF03–05, PRO-RF08, PRO-RF12, PRO-RF15–16; PRO-RN04, PRO-RN07, PRO-RN09–10, PRO-RN15; PRO-RNF01, PRO-RNF04.

### PRO-UC03 — Registrar envio

**Ator:** operador. **Pré-condição:** proposta Em elaboração completa e vigente.

1. Conferir valores, dados, validade e indicar “Registrar envio”.
2. Confirmar a ação; servidor revalida cliente ativo e veículo Disponível.
3. Congelar dados comerciais, gravar evento e mudar para Enviada.
4. Disponibilizar detalhes e impressão da versão enviada.

**Alternativas:** dado incompleto, prazo vencido ou indisponibilidade bloqueia transição; erro desfaz congelamento/evento/status. Não dispara comunicação externa.

**Pós-condição:** proposta Enviada e conteúdo comercial bloqueado para edição. **Vínculos:** PRO-RF09, PRO-RF13, PRO-RF15–16; PRO-RN02–03, PRO-RN06–12, PRO-RN16, PRO-RN18; PRO-RNF01, PRO-RNF03–05; PRO-RIS01–04, PRO-RIS06.

### PRO-UC04 — Registrar aprovação ou cancelamento

**Ator:** operador. **Pré-condição de aprovação:** proposta Enviada vigente, cliente ativo e veículo Disponível.

**Aprovação:** abrir detalhes → registrar e confirmar aprovação → revalidar condições → gravar evento → mudar para Aprovada.

**Cancelamento:** solicitar em estado permitido → informar motivo → confirmar → revalidar ausência de pagamento Pendente/Aprovado → registrar evento e mudar para Cancelada.

**Alternativas:** vencimento/status inelegível impede aprovação. Pagamento pendente exige cancelar tentativa primeiro; aprovado bloqueia cancelamento. Repetir ação concluída não duplica evento. Cancelada não reabre.

**Pós-condição:** negociação atualizada sem alteração automática do caminhão. **Vínculos:** PRO-RF10–11, PRO-RF15–16; PRO-RN02–03, PRO-RN09–10, PRO-RN12–14, PRO-RN16, PRO-RN18; PRO-RIS04, PRO-RIS07.

### PRO-UC05 — Consultar, imprimir e acessar pagamentos

**Ator:** operador. **Pré-condição:** proposta existente.

**Fluxo:** pesquisar/filtrar → abrir → consultar itens, valores e eventos → imprimir versão enviada quando disponível → consultar tentativas financeiras e iniciar pagamento simulado se elegível.

**Alternativas:** rascunho sem envio não oferece impressão comercial; proposta vencida/cancelada ou com cliente inativo/caminhão indisponível não inicia pagamento. Dados congelados continuam acessíveis e não são reescritos por mudanças nos cadastros.

**Pós-condição:** consulta sem alteração ou encaminhamento para PAG-UC01. **Vínculos:** PRO-RF06–07, PRO-RF13–16; PRO-RN03, PRO-RN10–14, PRO-RN16–18; PRO-RNF03, PRO-RNF05; PRO-RIS01, PRO-RIS05–07.

## 11. Endpoints previstos

| Método e rota | Finalidade |
|---|---|
| `GET /api/proposals` | Listagem e dados para filtros. |
| `POST /api/proposals` | Criar rascunho com itens; retornar 201. |
| `GET /api/proposals/{id}` | Detalhar dados, itens, histórico e pagamentos. |
| `PUT /api/proposals/{id}` | Substituir campos editáveis e itens somente em elaboração. |
| `POST /api/proposals/{id}/status` | Registrar envio, aprovação ou cancelamento permitido. |
| `DELETE /api/proposals/{id}` | Excluir rascunho sem pagamentos. |

Todas as rotas desta API exigem cookie de sessão válido com papel `admin`. Obter o token CSRF por `GET /api/shop/session` e enviá-lo em `X-CSRF-Token` nos métodos `POST`, `PUT` e `DELETE`. A API retorna 401 sem sessão válida, 403 para papel insuficiente, token CSRF inválido ou origem recusada, e 405 para método não permitido. Impressão usa os dados do detalhe na própria interface. Dados calculados, número, cópias congeladas e datas não são editáveis pelo cliente HTTP. Aplicar respostas de erro COM-RNF10.

## 12. Critérios de aceite

- Criar proposta para empresa ativa/veículo disponível com zero, um ou vários itens; bloquear outros vínculos.
- Conferir cálculo: preço-base R$ 500.000,00 + 2 × R$ 1.500,00 + 1 × R$ 4.000,00 = R$ 507.000,00.
- Manipular o total no JSON não muda o valor calculado pelo servidor; rejeitar quantidade fracionária, negativa, maior que 100 e preço com mais de duas casas.
- Editar rascunho e trocar caminhão com revisão explícita do novo preço-base; manter ID e número.
- Registrar envio e impedir alteração de campos/itens depois disso, inclusive por PUT direto.
- Alterar razão social, endereço ou características do caminhão após envio sem mudar a versão comercial impressa.
- Impedir transições inválidas e ações comerciais depois da validade ou com vínculo inelegível.
- Consultar eventos de envio, aprovação e cancelamento com data; repetição de ação não duplica evento.
- Bloquear cancelamento com pagamento pendente/aprovado e exclusão fora do rascunho.
- Bloquear exclusão do caminhão/cliente quando qualquer proposta existir; não mudar estoque por enviar/aprovar proposta.
- Manter valores e histórico após reiniciar o servidor e cumprir requisitos comuns de interface, segurança e atomicidade.
