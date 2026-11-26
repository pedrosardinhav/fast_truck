# FasTruck — Cadastro administrativo de veículos

Data: 25/11/2026. Documento do estoque administrativo e do ciclo de vida integrado. A loja, os pedidos e o pagamento são descritos em [Área do cliente](REQUISITOS-AREA-CLIENTE.md).

## 1. Objetivo e escopo

Cadastrar e gerenciar caminhões da FasTruck, incluindo características, preço anunciado, situação do estoque e observações de personalização. O painel fica em `/admin` e exige conta de administrador; a raiz `/` é a loja pública e mostra apenas veículos Disponíveis.

HTML, CSS e JavaScript compõem a interface; Python e SQLite implementam a API e a persistência. O estoque mantém histórico por exclusão lógica, controla reservas temporárias do checkout e registra venda administrativa ou da loja.

## 2. Premissas e dados

- O administrador inicia `python src/backend/app.py` na raiz do projeto, acessa o servidor local e entra com suas credenciais.
- A primeira execução do servidor cria o acesso administrativo em `data/.admin-access`, ignorado pelo Git; o botão **Admin** no cabeçalho permite consultá-lo e preencher o login local.
- A base padrão é `data/fasttruck.db`, criada localmente e ignorada pelo Git.
- Uma base nova recebe 13 caminhões de exemplo; as duas cargas são aplicadas uma vez e não recriam veículos excluídos. Sete empresas acadêmicas são carregadas por `src/backend/demo_data.py` para viabilizar consulta e compra.
- O administrador declara as características e a disponibilidade; o sistema não verifica documentação, procedência ou estado mecânico.
- O servidor escuta em `127.0.0.1:8000`; outras pessoas executam sua própria cópia do projeto.

| Campo | Regra do cadastro |
|---|---|
| ID | Texto gerado pelo servidor; preservado na edição. |
| Placa | Obrigatória, normalizada e única; padrão antigo ou Mercosul. |
| Marca, modelo, cor | Textos obrigatórios, sem valor composto apenas de espaços. |
| Ano de fabricação/modelo | Texto obrigatório, até 20 caracteres; permite apresentação como `2022 / 2023`. |
| Status | Obrigatório: Disponível, Reservado ou Vendido. |
| Valor anunciado | Obrigatório, número finito não negativo, em reais; tabela legada usa REAL. |
| Carroceria, tração, combustível | Textos opcionais. |
| Quilometragem | Opcional, convertida para inteiro no servidor, não negativa; valor ausente usa zero. |
| Personalizado | `sim` ou `nao`; formulário permite escolher ambos. |
| Observações | Texto opcional para características e personalizações já incluídas no anúncio. |

## 3. Requisitos funcionais

| ID | Requisito |
|---|---|
| RF01 | Cadastrar caminhão com placa, marca, modelo, ano, cor, status e valor anunciado. |
| RF02 | Registrar carroceria, tração, combustível, quilometragem e informações de personalização. |
| RF03 | Listar veículos com identificação, placa, ano, personalização, status e preço. |
| RF04 | Editar veículo existente preservando o identificador. |
| RF05 | Arquivar caminhão por exclusão lógica, registrando data, administrador e motivo; bloquear arquivamento enquanto estiver Reservado. |
| RF06 | Pesquisar por placa, marca ou modelo e filtrar por status na interface. |
| RF07 | Mostrar cadastros ativos (`deleted_at IS NULL`), disponíveis e personalizados; somar valores anunciados exceto os Vendidos. Indicadores ignoram busca/filtros da lista. |
| RF08 | Persistir e recuperar os cadastros no SQLite por meio da API Python. |
| RF09 | Mostrar mensagens de sucesso ou erro nas operações. |
| RF10 | Disponibilizar endpoints autenticados para listar, criar, atualizar e arquivar veículos. |
| RF11 | Restringir painel e operações administrativas a contas autenticadas com papel de administrador. |
| RF12 | Consultar estoque ativo, arquivado ou completo; consultar detalhe com eventos e venda vinculada. |
| RF13 | Registrar eventos de criação, edição, arquivamento, reserva, liberação e venda com snapshots antes/depois quando aplicável. |
| RF14 | Registrar venda administrativa para empresa ativa, com valor informado ou preço anunciado, observações e chave UUID opcional. |
| RF15 | Preservar veículos vendidos e arquivados para consulta; manter placas únicas inclusive no histórico. |

## 4. Regras de negócio

