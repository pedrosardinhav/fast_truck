# FasTruck — Área do cliente e pedidos da loja

Data: 16/11/2026. Este documento especifica o fluxo de conta empresarial, loja e pedidos. O painel administrativo de veículos, clientes, propostas e pagamentos continua protegido por conta de administrador. Pedidos da loja e propostas comerciais são processos separados, com tabelas e estados próprios.

## 1. Objetivo e atores

A loja pública permite consultar caminhões disponíveis, escolher personalizações e, após autenticação, criar e acompanhar pedidos. Uma empresa só vê pedidos vinculados à própria conta. O administrador mantém os cadastros e pode consultar os pedidos da loja. Toda tentativa de pagamento da loja é uma simulação sem valor financeiro.

| Ator | Acesso |
|---|---|
| Visitante | Loja pública, catálogo de caminhões e personalizações; pode criar nova conta e entrar. |
| Cliente | Sua conta empresarial, criação de pedidos, tentativas simuladas, consulta e cancelamento de pedidos próprios. |
| Administrador | Painel administrativo, cadastros e propostas existentes, e consulta de pedidos da loja. |

## 2. Dados e estados

O banco tem cinco migrações versionadas (`001_customers.sql` a `005_shop_orders.sql`). Os domínios ficam separados: propostas e pagamentos administrativos usam `proposals`, `proposal_items`, `proposal_events`, `payments` e `payment_events`; a loja usa `accounts`, `shop_sessions`, `shop_orders`, `shop_order_items` e `shop_order_payments`. Ambos referenciam `customers` e `vehicles`; pedido não é proposta e pagamento de loja não é pagamento de proposta.

| Registro | Dados relevantes |
|---|---|
| Conta | `id`, `customer_id`, e-mail único da conta, hash scrypt, papel `customer`/`admin` e data de criação. Conta de cliente tem uma empresa; conta admin não tem empresa. Uma empresa pode ter no máximo uma conta. |
| Sessão | Hash do token aleatório, conta, token CSRF e expiração. Cookie `fastruck_session` é HttpOnly, SameSite=Lax e tem validade de sete dias. |
| Pedido | UUID, número sequencial `PED-000001`, empresa e caminhão vinculados, preço-base e total em centavos, notas, status, snapshots da empresa/caminhão, hash da requisição idempotente e datas. |
| Item de pedido | ID de personalização, descrição e preço unitário copiados do catálogo servidor, quantidade inteira e subtotal em centavos. |
| Tentativa de pagamento da loja | Método, resultado escolhido, valor integral do pedido, chave UUID idempotente, indicador `simulated=1` e data. Não armazena dados de cartão. |

Estados do pedido: `Aguardando pagamento`, `Pagamento aprovado` ou `Cancelado`. A aprovação e o cancelamento do pedido são finais. Uma tentativa registra `Aprovado`, `Recusado` ou `Cancelado`; recusa/cancelamento da tentativa mantém o pedido aguardando pagamento e permite outra tentativa. Apenas uma tentativa aprovada é permitida por pedido.

### Campos de cadastro e limites do servidor

O cadastro de empresa exige CNPJ válido, razão social (2–160), contato (2–120), telefone nacional com DDD (10 ou 11 dígitos após normalização), e-mail de contato (até 254), CEP (oito dígitos), logradouro (2–160), número (1–20), bairro (2–100), cidade (2–100) e UF brasileira de duas letras. Nome fantasia (até 160), complemento (até 100) e observações (até 1.000) são opcionais. E-mail da conta aceita até 254 caracteres e senha de 8–128 caracteres. Esses limites são validados no backend; o navegador também marca os campos obrigatórios e limita alguns campos de texto.

## 3. Catálogo e personalizações

`GET /api/shop/catalog` é público e retorna somente veículos cujo status é `Disponível`, sem incluir registros de clientes. Cada veículo expõe os campos cadastrais públicos: `id`, `plate`, `brand`, `model`, `year`, `color`, `body`, `axles`, `fuel`, `km`, `price`, `customized`, `notes` e `status`.

