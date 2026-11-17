# FasTruck — Requisitos do módulo de clientes PJ

Data: 16/11/2026. Status: implementado. Cobertura de aceite e limites no [relatório de validação](VALIDACAO-MODULOS.md).

Este documento descreve a gestão administrativa de empresas. A empresa também pode criar sua conta e fazer pedidos na [área do cliente](REQUISITOS-AREA-CLIENTE.md); esse fluxo é separado das propostas administrativas. Empresa vinculada a conta, pedido ou proposta não pode ser excluída nem ter o CNPJ alterado. Inativar uma empresa bloqueia seu acesso à loja.

Documento integrante do [plano dos novos módulos](PLANO-NOVOS-MODULOS.md). Aplicam-se também COM-RNF01 a COM-RNF15 definidos no plano.

## 1. Objetivo e escopo

Cadastrar empresas interessadas nos caminhões da FasTruck, consultar CNPJ opcionalmente e permitir que propostas administrativas e pedidos da loja referenciem essas empresas. Incluir cadastro, consulta, edição, inativação, reativação e exclusão de empresas sem vínculos.

Ator administrativo: operador autenticado como administrador. Ator cliente: empresa autenticada, apenas para autocadastro e uso de sua área própria. Ator externo: BrasilAPI, usada somente para consulta de dados empresariais. As rotas administrativas de clientes exigem sessão de administrador; clientes não recebem acesso a essas rotas.

## 2. Dados do cadastro

| Campo | Obrigatoriedade e limite | Regra |
|---|---|---|
| ID | Automático | Identificador estável gerado pelo servidor. |
| CNPJ | Obrigatório, 14 posições após normalização | Texto, aceitando padrão numérico e alfanumérico; único no banco. |
| Razão social | Obrigatório, 2 a 160 caracteres | Remover espaços das extremidades. |
| Nome fantasia | Opcional, até 160 caracteres | Não substitui a razão social. |
| Nome do responsável | Obrigatório, 2 a 120 caracteres | Contato comercial; sem CPF ou documentação pessoal. |
| Telefone | Obrigatório, 10 ou 11 dígitos após normalização | Número nacional com DDD; pontuação é apenas apresentação. |
| E-mail | Obrigatório, até 254 caracteres | Validação básica de estrutura; não comprova que a caixa postal existe. |
| CEP | Obrigatório, 8 dígitos | Normalizado sem pontuação; sem consulta de CEP nesta etapa. |
| Logradouro | Obrigatório, 2 a 160 caracteres | Endereço informado ou revisado pelo operador. |
| Número | Obrigatório, até 20 caracteres | Texto; aceitar `s/n`. |
| Complemento | Opcional, até 100 caracteres | Texto livre. |
| Bairro / cidade | Obrigatórios, 2 a 100 caracteres cada | Endereço brasileiro. |
| UF | Obrigatória, 2 letras | Uma das 27 siglas válidas. |
| Observações | Opcional, até 1.000 caracteres | Somente informação comercial necessária. |
| Ativo | Automático na criação; alterável por ação específica | Ativo ou Inativo, independente da situação cadastral externa. |
| Origem e data da consulta | Automáticas, opcionais | Registrar BrasilAPI e horário apenas quando houver consulta bem-sucedida associada ao CNPJ atual. |
| Situação cadastral consultada | Opcional, somente leitura | Informação externa com data; não representa certificação pelo FasTruck. |
| Criado em / atualizado em | Automáticos | Datas do servidor. |
| Conta da loja | Criada no autocadastro | E-mail de acesso normalizado, distinto do e-mail de contato se necessário; senha armazenada como hash e nunca devolvida pela API. A conta pertence a uma única empresa. |

Campos obrigatórios não podem ser compostos apenas por espaços. Não armazenar o JSON completo da consulta nem dados de sócios; guardar apenas os campos usados acima.

## 3. Requisitos funcionais

