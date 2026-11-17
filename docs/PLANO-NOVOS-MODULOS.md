# FasTruck — Plano e evolução dos módulos

Data: 16/11/2026. Este documento registra a arquitetura e o planejamento dos módulos administrativos e a evolução posterior para contas, loja e pedidos. Ele distingue os fluxos já definidos para cada área e não transforma ideias futuras em requisitos da entrega atual.

## 1. Objetivo e contexto

A primeira ampliação do cadastro de veículos organizou três módulos administrativos relacionados: clientes PJ, propostas com personalizações e pagamentos simulados. Uma evolução posterior acrescentou autenticação de cliente e administrador, loja pública e checkout de pedido com pagamento simulado. A raiz do servidor agora abre a loja; o painel protegido fica em `/admin`.

Os módulos compartilham Python, SQLite, HTML, CSS e JavaScript. Cadastro de veículos e regras de propostas continuam administrativos. O checkout da loja é um segundo processo comercial, com estrutura, estados e APIs próprios.

## 2. Documentos de requisitos

Os documentos específicos preservam os requisitos e casos de uso de cada área:

- [Clientes PJ](REQUISITOS-CLIENTES-PJ.md).
- [Propostas e personalizações](REQUISITOS-PROPOSTAS-PERSONALIZACOES.md).
- [Pagamentos simulados de propostas](REQUISITOS-PAGAMENTOS-SIMULADOS.md).
- [Cadastro de veículos](REQUISITOS-CADASTRO-VEICULOS.md).
- [Área do cliente e pedidos da loja](REQUISITOS-AREA-CLIENTE.md).
- [Registro histórico de validação dos módulos administrativos](VALIDACAO-MODULOS.md).

Os documentos dos módulos administrativos descrevem o fluxo operacional de propostas. O documento da área do cliente especifica conta, catálogo, pedido e pagamento simulado da loja. Requisitos de um fluxo não implicam comportamento equivalente no outro.

## 3. Fluxos e limites de negócio

### 3.1 Processo administrativo

O operador cadastra ou consulta uma empresa, seleciona cliente ativo e caminhão disponível, cria proposta em elaboração, define personalizações e validade, registra envio/aprovação e, quando elegível, cria uma tentativa de pagamento simulada. Dados e preços da proposta são congelados conforme o estado do processo. O resultado financeiro não cobra, transfere ou altera o estoque.

### 3.2 Processo da loja

O visitante consulta caminhões disponíveis e personalizações com preço definido pelo servidor. Para confirmar, cria uma conta para uma empresa nova ou entra em conta existente. O cliente envia um caminhão, opcionais por ID, quantidades, notas e chave UUID. O servidor recalcula o total, grava snapshot e pedido, e disponibiliza pagamento integral simulado. O cliente consulta ou cancela seus próprios pedidos; a administração consulta pedidos pela tela própria.

Pedido da loja tem um caminhão e os estados `Aguardando pagamento`, `Pagamento aprovado` ou `Cancelado`. Tentativas da loja usam `Aprovado`, `Recusado` ou `Cancelado`; recusa/cancelamento mantém o pedido aguardando. Pedidos e pagamentos simulados não reservam nem vendem caminhões; aprovação revalida disponibilidade, sem alterar status do estoque. Propostas e pagamentos administrativos mantêm estados e regras próprios.

## 4. Dados e migrações

O esquema tem a tabela existente `vehicles`, o cadastro de empresas e cinco migrações em `sql/migrations/`:

| Migração | Dados e responsabilidade |
|---|---|
| `001_customers.sql` | Empresas em `customers`, com CNPJ, contato, endereço, situação e datas. |
| `002_proposals.sql` | `proposals`, `proposal_items` e `proposal_events`. |
| `003_payments.sql` | `payments` e `payment_events` do fluxo de propostas. |
| `004_shop_accounts.sql` | Contas em `accounts` e sessões em `shop_sessions`. Conta de cliente referencia uma empresa; conta admin não. |
| `005_shop_orders.sql` | Pedidos, itens e tentativas em `shop_orders`, `shop_order_items` e `shop_order_payments`. |

Os domínios financeiros são separados: `payments` tem chave estrangeira para proposta; `shop_order_payments` tem chave estrangeira para pedido. Ambos referenciam as tabelas comuns de empresas/veículos conforme aplicável. IDs de cliente, conta, pedido e proposta usam texto; valores monetários novos usam centavos inteiros. Snapshots guardam dados relevantes à época do registro. Chaves estrangeiras são ativadas em cada conexão e referências que precisam de histórico usam `ON DELETE RESTRICT`.

O inicializador cria/atualiza o esquema base e aplica migrações ainda não registradas em `schema_migrations`. As migrações pendentes são executadas em uma transação; falha interrompe a evolução inteira. Antes de aplicar migração pendente quando existem veículos, `db.py` cria uma cópia consistente do SQLite em `data/backups/`.

