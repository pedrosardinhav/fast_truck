# FasTruck — Cadastro administrativo de veículos

Data: 16/11/2026. Documento do estoque administrativo. A loja e os pedidos de clientes são descritos em [Área do cliente](REQUISITOS-AREA-CLIENTE.md); propostas e pagamentos administrativos têm requisitos próprios.

## 1. Objetivo e escopo

Cadastrar e gerenciar caminhões da FasTruck, incluindo características, preço anunciado, situação do estoque e observações de personalização. O painel fica em `/admin` e exige conta de administrador; a raiz `/` é a loja pública e mostra apenas veículos Disponíveis.

HTML, CSS e JavaScript compõem a interface; Python e SQLite implementam a API e a persistência. Este módulo mantém o estoque; pedidos e pagamentos simulados não reservam ou vendem caminhões automaticamente.

## 2. Premissas e dados

- O administrador inicia `python src/backend/app.py` na raiz do projeto, acessa o servidor local e entra com suas credenciais.
- A primeira execução do servidor cria o acesso administrativo em `data/.admin-access`, ignorado pelo Git.
- A base padrão é `data/fasttruck.db`, criada localmente e ignorada pelo Git.
- Uma base nova recebe 13 caminhões de exemplo; as duas cargas são aplicadas uma vez e não recriam veículos excluídos.
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
| RF05 | Confirmar exclusão na interface e rejeitá-la se houver proposta ou pedido vinculado. |
| RF06 | Pesquisar por placa, marca ou modelo e filtrar por status na interface. |
| RF07 | Mostrar total de veículos, disponíveis, personalizados e soma do valor anunciado. |
| RF08 | Persistir e recuperar os cadastros no SQLite por meio da API Python. |
| RF09 | Mostrar mensagens de sucesso ou erro nas operações. |
| RF10 | Disponibilizar endpoints autenticados para listar, criar, atualizar e excluir veículos. |
| RF11 | Restringir painel e operações administrativas a contas autenticadas com papel de administrador. |

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
| RN08 | Exclusão depende de confirmação e ausência de qualquer proposta ou pedido vinculado, inclusive cancelados. A API/SQLite bloqueiam vínculos existentes. |
| RN09 | Indicadores representam todo o estoque, independentemente da busca/filtro; a soma anunciada inclui todos os status. |
| RN10 | Cargas iniciais usam metadados para execução única; não reinserem registros removidos pelo administrador. |
| RN11 | Alterações no estoque não reescrevem propostas enviadas ou pedidos já criados; propostas, pedidos e simulações não alteram automaticamente preço, personalizações ou status do caminhão. |

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

- Operação local; sem implantação pública, sincronização entre instalações ou preparação de produção.
- A existência de login não comprova titularidade do veículo ou dados empresariais.
- Sem consulta oficial de placa, documentação, procedência, valor de mercado ou especificações mecânicas.
- Sem upload de fotos, catálogo de acessórios editável ou reserva automática de caminhão nesta etapa.
- Loja, contas, propostas e pagamentos simulados pertencem a módulos relacionados; nenhuma parte processa dinheiro real.
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
| Excluir histórico comercial por remover caminhão | Bloquear exclusão por vínculo com proposta ou pedido; conservar snapshots históricos. |

## 8. Casos de uso

Todos os casos administrativos exigem servidor/banco disponíveis e sessão com papel de administrador.

### UC01 — Cadastrar caminhão

**Ator:** administrador. **Fluxo:** abre Novo caminhão → preenche campos obrigatórios e opcionais → confirma cadastro → API valida → SQLite grava → lista/indicadores são atualizados. **Alternativas:** placa inválida/duplicada, campos rejeitados ou falha de conexão/gravação mostram erro sem confirmar cadastro. **Pós-condição:** novo veículo persiste no estoque.

### UC02 — Consultar e localizar caminhão

**Ator:** administrador. **Fluxo:** abre painel → carrega lista da API → pesquisa placa/marca/modelo e filtra status. **Pós-condição:** lista filtrada; indicadores continuam representando o estoque inteiro, sem alterar registros.

### UC03 — Editar caminhão

**Ator:** administrador. **Pré:** veículo existe. **Fluxo:** aciona editar → formulário recebe valores atuais → altera e salva → API revalida e atualiza mesmo ID → lista e indicadores atualizam. **Alternativas:** dados rejeitados, placa duplicada ou falha de persistência não confirmam alteração. **Pós-condição:** estoque atualizado; propostas/pedidos históricos não são reescritos.

### UC04 — Excluir caminhão

**Ator:** administrador. **Pré:** veículo existe e não possui proposta/pedido vinculado. **Fluxo:** aciona excluir → interface pede confirmação → API remove pelo ID → lista/indicadores atualizam. **Alternativas:** Manter veículo, clique fora ou Esc encerram o diálogo sem excluir; vínculo com proposta/pedido faz a API rejeitar exclusão e manter o registro; ID inexistente retorna não encontrado. **Pós-condição:** apenas veículo elegível e confirmado é removido.

## 9. Rastreabilidade

| Caso | Requisitos e regras |
|---|---|
| UC01 | RF01, RF02, RF08–RF11; RN01–RN06, RN10; RNF03, RNF04, RNF06 |
| UC02 | RF03, RF06, RF07, RF08, RF10, RF11; RN09; RNF01, RNF02, RNF07 |
| UC03 | RF04, RF08–RF11; RN02, RN07, RN11; RNF05, RNF06 |
| UC04 | RF05, RF08–RF11; RN08, RN11; RNF05, RNF06 |

## 10. Contrato da API e critérios de aceite

| Método e rota | Finalidade |
|---|---|
| `GET /api/vehicles` | Listar todos os veículos para a administração. |
| `POST /api/vehicles` | Criar veículo. |
| `PUT /api/vehicles/{id}` | Atualizar veículo. |
| `DELETE /api/vehicles/{id}` | Excluir veículo sem vínculos. |
| `GET /api/shop/catalog` | Catálogo público somente de veículos Disponíveis. |

As quatro rotas administrativas exigem cookie de sessão admin; mutações exigem `X-CSRF-Token` obtido em `GET /api/shop/session`. Respostas incluem 401 sem sessão, 403 para papel ou CSRF/origem recusados, 400 para dados inválidos, 404 para ID inexistente e 409 para duplicidade/vínculo. A página administrativa redireciona visitante para entrar.

Critérios de aceite: criar/editar/consultar/excluir sem vínculo; rejeitar placa duplicada e preço negativo; manter dados após reinício; bloquear cliente comum na administração; preservar veículo vinculado a proposta ou pedido; manter snapshots e estoque sem alterações automáticas por simulação. Esses critérios são expectativas, não uma declaração de execução completa. Consulte o [registro de validação](VALIDACAO-MODULOS.md).