| ID | Requisito |
|---|---|
| CLI-RF01 | Cadastrar empresa preenchendo os campos manualmente. |
| CLI-RF02 | Validar CNPJ no navegador para feedback e obrigatoriamente no servidor antes de cadastrar, alterar ou consultar. |
| CLI-RF03 | Consultar a BrasilAPI por ação explícita “Consultar CNPJ” e oferecer preenchimento de dados empresariais retornados. |
| CLI-RF04 | Preservar campos já preenchidos ao consultar; pedir confirmação antes de sobrescrever e exigir revisão antes de salvar. |
| CLI-RF05 | Listar empresas e pesquisar por CNPJ, razão social, nome fantasia ou responsável; filtrar Ativo, Inativo ou Todos. |
| CLI-RF06 | Exibir detalhes, contato, endereço e origem/data da última consulta associada ao CNPJ atual. |
| CLI-RF07 | Editar dados de empresa existente mantendo o ID e revalidando campos e unicidade. |
| CLI-RF08 | Inativar e reativar empresa mediante confirmação. |
| CLI-RF09 | Excluir fisicamente empresa sem conta, pedido ou proposta vinculados, com confirmação; bloquear exclusão quando houver qualquer desses vínculos. |
| CLI-RF10 | Rejeitar cadastro ou alteração com CNPJ duplicado, inclusive com outra formatação ou letras em caixa diferente. |
| CLI-RF11 | Informar documento inválido, duplicidade, ausência de dados na consulta e falhas externas sem apagar o formulário. |
| CLI-RF12 | Manter o cadastro manual disponível quando a consulta externa falhar ou estiver sem internet. |
| CLI-RF13 | Disponibilizar cliente ativo para seleção em novas propostas e mostrar suas propostas vinculadas nos detalhes. |
| CLI-RF14 | Persistir cadastros e datas no SQLite e oferecer endpoints de cadastro, consulta, edição e exclusão. |

## 4. Regras de negócio

| ID | Regra |
|---|---|
| CLI-RN01 | Aceitar somente PJ com CNPJ; CPF não faz parte do cadastro. |
| CLI-RN02 | Remover apenas espaços e separadores esperados (`.`, `/`, `-`), converter letras para maiúsculas e rejeitar outros caracteres. Validar 12 posições A–Z/0–9 seguidas de 2 dígitos, incluindo cálculo dos verificadores conforme referência oficial. |
| CLI-RN03 | Rejeitar CNPJ vazio, comprimento incorreto, verificadores inválidos e sequências numéricas repetidas; preservar zeros iniciais como texto. |
| CLI-RN04 | CNPJ normalizado possui restrição UNIQUE. Empresas com filiais podem ter cadastros separados, desde que o CNPJ completo seja diferente. |
| CLI-RN05 | Validação matemática não comprova existência, titularidade ou situação cadastral. Não exibir “validado na Receita” só porque o dígito confere. |
| CLI-RN06 | Consulta externa não é condição de cadastro. Situação retornada pela BrasilAPI deve gerar informação ao operador, sem mudar Ativo/Inativo nem validar crédito. |
| CLI-RN07 | Dados retornados são sugestões revisáveis; campos obrigatórios ausentes devem ser preenchidos pelo operador. Consultar não salva o cliente automaticamente. |
| CLI-RN08 | Razão social, contato e endereço completos da seção 2 são obrigatórios para salvar. Nome fantasia, complemento e observações são opcionais. |
| CLI-RN09 | Cliente nasce Ativo. Inativo não pode entrar na loja, fazer pedido, ser escolhido para nova proposta, nem ter proposta enviada/aprovada ou pagamento criado/aprovado; consultas, cancelamentos, recusas e histórico administrativos continuam disponíveis. |
| CLI-RN10 | Inativar não exclui nem cancela propostas, pedidos ou pagamentos existentes. Reativar libera ações futuras, respeitando as demais regras. |
| CLI-RN11 | Não excluir empresa com conta, pedido ou proposta de qualquer status. Oferecer inativação e explicar o vínculo. |
| CLI-RN12 | Alteração do cadastro não modifica as cópias já congeladas de propostas enviadas nem os dados copiados para pedidos da loja. Propostas em elaboração usam os dados atuais no envio. |
| CLI-RN13 | CNPJ pode ser corrigido somente enquanto não houver conta, pedido ou proposta vinculados. Depois, a identidade é bloqueada; para outra empresa deve haver outro cadastro. |
| CLI-RN14 | Alterar CNPJ antes de existir vínculo limpa metadados/situação da consulta anterior. Uma resposta atrasada para outro CNPJ não pode preencher nem marcar o cadastro atual como consultado. |
| CLI-RN15 | Criação e atualização registram datas pelo servidor; o operador não pode editar ID, datas ou metadados de consulta diretamente. |

## 5. Requisitos não funcionais específicos

| ID | Requisito |
|---|---|
| CLI-RNF01 | Fazer a consulta externa no backend com URL de origem fixa, HTTPS, CNPJ validado e timeout de 5 segundos; não aceitar URL fornecida pelo navegador. |
| CLI-RNF02 | Haver no máximo uma consulta em andamento por formulário; o botão fica desabilitado até terminar, sem consulta automática a cada caractere e sem repetição automática. |
| CLI-RNF03 | Em timeout, resposta inesperada, limite de requisições ou falha de rede, mostrar mensagem recuperável e preservar todos os campos manuais. |
| CLI-RNF04 | Tratar conteúdo externo como não confiável, limitar tamanho da resposta a 1 MB e mapear somente os campos do cadastro. Não renderizar HTML retornado. |
| CLI-RNF05 | Datas da consulta são armazenadas em UTC e mostradas no horário de Brasília. Diferenciar situação da empresa, resultado da consulta e status interno do cliente. |