### 4.1 Backup operacional

O backup automático é uma proteção de atualização: é criado antes de migrações pendentes somente se houver veículos cadastrados. Ele não substitui rotina periódica. Para cópias manuais periódicas, interrompa o servidor com `Ctrl+C` e copie `data/fasttruck.db` para outro local; o programa não agenda essa tarefa. Preserve também `data/.admin-access` para poder usar as credenciais iniciais, e `data/.cnpj-lookup-key` se precisar manter válidos tokens locais de consulta CNPJ ainda não expirados. Esses arquivos locais não devem ser enviados ao Git.

## 5. Contratos de acesso e API

O login usa e-mail da conta e senha. Senhas são armazenadas em hash scrypt com salt; sessões usam tokens aleatórios, persistidos como hash, e expiram em sete dias. O navegador recebe cookie HttpOnly/SameSite=Lax e token CSRF para mutações. Cadastro público só cria conta `customer`. Se ainda não há administrador, inicialização cria conta local e grava a senha aleatória em `data/.admin-access`.

| API | Acesso e função |
|---|---|
| `GET /api/shop/catalog` | Público; lista veículos `Disponível` e seus campos cadastrais públicos. |
| `GET /api/shop/customizations` | Público; lista IDs, nomes e preços fixos no backend. |
| `POST /api/shop/register`, `POST /api/shop/login` | Criar empresa/conta ou autenticar; sessão via cookie. |
| `GET /api/shop/session`, `POST /api/shop/logout` | Ver sessão atual e encerrar sessão. |
| `GET /api/shop/account` | Cliente autenticado; retorna a própria empresa. |
| `GET/POST /api/shop/orders` | Cliente autenticado; listar seus pedidos ou criar pedido de um caminhão. |
| `GET /api/shop/orders/{id}` | Cliente autenticado; detalhes somente se o pedido lhe pertencer; caso contrário, 404. |
| `POST /api/shop/orders/{id}/payment` | Cliente dono; recebe método, resultado escolhido e chave UUID, sem dados de cartão. |
| `POST /api/shop/orders/{id}/cancel` | Cliente dono; cancela se ainda não há tentativa aprovada. |
| `GET /api/shop/admin/orders` | Administrador; lista pedidos e seus itens/tentativas. |
| APIs fora de `/api/shop/` | Exigem sessão de administrador. |

Pedido aceita `vehicle_id`, `items`, `notes` e `idempotency_key`. Cada item contém exclusivamente `customization_id` e `quantity`; valor/descrição vêm do backend. Quantidade é inteira 1–100, sem personalização repetida, até 30 itens por requisição; o catálogo atual contém seis opções e a interface oferece 1–10. Observações aceitam até 2.000 caracteres. Preço-base e total têm limite de R$ 99.999.999,99; total deve ser positivo. Idempotência usa UUID e hash da intenção normalizada. A resposta não expõe a chave nem o hash.

Uma tentativa de pagamento da loja aceita exatamente `method`, `result` e `idempotency_key`. Métodos: `Pix`, `Boleto` e `Cartão`; resultados: `Aprovado`, `Recusado` e `Cancelado`. O total integral do pedido é gravado; apenas uma tentativa aprovada por pedido é permitida. A tela de pagamento explica que o resultado é simulado e sem valor financeiro.

## 6. Requisitos técnicos comuns