`GET /api/shop/customizations` é público e retorna `{id,name,price_cents}`. O catálogo atual é definido no backend:

| ID | Nome | Preço unitário |
|---|---|---:|
| `pintura` | Pintura personalizada | R$ 8.500,00 |
| `rodas` | Rodas especiais | R$ 2.400,00 |
| `cabine` | Personalização de cabine | R$ 6.200,00 |
| `defletor` | Defletor | R$ 3.900,00 |
| `luzes` | Iluminação auxiliar | R$ 1.750,50 |
| `camera` | Câmera | R$ 980,00 |

O cliente envia apenas o ID e a quantidade de cada adicional. A interface oferece quantidades de 1 a 10; a API valida inteiros de 1 a 100. A API admite até 30 itens, rejeita IDs desconhecidos e repetição do mesmo ID; na prática, há no máximo seis adicionais distintos.

## 4. Requisitos funcionais

| ID | Requisito |
|---|---|
| LOJ-RF01 | Servir a loja pública na raiz e exibir somente caminhões `Disponível`, com busca e ordenação local por preço. |
| LOJ-RF02 | Exibir campos públicos do caminhão e permitir abrir seus detalhes. |
| LOJ-RF03 | Cadastrar conta de cliente e nova empresa PJ na mesma operação, validando os dados no servidor. |
| LOJ-RF04 | Autenticar cliente ou administrador por e-mail de conta e senha; permitir sair. |
| LOJ-RF05 | Consultar a sessão atual ao abrir/recarregar a loja e manter acesso enquanto a sessão não expirar ou for invalidada. |
| LOJ-RF06 | Exibir personalizações e preços definidos no servidor; permitir selecionar opções e quantidades. |
| LOJ-RF07 | Mostrar caminhão, adicionais, notas e total estimado antes de enviar o pedido. |
| LOJ-RF08 | Criar pedido para exatamente um caminhão, vinculado à empresa da sessão, com preço calculado no servidor. |
| LOJ-RF09 | Listar e detalhar somente pedidos da empresa autenticada, com snapshots, itens e tentativas. |
| LOJ-RF10 | Registrar tentativa simulada integral por Pix, Boleto ou Cartão, sem coletar dados bancários ou de cartão. |
| LOJ-RF11 | Permitir ao cliente escolher o resultado simulado: Aprovado, Recusado ou Cancelado. |
| LOJ-RF12 | Permitir outra tentativa após recusa/cancelamento da tentativa, enquanto o pedido estiver aguardando pagamento. |
| LOJ-RF13 | Exibir comprovante imprimível identificado como simulado e sem valor financeiro. |
| LOJ-RF14 | Permitir cancelar pedido próprio enquanto não houver aprovação, mantendo pedido e tentativas no histórico. |
| LOJ-RF15 | Exigir papel de administrador para APIs e páginas administrativas; exigir sessão de cliente para pedidos e conta. |
| LOJ-RF16 | Permitir ao administrador listar e consultar os pedidos da loja e suas tentativas; interface administrativa permite pesquisa local. |
| LOJ-RF17 | Aplicar migrações versionadas preservando registros existentes e criar backup automático antes de migrar uma base com veículos. |
| LOJ-RF18 | Informar rejeições de cadastro, autenticação, disponibilidade e processamento sem indicar sucesso quando a operação falhar. |

## 5. Regras de negócio