| ID | Regra |
|---|---|
| RN01 | Placa obrigatória nos padrões antigo (`ABC-1234`) ou Mercosul (`ABC-1D23`); normalizar letras para maiúsculas e apresentar hífen. |
| RN02 | Placa é única; pontuação e espaços são removidos na normalização antes de validar e gravar. |
| RN03 | Marca, modelo, ano, cor, status e valor anunciado são obrigatórios. |
| RN04 | Status só aceita Disponível, Reservado ou Vendido. |
| RN05 | Quilometragem convertida para inteiro e valor anunciado não podem ser negativos; preço precisa ser finito. |
| RN06 | Personalização só aceita `sim` ou `nao`; observações são opcionais. |
| RN07 | Atualização mantém ID e valida novamente campos e unicidade da placa. |
| RN08 | `DELETE /api/vehicles/{id}` arquiva o registro: define `deleted_at`, `deleted_by` e `deleted_reason`, sem apagar linha, placa, eventos, pedidos ou vendas. |
| RN09 | Indicadores contam todos os cadastros não arquivados, inclusive Vendidos, sem considerar busca/filtros. A soma anunciada inclui apenas veículos ativos não Vendidos. |
| RN10 | Cargas iniciais usam metadados para execução única; não reinserem registros removidos pelo administrador. |
| RN11 | Arquivamento é bloqueado para veículo Reservado; veículo Vendido pode ser arquivado, mas permanece consultável em `deleted`/`all`. |
| RN12 | Reserva de checkout pertence a um pedido e expira em 15 minutos; expiração cancela pedido/tentativas ativas e libera somente a reserva daquele pedido. |
| RN13 | Venda exige empresa ativa e veículo não arquivado. Checkout só vende Reserva cujo pedido é o proprietário; venda administrativa também pode concluir veículo com status Reservado quando `reserved_order_id IS NULL`, sem tomar reserva pertencente a pedido. |
| RN14 | Vínculos e histórico comercial não são apagados. Alterações no cadastro não reescrevem snapshots existentes. |
| RN15 | Concluir venda atualiza `vehicles.status='Vendido'`, grava `sold_at`, `vehicle_sales` e evento na mesma transação. |
| RN16 | Placa continua única após arquivamento; recadastrar placa histórica não é permitido. |

## 5. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF01 | Interface responsiva para desktop e telas estreitas. |
| RNF02 | Campos rotulados, foco visível e mensagens acessíveis. |
| RNF03 | Escapar texto do cadastro antes de inseri-lo como HTML na lista. |
| RNF04 | Usar a biblioteca padrão do Python, sem pacotes externos obrigatórios. |
| RNF05 | Persistir entre reinícios; fazer cópia automática antes de migrações pendentes quando houver veículos, mantendo cópias periódicas manuais. |
| RNF06 | Validar no servidor, além das validações do formulário, e restringir operações administrativas por sessão e papel. |
| RNF07 | Servir interface e API na mesma origem local `http://127.0.0.1:8000`. |

## 6. Restrições

- Operação local; sem implantação pública, sincronização entre instalações ou preparação de produção. O atalho de credenciais administrativas não deve ser publicado na internet.
- A existência de login não comprova titularidade do veículo ou dados empresariais.
- Sem consulta oficial de placa, documentação, procedência, valor de mercado ou especificações mecânicas.
- Sem upload de fotos, consulta oficial de placa ou integração de pagamento real.
- Reserva pertence ao checkout da loja; apenas a venda administrativa pode concluir diretamente um veículo reservado sem pedido proprietário.
- Não há cópias periódicas agendadas; a cópia de migração não substitui backup operacional regular.

## 7. Riscos e respostas

| Risco | Tratamento ou limite |
|---|---|
| Perder ou danificar o SQLite | Manter cópia periódica com servidor parado; preservar também credenciais e chave local necessárias. |
| Placa repetida por variação de escrita | Normalizar e validar na API, com restrição UNIQUE no banco. |
| Banco inacessível ou servidor parado | Apresentar erro; iniciar o servidor pelo comando do README. |
| Personalização ou características incorretas | Informação declarada pelo administrador, sem verificação externa. |
| Acesso indevido ao estoque | Exigir papel admin na API; manter servidor em loopback, sem exposição pública. |
| Erro ao gravar | Usar transação e informar falha sem confirmar a operação. |
| Perder histórico comercial por remover caminhão | Arquivamento lógico conserva linha, placa, vínculos, eventos e venda; FK continua restringindo remoção física. |
| Duas compras disputarem o mesmo veículo | Reserva condicional transacional, expiração UTC e venda atômica vinculada ao pedido reservador. |
| Vendedor arquivar veículo reservado | API rejeita arquivamento enquanto houver reserva ativa. |

## 8. Casos de uso

Todos os casos administrativos exigem servidor/banco disponíveis e sessão com papel de administrador.

### UC01 — Cadastrar caminhão

**Ator:** administrador. **Fluxo:** abre Novo caminhão → preenche campos obrigatórios e opcionais → confirma cadastro → API valida → SQLite grava → lista/indicadores são atualizados. **Alternativas:** placa inválida/duplicada, campos rejeitados ou falha de conexão/gravação mostram erro sem confirmar cadastro. **Pós-condição:** novo veículo persiste no estoque.

### UC02 — Consultar e localizar caminhão

**Ator:** administrador. **Fluxo:** abre painel → carrega lista da API → pesquisa placa/marca/modelo e filtra status. **Pós-condição:** lista filtrada; indicadores continuam representando o estoque inteiro, sem alterar registros.

### UC03 — Editar caminhão