| ID | Decisão de implementação |
|---|---|
| COM-RNF01 | Manter a aplicação local em `127.0.0.1:8000`, com interface e API na mesma origem e sem dependências Python externas obrigatórias. A apresentação separada usa a porta 8001. |
| COM-RNF02 | Manter telas utilizáveis a partir de 360 px, com rótulos, navegação por teclado, foco visível e mensagens de sucesso/erro acessíveis. |
| COM-RNF03 | Validar regras no servidor, inclusive requisições sem passar pelo formulário; entradas inválidas recebem mensagem apropriada. |
| COM-RNF04 | Usar parâmetros nas consultas SQL e escapar texto ao renderizar HTML; entradas de operador/serviço externo não viram HTML executável. |
| COM-RNF05 | Gravar operações relacionadas em transação; falha de item, evento ou atualização deve desfazer a operação toda. A loja abre transações de escrita com `BEGIN IMMEDIATE`. |
| COM-RNF06 | Preservar veículos e cadastros existentes na migração; aplicar alterações uma vez por versão e criar backup automático antes de migrações pendentes se houver veículos. |
| COM-RNF07 | Representar novos valores em centavos inteiros e cálculos com inteiros/Decimal; rejeitar NaN, infinito e frações abaixo de um centavo quando aplicável. |
| COM-RNF08 | Impedir duplicidades e transições concorrentes no banco, inclusive duplo clique e requisições simultâneas; desabilitar o botão durante o envio. Pedidos da loja não reservam estoque. |
| COM-RNF09 | Persistir IDs estáveis e datas em UTC, apresentando horários de Brasília. Validade comercial de proposta usa data de Brasília e permanece válida até o fim do dia informado. |
| COM-RNF10 | Usar 201 para cadastro, 200 para consultas/alterações/encerramento, 400 para entrada inválida, 401 sem sessão/autenticação, 403 para papel/permissão/CSRF insuficientes, 404 para registro inexistente, 405 para método não aceito, 409 para conflito de vínculo/unicidade/estado e 503 para SQLite temporariamente indisponível. Páginas administrativas redirecionam visitante ao acesso; erros internos não expõem traceback/caminhos. |
| COM-RNF11 | Limitar texto, listas e corpos JSON no servidor a 64.000 bytes. Proposta e pedido admitem no máximo 30 itens na API; a UI da loja apresenta até 10 unidades por personalização. |
| COM-RNF12 | Não registrar corpos completos, contatos, senhas ou dados externos desnecessários em logs. Não coletar CPF nem dados reais de cartão. Senhas pertencem somente à autenticação e são armazenadas como hash no banco; o acesso inicial de administrador é disponibilizado em arquivo local ignorado pelo Git. |
| COM-RNF13 | Sem migração destrutiva ou redefinição da carga inicial; base sobrevive a paradas/reinicializações. Fazer cópias manuais periódicas com servidor parado; antes de migração pendente em base com veículos há cópia automática. |
| COM-RNF14 | Critérios de aceite incluem operação sem internet para fluxos locais, validação direta na API, persistência após reinício e falhas de gravação, conforme cada documento. Histórico de testes administrativos não representa aceite da loja. |
| COM-RNF15 | Meta de planejamento local: com até 1.000 registros por módulo, listagem, pesquisa e salvamento até 2 segundos no computador de aceite, sem consulta externa. A meta não é uma medição nem garantia já aferida para a loja. |

## 7. Estrutura do projeto

```text
sql/
├── schema.sql
└── migrations/                 # cinco versões incrementais
src/
├── backend/
│   ├── app.py                   # servidor, sessão, autorização e roteamento
│   ├── db.py                    # conexão, backup pré-migração e transações
│   ├── common.py                # validações compartilhadas
│   ├── services/                # clientes, propostas, pagamentos, autenticação e pedidos
│   └── integrations/             # consulta CNPJ opcional
└── frontend/
    ├── loja.html                 # página inicial pública
    ├── index.html                # painel de veículos em /admin
    ├── clientes.html
    ├── propostas.html
    ├── pagamentos.html
    ├── pedidos.html              # consulta administrativa de pedidos da loja
    ├── css/
    └── js/
```

Os bancos, credenciais locais e backups ficam em `data/`, fora do controle de versão. Os documentos de requisitos e validação ficam em `docs/`.

## 8. Sequência do planejamento

| Etapa | Escopo planejado | Resultado esperado |
|---|---|---|
| 1 — Base e preservação | Utilitários, migrações versionadas, navegação e cópia prévia à migração. | Cadastro de veículos e dados antigos permanecem disponíveis. |
| 2 — Clientes PJ | CRUD administrativo, inativação, validação CNPJ e consulta externa opcional. | Cadastro manual funciona sem depender da consulta. |
| 3 — Propostas | Empresa/veículo, itens, cálculos, validade, estados, snapshots e eventos. | Proposta administrativa mantém histórico e valida elegibilidade. |
| 4 — Pagamentos de proposta | Tentativas derivadas de proposta aprovada, estados, idempotência e comprovante. | Uma única tentativa ativa por proposta; sem dados financeiros reais. |
| 5 — Integração administrativa | Proteções de vínculo e fluxo de UI entre cadastros, propostas e pagamentos. | Dados persistem e simulação não altera estoque. |
| 6 — Evolução de acesso e loja | Contas de cliente/admin, sessões, catálogo, personalizações fixas, pedidos e pagamentos simulados da loja. | Conta do cliente isolada e pedidos separados do processo de proposta. |
| 7 — Documentação operacional | Instruções de execução, credenciais iniciais, backups e escopo dos módulos. | Operador consegue iniciar, acessar e preservar os dados. |

As etapas registram a sequência de planejamento; a presença de uma entrega na tabela não é resultado de teste. Critérios de validação e seus limites ficam documentados separadamente.

## 9. Integração com cadastro de veículos