| ID | Regra |
|---|---|
| LOJ-RN01 | Conta de cliente referencia uma única empresa; `accounts.customer_id` é único. Conta admin não referencia empresa. |
| LOJ-RN02 | CNPJ é único na tabela de empresas e e-mail de conta é único em `accounts`. E-mail de contato da empresa é um campo separado e não substitui a unicidade do e-mail de acesso. |
| LOJ-RN03 | Registro público cria apenas papel `customer`; empresa e `customer_id` são derivados no servidor, não escolhidos pelo usuário. |
| LOJ-RN04 | Senha tem 8 a 128 caracteres; é guardada como hash scrypt com salt e nunca retornada pela API. |
| LOJ-RN05 | Cliente de empresa inativa não consegue entrar nem usar sessão existente. A inativação bloqueia ações da conta. |
| LOJ-RN06 | Pedido contém exatamente um caminhão; adicionais são opcionais. Não existe carrinho de vários caminhões. |
| LOJ-RN07 | Caminhão deve estar `Disponível` na criação e novamente na aprovação. Pagamento simulado não altera o estoque. |
| LOJ-RN08 | Catálogo fixo de personalizações e preços é definido no backend; cliente não envia descrição/preço. A API rejeita propriedades extras nos itens. |
| LOJ-RN09 | Cada item aceita somente `customization_id` e `quantity`; quantidade inteira 1–100, sem IDs repetidos, até 30 itens e apenas IDs catalogados. |
| LOJ-RN10 | O backend calcula preços em centavos. Preço-base do veículo e total têm limite de R$ 99.999.999,99; total do pedido deve ser maior que zero. |
| LOJ-RN11 | Snapshots copiam dados comerciais e preço ao criar pedido. Alterações posteriores em cliente/veículo não reescrevem o pedido. |
| LOJ-RN12 | Chaves de idempotência são UUID. Repetição com a mesma intenção retorna o registro; reutilização com outro conteúdo gera conflito. |
| LOJ-RN13 | Apenas uma aprovação financeira por pedido. Pedido e tentativas não podem ser excluídos pela loja; cancelamento preserva o registro e as datas. |
| LOJ-RN14 | Resultado é escolha explícita da simulação; não há gateway, cobrança, QR Code bancário ou boleto válido. Campos de pagamento aceitam somente método, resultado e chave idempotente. |
| LOJ-RN15 | Pedido e pagamento não reservam nem vendem caminhão. Vários clientes podem pedir o mesmo veículo; a disponibilidade é revalidada antes da aprovação, sem controle de estoque reservado. |
| LOJ-RN16 | Consulta de pedido sempre filtra por empresa autenticada; ID de pedido alheio responde 404. |
| LOJ-RN17 | Não excluir empresa com conta, proposta ou pedido vinculado, nem caminhão com proposta ou pedido. Não alterar CNPJ de empresa vinculada a conta, proposta ou pedido. O servidor verifica esses vínculos, e as chaves estrangeiras preservam as referências existentes. |
| LOJ-RN18 | Se não existir administrador, a inicialização cria conta admin local com senha aleatória e grava as credenciais em `data/.admin-access`, arquivo ignorado pelo Git. Registro público não cria admin. |

## 6. Requisitos não funcionais

| ID | Requisito |
|---|---|
| LOJ-RNF01 | Manter Python/SQLite e HTML/CSS/JavaScript sem dependências Python externas obrigatórias. |
| LOJ-RNF02 | Interface responsiva com rótulos, foco visível e mensagens de erro/sucesso compreensíveis. |
| LOJ-RNF03 | Usar scrypt com salt aleatório para senha e persistir somente hash de token de sessão. |
| LOJ-RNF04 | Cookie de sessão HttpOnly/SameSite=Lax; mutações autenticadas exigem token CSRF e, se houver cabeçalho Origin, origem compatível com Host. |
| LOJ-RNF05 | Validar autorização e regras no backend, independentemente da interface. A API usa 401 para falta de sessão e 403 para papel/permissão insuficiente; página administrativa redireciona visitante ao acesso. |
| LOJ-RNF06 | Gravar conta/empresa, pedido/itens e tentativa/status em transações SQLite (`BEGIN IMMEDIATE`). |
| LOJ-RNF07 | Limitar corpos JSON a 64.000 bytes e validar limites dos textos e listas no servidor; escapar conteúdo exibido como HTML. |
| LOJ-RNF08 | Não guardar senha/token de sessão em `localStorage` nem coletar dados reais de cartão; seleção temporária pode ficar em `sessionStorage`. |
| LOJ-RNF09 | Migrar sem apagar dados e registrar cada versão uma única vez. Ao inicializar com migração pendente e veículos existentes, criar backup consistente em `data/backups/` antes de aplicar migrações. |
| LOJ-RNF10 | Servir loja, administração e APIs na mesma origem local em `127.0.0.1:8000`; servidor de apresentação separado usa a porta 8001. |
| LOJ-RNF11 | Persistir dados entre reinícios; armazenar horários em UTC e apresentar horários ao usuário em Brasília. |
| LOJ-RNF12 | Catálogo, cadastro, pedido e simulação não dependem de serviço externo. A consulta CNPJ do painel administrativo pode usar serviço externo, mas é opcional. |
| LOJ-RNF13 | Operador deve fazer backups periódicos manuais com o servidor parado, copiando `data/fasttruck.db` para outro local. O aplicativo não agenda essa rotina. |