**Ator:** administrador. **Pré:** veículo existe. **Fluxo:** aciona editar → formulário recebe valores atuais → altera e salva → API revalida e atualiza mesmo ID → lista e indicadores atualizam. **Alternativas:** dados rejeitados, placa duplicada ou falha de persistência não confirmam alteração. **Pós-condição:** estoque atualizado; pedidos históricos não são reescritos.

### UC04 — Arquivar caminhão

**Ator:** administrador. **Pré:** veículo existe e não está Reservado. **Fluxo:** informa motivo (mínimo 3, máximo 500; vazio usa motivo padrão) → confirma → API marca `deleted_at`, `deleted_by`, `deleted_reason` e registra evento → sai da visão ativa, mas continua em consultas `deleted` e `all`. **Alternativas:** reserva ativa gera conflito; ID inexistente retorna não encontrado. **Pós-condição:** registro permanece íntegro no banco e sua placa continua ocupada.

### UC05 — Consultar histórico do veículo

**Ator:** administrador. **Fluxo:** lista `GET /api/vehicles?view=active|deleted|all` (padrão `active`) → abre `GET /api/vehicles/{id}` → recebe histórico de eventos e venda, inclusive para arquivados. **Pós-condição:** consulta não altera o histórico, exceto liberação de reservas vencidas processada na transação da listagem.

### UC06 — Registrar venda administrativa

**Ator:** administrador. **Pré:** empresa ativa e veículo não arquivado nem vendido; veículo Reservado sem `reserved_order_id` pode ser vendido manualmente, mas a reserva de checkout de outro pedido não pode ser tomada. **Fluxo:** envia `customer_id`, `amount` opcional, `notes` e `idempotency_key` UUID opcional → API valida → grava venda, status Vendido, `sold_at` e evento atomicamente. Sem valor usa o preço anunciado convertido a centavos. **Alternativas:** empresa inativa, venda duplicada, reserva de outro pedido ou dado inválido gera conflito/erro sem gravação parcial. **Pós-condição:** veículo vendido com número `VEN-...` e histórico consultável.

### UC07 — Comprar na loja e reservar

**Ator:** cliente autenticado. **Fluxo:** cria pedido de caminhão disponível → veículo fica Reservado para o pedido por 15 minutos → escolhe cartão, Pix ou boleto → o servidor processa automaticamente → aprovação, venda e mudança para Vendido ocorrem juntas. **Alternativas:** recusa permite nova tentativa; expiração ou cancelamento libera somente a reserva do pedido proprietário. O processamento é interno ao projeto e não coleta PAN/CVV ou credenciais bancárias.

## 9. Rastreabilidade

| Caso | Requisitos e regras |
|---|---|
| UC01 | RF01, RF02, RF08–RF11; RN01–RN06, RN10; RNF03, RNF04, RNF06 |
| UC02 | RF03, RF06, RF07, RF08, RF10, RF11; RN09; RNF01, RNF02, RNF07 |
| UC03 | RF04, RF08–RF11; RN02, RN07, RN11; RNF05, RNF06 |
| UC04 | RF05, RF08–RF13, RF15; RN08, RN11, RN14, RN16; RNF05, RNF06 |
| UC05 | RF12, RF13, RF15; RN08, RN14; RNF05, RNF06 |
| UC06 | RF14–RF15; RN11, RN13–RN16; RNF05–RNF06 |
| UC07 | RF12–RF15; RN12–RN16; RNF05–RNF06 |

## 10. Contrato da API e critérios de aceite

| Método e rota | Finalidade |
|---|---|
| `GET /api/vehicles?view=active\|deleted\|all` | Listar veículos; omitir `view` retorna `active`. |
| `POST /api/vehicles` | Criar veículo. |
| `PUT /api/vehicles/{id}` | Atualizar veículo. |
| `DELETE /api/vehicles/{id}` | Arquivar (soft delete); payload opcional `{ "reason": "..." }`. |
| `GET /api/vehicles/{id}` | Detalhar inclusive arquivados, eventos e venda. |
| `POST /api/vehicles/{id}/sell` | Venda administrativa; `customer_id`, `amount` opcional, `notes`, `idempotency_key` opcional. |
| `GET /api/shop/catalog` | Catálogo público somente de veículos Disponíveis. |

As rotas administrativas exigem cookie de sessão admin; mutações exigem `X-CSRF-Token` obtido em `GET /api/shop/session`. Respostas incluem 401 sem sessão, 403 para papel ou CSRF/origem recusados, 400 para dados inválidos, 404 para ID inexistente e 409 para duplicidade/vínculo. A página administrativa redireciona visitante para entrar.

Critérios de aceite: criar/editar/listar e arquivar sem apagar; rejeitar placa duplicada/preço negativo; permitir consultas históricas; bloquear arquivamento reservado; reservar por 15 minutos, liberar apenas reserva proprietária, exigir empresa ativa e gravar venda/veículo/evento atomicamente. Resultados da validação são registrados separadamente em [validação](VALIDACAO-MODULOS.md).