O servidor cria automaticamente uma cópia do SQLite antes de aplicar migrações pendentes quando a base já contém veículos. A aplicação não agenda cópias periódicas: a rotina operacional deve fazer cópias manuais regulares e verificar sua recuperação.

## 6. Premissas

- O operador administra cadastros e propostas; o cliente usa uma área autenticada separada para seus pedidos.
- Operador conhece ou revisa os dados da empresa e possui um contato comercial para informar.
- Cadastro é local e brasileiro, com um telefone nacional principal e um endereço principal.
- A consulta depende da disponibilidade e atualização da BrasilAPI; dados incompletos não impedem preenchimento manual.
- A validação local aceita CNPJ numérico e alfanumérico; a consulta externa depende do suporte e da disponibilidade do provedor.

## 7. Restrições

- Sem clientes PF, validação de CPF, consulta de crédito, confirmação de titularidade ou verificação documental dos poderes de representação do responsável.
- Sem importação em lote, múltiplos endereços, múltiplos contatos, consulta de CEP ou coleta de dados de sócios.
- Sem integração direta paga com Receita/Serpro, automação de consultas em massa ou envio automático de mensagens.
- As rotas administrativas de clientes, propostas e pagamentos exigem sessão de administrador; a área da loja usa a conta vinculada à empresa e não expõe essas operações administrativas.

## 8. Riscos e respostas

| ID | Risco | Resposta nesta etapa |
|---|---|---|
| CLI-RIS01 | API indisponível, limitada ou lenta | Timeout, consulta explícita, mensagem recuperável e cadastro manual offline. |
| CLI-RIS02 | Informação externa desatualizada ou incompleta | Mostrar origem/data e exigir revisão; não certificar situação cadastral. |
| CLI-RIS03 | Mesmo CNPJ com máscaras distintas | Normalização no servidor e unicidade no SQLite. |
| CLI-RIS04 | Rejeitar documento com letras ou perder zeros | Campo textual e validação dos dois formatos. |
| CLI-RIS05 | Apagar histórico comercial | Restringir exclusão, manter vínculos e oferecer inativação. |
| CLI-RIS06 | Sobrescrever dados por consulta atrasada | Conferir CNPJ atual antes de aplicar resposta e confirmar substituições. |

## 9. Casos de uso

### CLI-UC01 — Cadastrar empresa manualmente

**Ator:** administrador. **Pré-condições:** sessão administrativa, servidor iniciado e base acessível.

1. Abrir Clientes e acionar “Nova empresa”.
2. Informar CNPJ, razão social, contato e endereço; preencher opcionais se necessário.
3. Salvar; a API normaliza e valida os dados e verifica unicidade.
4. O sistema grava cliente Ativo, ID e datas e atualiza a listagem.

**Alternativas:** documento/campos inválidos ou CNPJ duplicado retornam erro sem gravar; falha no banco não confirma sucesso. Não exige internet.

**Pós-condição:** empresa disponível para proposta. **Vínculos:** CLI-RF01–02, CLI-RF10–12, CLI-RF14; CLI-RN01–05, CLI-RN08, CLI-RN15; CLI-RIS03–04.

### CLI-UC02 — Consultar CNPJ e completar cadastro

**Ator principal:** administrador. **Secundário:** BrasilAPI. **Pré-condições:** sessão administrativa e CNPJ localmente válido.

1. Acionar “Consultar CNPJ”. O backend consulta a origem configurada.
2. Exibir sugestões de razão social, nome fantasia, endereço e situação quando disponíveis.
3. Confirmar substituição se já houver campos preenchidos e revisar o resultado.
4. Completar campos obrigatórios e salvar pelo fluxo CLI-UC01 ou CLI-UC04.

**Alternativas:** não encontrado, limite, timeout ou formato de resposta inesperado mostram mensagem; o operador continua manualmente. Resposta de um CNPJ anterior é descartada. Consultar sem salvar não cria cliente.

**Pós-condição:** formulário revisado; se salvo, metadados da consulta associados ao CNPJ correto. **Vínculos:** CLI-RF03–04, CLI-RF06, CLI-RF11–12; CLI-RN05–07, CLI-RN14; CLI-RNF01–05; CLI-RIS01–02, CLI-RIS06.

### CLI-UC03 — Localizar empresa e consultar histórico