## 7. Escopo, premissas e restrições

Premissas: empresas brasileiras com CNPJ; estoque administrado localmente; navegador com JavaScript e cookies habilitados; uso para estudo e execução local.

Fora do escopo: recuperação de senha por e-mail, confirmação de e-mail/titularidade, mais de uma conta por empresa, compartilhamento/sincronização entre instalações, frete, impostos, descontos, parcelas, nota fiscal, entrega, estorno, gateway, cobrança ou hospedagem pública. CNPJ válido matematicamente não comprova representação legal. Cadastro público não vincula uma empresa preexistente; para criar acesso, o CNPJ precisa estar disponível.

Backup automático ocorre somente antes de migrações pendentes e apenas quando há veículos cadastrados. Backup periódico manual é procedimento operacional, não tarefa agendada pelo programa.

## 8. Riscos e respostas

| ID | Risco | Tratamento |
|---|---|---|
| LOJ-RIS01 | Cliente acessar pedido de outra empresa | Toda consulta usa `id` e `customer_id` da sessão; pedido alheio retorna 404. |
| LOJ-RIS02 | Cliente alterar preço ou descrição | API aceita IDs e quantidades; backend consulta catálogo e recalcula total. |
| LOJ-RIS03 | Repetição de pedido/pagamento após falha de rede | Chaves UUID únicas, hash de requisição, transação e resposta idempotente. |
| LOJ-RIS04 | Simulação ser entendida como cobrança | Avisos na UI e comprovante dizem “sem valor financeiro”; não há dados reais de pagamento. |
| LOJ-RIS05 | Empresa real ser cadastrada por pessoa sem poderes | Validação CNPJ não verifica titularidade; verificação oficial está fora do escopo. |
| LOJ-RIS06 | Veículo mudar de disponibilidade | Conferir disponibilidade ao criar e aprovar pedido; não prometer reserva. |
| LOJ-RIS07 | Perda do banco ou senha admin inicial | Criar backup automático pré-migração e orientar backup periódico manual; preservar `data/.admin-access`. |
| LOJ-RIS08 | Exposição pública do servidor | Bind local em `127.0.0.1`; TLS e controles de implantação pública fora do escopo. |

## 9. Casos de uso e rastreabilidade

### LOJ-UC01 — Cadastrar empresa e iniciar sessão

**Ator:** visitante representante da empresa. **Pré-condição:** CNPJ e e-mail de conta ainda não utilizados. **Fluxo:** abre criar conta; informa CNPJ, dados empresariais e de contato, e-mail da conta e senha; backend valida e grava empresa/conta em transação; login inicia sessão e retorna usuário público e CSRF. E-mail da conta pode ser o e-mail de contato ou outro. **Alternativas:** validação ou unicidade falham, a operação é recusada sem associar a empresa antiga. **Pós-condição:** nova empresa ativa possui uma conta customer. **Rastreabilidade:** RF03–RF05, RF18; RN01–RN05, RN18; RNF03–RN07.

### LOJ-UC02 — Consultar e personalizar caminhão