| ID | Regra de integração |
|---|---|
| INT-RF01 | Impedir exclusão de veículo vinculado a proposta ou pedido, na interface e no banco/API. |
| INT-RF02 | Alterações do cadastro de cliente/veículo não reescrevem snapshots nem valores já copiados para proposta/pedido. |
| INT-RF03 | Proposta revalida elegibilidade nas transições comerciais/financeiras definidas em seu documento; pedido da loja revalida cliente ativo e veículo disponível ao criar, e disponibilidade antes de aprovar tentativa. |
| INT-RF04 | Valores simulados não entram nos indicadores do estoque nem mudam status para Reservado/Vendido automaticamente. |

As exceções e regras específicas de exclusão por vínculo constam em [requisitos de veículos](REQUISITOS-CADASTRO-VEICULOS.md).

## 10. Premissas, limites e riscos

Premissas: Python 3.10 ou superior, banco SQLite gravável e uso local. Consulta externa se limita à consulta CNPJ opcional; fluxo de autenticação, catálogo, pedidos e pagamentos simulados é local.

Limites atuais: sem recuperação de senha por e-mail, confirmação de e-mail ou titularidade de CNPJ, mais de uma conta por empresa, sincronização entre instalações, frete, imposto, nota fiscal, entrega, gateway, cobrança real ou hospedagem pública. CNPJ é validado matematicamente, não como prova de representação legal. A loja não reserva estoque.

| Risco | Tratamento |
|---|---|
| Perda ao evoluir o banco | Migrações transacionais, backup automático antes de migração pendente com veículos e rotina manual periódica. |
| Consulta CNPJ indisponível | Consulta opcional; manter cadastro manual e comunicar origem/horário quando consultado. |
| Divergência entre preço exibido e enviado | O backend reconsulta o catálogo e recalcula o pedido; revalidar disponibilidade antes de aprovar. |
| Acesso cruzado a pedido | Filtrar por empresa autenticada e retornar 404 para pedido de outra empresa. |
| Simulação ser interpretada como cobrança | Mensagens na etapa financeira, histórico e comprovante informam que não há valor financeiro. |
| Exposição como serviço público | Servidor escuta em loopback; preparação de produção, TLS e hospedagem pública não fazem parte deste escopo. |

## 11. Validação histórica e rastreabilidade

O [registro de validação](VALIDACAO-MODULOS.md) relata uma execução anterior de 17 testes dos módulos administrativos de clientes, propostas, pagamentos e migrações daquela etapa. Essa execução antecede ou não especifica cobertura suficiente para as mudanças de login, sessões, checkout e pedidos da loja; não deve ser interpretada como aceite desses fluxos. Os critérios para conta e loja estão em [requisitos da área do cliente](REQUISITOS-AREA-CLIENTE.md), seção 10.

Rastreabilidade por fluxo:

| Fluxo | Requisitos relacionados |
|---|---|
| Cadastro e manutenção de empresa | [Clientes PJ](REQUISITOS-CLIENTES-PJ.md), mais RF03–RF05 e RN01–RN05 da área do cliente para conta/sessão. |
| Proposta e personalizações digitadas | [Propostas e personalizações](REQUISITOS-PROPOSTAS-PERSONALIZACOES.md); mantém suas tabelas e regras administrativas. |
| Pagamento simulado de proposta | [Pagamentos simulados](REQUISITOS-PAGAMENTOS-SIMULADOS.md); separado de pagamento da loja. |
| Pedido e pagamento simulado da loja | [Área do cliente](REQUISITOS-AREA-CLIENTE.md), RF06–RF16, RN06–RN17 e casos de uso LOJ-UC02–LOJ-UC06. |
| Estoque e exclusão por vínculos | [Cadastro de veículos](REQUISITOS-CADASTRO-VEICULOS.md) e INT-RF01–INT-RF04 acima. |

## 12. Evoluções futuras (fora do escopo atual)

Os seguintes itens não são comportamento entregue nem critério de aceite atual. Exigiriam planejamento e requisitos próprios antes de implementação: recuperação de senha, verificação de titularidade de empresa, múltiplos usuários por empresa, reserva concorrente de estoque, integração real com pagamento, operação hospedada/publicamente acessível, frete/entrega/faturamento e replicação de contas ou pedidos entre instalações.

## 13. Referências de consulta CNPJ

Referências usadas para planejar a validação de CNPJ e o contrato da consulta externa opcional. A disponibilidade e o suporte atual do provedor não são garantidos pelo aplicativo; o cadastro manual permanece possível.

- [BrasilAPI — especificação do endpoint CNPJ](https://github.com/BrasilAPI/BrasilAPI/blob/main/pages/docs/doc/cnpj.json).
- [Receita Federal — CNPJ alfanumérico](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/cnpj-alfanumerico).
- [Receita Federal/Serpro — cálculo dos dígitos verificadores](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj/manual-dv-cnpj.pdf).