**Ator:** administrador. **Pré-condição:** sessão administrativa.

**Fluxo:** listar → pesquisar empresa/CNPJ/responsável → filtrar status → abrir detalhes → consultar endereço, contato, consulta externa e propostas vinculadas.

**Alternativas:** lista vazia informa ausência; erro de conexão permite tentar novamente sem alterar dados. **Pós-condição:** nenhum registro alterado.

**Vínculos:** CLI-RF05–06, CLI-RF13–14; CLI-RN06, CLI-RN12; CLI-RNF05.

### CLI-UC04 — Editar, inativar ou reativar empresa

**Ator:** administrador. **Pré-condição:** empresa existente.

**Fluxo de edição:** abrir cadastro → alterar dados permitidos → salvar → revalidar → manter ID e atualizar data.

**Fluxo de status:** solicitar Inativar/Reativar → confirmar → persistir → atualizar disponibilidade para propostas.

**Alternativas:** impedir alteração de CNPJ com conta, pedido ou proposta vinculados; rejeitar duplicidade ou campo inválido. Cancelar confirmação não altera status. Inativação não apaga histórico nem muda os estados de propostas/pagamentos, mas bloqueia o acesso à área do cliente.

**Pós-condição:** cadastro ou status atualizado. **Vínculos:** CLI-RF07–08, CLI-RF10, CLI-RF13–14; CLI-RN08–10, CLI-RN12–15.

### CLI-UC05 — Excluir empresa sem vínculos

**Ator:** administrador. **Pré-condição:** empresa existente sem conta, pedido ou proposta.

**Fluxo:** solicitar exclusão → confirmar → servidor revalida ausência de vínculo → remover cadastro → atualizar lista.

**Alternativas:** se existir conta, pedido ou proposta, retornar conflito e orientar inativação; cancelar não remove; erro de banco não confirma exclusão.

**Pós-condição:** cliente sem vínculos removido ou operação bloqueada. **Vínculos:** CLI-RF09, CLI-RF14; CLI-RN11; CLI-RIS05.

## 10. Endpoints previstos

| Método e rota | Finalidade |
|---|---|
| `GET /api/customers` | Listar; pesquisa e filtros podem ocorrer no frontend nesta escala. |
| `POST /api/customers` | Criar, retornando 201. |
| `GET /api/customers/{id}` | Detalhar e informar propostas vinculadas. |
| `PUT /api/customers/{id}` | Editar os campos permitidos, inclusive ação explícita de ativo/inativo. |
| `DELETE /api/customers/{id}` | Remover somente sem vínculos. |
| `GET /api/cnpj/{cnpj}` | Validar e consultar o provedor pelo backend. |

As rotas administrativas desta seção exigem cookie de sessão válido com papel `admin`. Obter o token CSRF por `GET /api/shop/session` e enviá-lo em `X-CSRF-Token` nos métodos `POST`, `PUT` e `DELETE`. A API retorna 401 sem sessão válida, 403 para papel insuficiente, token CSRF inválido ou origem recusada, e 405 para método não permitido. A área da empresa usa rotas próprias e não concede acesso aos cadastros administrativos; senhas nunca são devolvidas pela API.

Erros locais usam COM-RNF10. Na consulta CNPJ, devolver 404 se a origem indicar empresa não encontrada, 503 para limite/indisponibilidade, 504 para timeout e 502 para resposta externa inválida. Não converter esses erros em “CNPJ inválido” ou “empresa inexistente”.

## 11. Critérios de aceite

- Cadastrar PJ manualmente sem internet; impedir registro com CPF, CNPJ inválido ou repetido.
- Aceitar documento numérico e alfanumérico com dígitos corretos e preservar zeros iniciais.
- Consultar empresa sem salvar automaticamente; preservar formulário em falha e confirmar sobrescrita de campos.
- Não aplicar resposta externa quando o CNPJ do formulário tiver mudado.
- Pesquisar e filtrar empresas, editar contato e manter o ID.
- Inativar/reativar sem apagar propostas ou pedidos; impedir login e uso comercial enquanto inativo.
- Excluir empresa sem conta, pedido ou proposta; bloquear empresa com qualquer vínculo, inclusive proposta cancelada.
- Mostrar propostas antigas com seus dados congelados depois de editar o cliente.
- Atender requisitos comuns de persistência, acessibilidade, validação no servidor e segurança de conteúdo.

## 12. Referências

O [plano geral, seção 12](PLANO-NOVOS-MODULOS.md#12-fontes-da-integração-cnpj) registra as fontes da BrasilAPI e da Receita Federal para consulta, formatos e verificadores. Consulta cadastral e validação local têm finalidades diferentes.