**Ator:** visitante ou cliente. **Fluxo:** consulta catálogo público, pesquisa/ordena e abre detalhes; consulta opções fixas; escolhe opcionais e quantidades; confere preço estimado e notas. **Alternativas:** sem caminhão disponível, mostra estado vazio; se o veículo não estiver mais na lista, volta ao catálogo. Visitante precisa entrar para enviar pedido. **Pós-condição:** configuração pronta para confirmação. **Rastreabilidade:** RF01, RF02, RF06, RF07; RN06–RN10, RN15.

### LOJ-UC03 — Criar pedido

**Ator:** cliente autenticado. **Pré-condição:** empresa ativa, caminhão disponível e sessão válida. **Fluxo:** confirma um caminhão, IDs de adicionais, quantidades, notas e chave UUID; backend valida, relê preços, calcula total e snapshots e grava pedido/itens; apresenta pedido `Aguardando pagamento`. **Alternativas:** veículo indisponível, preço/total fora do limite, total zero, item inválido ou chave reutilizada com conteúdo diferente resulta em rejeição/conflito. Repetir mesma chave e intenção devolve pedido original. **Rastreabilidade:** RF08, RF18; RN06–RN12, RN15–RN17; RNF05–RN09.

### LOJ-UC04 — Simular pagamento e imprimir comprovante

**Ator:** empresa proprietária do pedido. **Pré-condição:** pedido aguardando pagamento. **Fluxo:** escolhe Pix/Boleto/Cartão e resultado explícito; envia apenas método, resultado e chave UUID; servidor revalida empresa ativa e disponibilidade se resultado for Aprovado, registra tentativa integral e atualiza status do pedido se aprovado; UI mostra histórico e comprovante para impressão. **Alternativas:** recusa/cancelamento de tentativa mantém pedido aguardando e aceita nova chave; veículo indisponível bloqueia aprovação; pagamento repetido com mesma chave/intenção não gera tentativa duplicada. **Pós-condição:** histórico de simulação preservado, sem cobrança. **Rastreabilidade:** RF10–RF13, RF18; RN07, RN10, RN12–RN15; RNF04–RN08.

### LOJ-UC05 — Consultar ou cancelar pedido

**Ator:** cliente autenticado. **Fluxo:** abre Meus pedidos, lista os próprios registros, consulta detalhes, itens, snapshots e pagamentos; pode cancelar enquanto não houver aprovação. **Alternativas:** pedido alheio ou inexistente retorna 404; pedido aprovado não pode ser cancelado; pedido cancelado mantém detalhes e histórico. **Rastreabilidade:** RF09, RF14, RF18; RN11–RN17; RNF05–RN07.

### LOJ-UC06 — Administrar loja e pedidos

**Ator:** administrador. **Pré-condição:** conta admin autenticada. **Fluxo:** entra por `/admin`, mantém veículos/empresas e usa a tela Pedidos da loja para listar, pesquisar e abrir pedidos/tentativas. **Alternativas:** visitante que abre página administrativa é redirecionado ao acesso; API retorna 401 sem sessão, 403 para cliente autenticado sem papel admin e 403 para falha de autorização/CSRF; vínculo com empresa/pedido/caminhão bloqueia exclusão incompatível. **Rastreabilidade:** RF15–RF18; RN05, RN17–RN18; RNF04–RN06.

## 10. Validação e aceite

O registro de validação anterior documenta 17 testes aprovados para os módulos administrativos de clientes, propostas e pagamentos antes da evolução de autenticação e checkout. Esses resultados são históricos e não demonstram cobertura ou aceite da loja, das contas, das sessões ou dos pedidos.

Critérios de aceite da loja: cadastro e login/logout de cliente/admin; persistência e expiração de sessão; catálogo apenas com veículos disponíveis; cálculo usando dois adicionais; rejeição de preço/descrição enviados pelo cliente; isolamento de pedidos entre empresas; tentativa recusada seguida de aprovada; idempotência; cancelamento permitido/bloqueado; bloqueio de cliente inativo; autorização administrativa; persistência após reinício; navegação em mobile e comprovante. Critérios listados são expectativas de validação, não resultados reportados.
