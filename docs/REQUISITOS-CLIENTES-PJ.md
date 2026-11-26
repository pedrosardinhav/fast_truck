# FasTruck — Requisitos de clientes PJ

Data: 25/11/2026.

## Objetivo

Manter empresas que compram caminhões na FasTruck. O cadastro pode ser criado na loja pela própria empresa ou consultado pela administração. Pedidos, pagamentos e vendas usam o mesmo cliente PJ.

## Atores

- Visitante: cria a empresa e a conta pela loja.
- Cliente PJ: entra, consulta os próprios dados e realiza compras.
- Administrador: lista, pesquisa, edita, ativa ou inativa empresas e consulta seus vínculos.
- Serviço de CNPJ: auxilia opcionalmente o preenchimento; sua indisponibilidade não bloqueia o cadastro manual.

## Dados principais

CNPJ, razão social, nome fantasia, responsável, e-mail, telefone, endereço, status, datas de criação e atualização. A conta de acesso acrescenta e-mail de login e senha armazenada como hash. Bancos novos recebem sete empresas acadêmicas; a Transportadora Horizonte Azul possui a conta de compra documentada no README.

## Requisitos funcionais

| ID | Requisito |
|---|---|
| CLI-RF01 | Cadastrar empresa com dados fiscais, contato e endereço. |
| CLI-RF02 | Validar CNPJ numérico ou alfanumérico e impedir duplicidade. |
| CLI-RF03 | Permitir consulta opcional de CNPJ para auxiliar o preenchimento. |
| CLI-RF04 | Listar, pesquisar e filtrar empresas por status. |
| CLI-RF05 | Consultar detalhes e pedidos vinculados. |
| CLI-RF06 | Editar dados permitidos e manter histórico comercial existente. |
| CLI-RF07 | Inativar e reativar uma empresa. |
| CLI-RF08 | Criar empresa e conta em uma única operação pela loja. |
| CLI-RF09 | Bloquear exclusão de empresa com conta, pedido, pagamento ou venda. |
| CLI-RF10 | Disponibilizar empresa ativa para pedido e venda administrativa. |
| CLI-RF11 | Carregar empresas acadêmicas de forma idempotente, sem duplicar nem substituir cadastros existentes. |

## Regras de negócio

- CNPJ e e-mail de acesso são únicos.
- Validação matemática não comprova existência ou situação cadastral.
- Consulta externa é opcional; falha não impede cadastro manual.
- Empresa nasce Ativa.
- Empresa inativa não entra na loja, cria pedido ou recebe venda.
- Inativar não apaga conta, pedido, pagamento ou venda.
- CNPJ vinculado a conta ou histórico comercial não pode ser alterado.
- Dados atuais do cadastro não reescrevem snapshots de pedidos e vendas anteriores.
- Senha não é exibida ou retornada pela API.
- Cliente autenticado acessa somente a própria empresa e seus pedidos.
- A carga compartilhada usa CNPJs e contatos destinados ao estudo e não representa empresas reais.

## Requisitos não funcionais

- Validações críticas executadas no servidor.
- Senhas armazenadas com scrypt.
- Cookie de sessão HttpOnly e SameSite; CSRF nas mutações.
- Textos escapados antes de aparecer na interface.
- Datas persistidas em UTC.
- Interface administrativa e cadastro público responsivos.
- Consulta externa tem timeout e tratamento de indisponibilidade.

## Premissas, restrições e riscos

### Premissas

- A empresa fornece seus dados e mantém contato e endereço atualizados.
- Um CNPJ corresponde a uma conta nesta etapa.
- O administrador possui sessão válida para consultar o conjunto completo.
- A consulta de CNPJ pode estar indisponível, mas o usuário consegue preencher os dados manualmente.

### Restrições

- Sem confirmação de e-mail ou verificação de titularidade da empresa.
- Sem múltiplos usuários por empresa e sem recuperação de senha por e-mail.
- Sem sincronização de alterações entre instalações locais.
- A validação matemática do CNPJ não comprova existência, atividade ou propriedade.

| Risco | Tratamento |
|---|---|
| CNPJ digitado incorretamente | Normalização, dígitos verificadores e confirmação visual. |
| Serviço externo indisponível | Manter cadastro manual. |
| Empresa inativa continuar comprando | Revalidar status no login, pedido e venda. |
| Alteração apagar contexto histórico | Manter snapshots nos pedidos e vendas. |
| Empresa tentar acessar outra conta | Aplicar propriedade em todas as consultas da loja. |

## Casos de uso

### CLI-UC01 — Criar conta PJ

**Ator:** visitante. **Fluxo:** informa CNPJ, dados empresariais, contato, endereço, e-mail e senha → servidor valida → empresa e conta são gravadas na mesma transação → sessão é iniciada. **Alternativas:** CNPJ/e-mail duplicado, senha curta ou campo inválido não deixam cadastro parcial.

### CLI-UC02 — Consultar empresas

**Ator:** administrador. **Fluxo:** abre **Clientes PJ** → lista e pesquisa empresas → filtra ativas ou inativas → consulta detalhes. **Pós-condição:** nenhuma informação é alterada.

### CLI-UC03 — Editar empresa

**Ator:** administrador. **Fluxo:** abre cadastro → altera contato ou endereço → servidor revalida → salva sem modificar snapshots de pedidos antigos. **Alternativa:** identidade bloqueada por vínculo ou dado inválido mantém o registro anterior.

### CLI-UC04 — Inativar ou reativar empresa

**Ator:** administrador. **Fluxo:** altera o status da empresa → sistema preserva conta e histórico. **Alternativa:** empresa inativa tem login, pedido e venda bloqueados até reativação.

### CLI-UC05 — Consultar vínculos comerciais

**Ator:** administrador. **Fluxo:** abre a empresa → consulta pedidos, pagamentos e vendas associados. **Pós-condição:** vínculos permanecem íntegros.

### CLI-UC06 — Proteger cadastro com vínculos

**Ator:** sistema. **Fluxo:** recebe tentativa de excluir empresa ou alterar CNPJ protegido → verifica conta e histórico → rejeita a operação e informa o motivo.

### CLI-UC07 — Consultar CNPJ

**Ator:** visitante ou administrador. **Fluxo:** solicita consulta → integração tenta localizar os dados → formulário é auxiliado. **Alternativa:** falha externa mantém o formulário manual disponível.

## Critérios de aceite

Cadastrar CNPJ válido e rejeitar inválido/duplicado; criar conta sem deixar registro parcial; impedir login e compra da empresa inativa; proteger senha e sessão; manter pedidos/vendas após edição; bloquear exclusão com vínculos; preservar funcionamento manual quando a consulta externa falhar; e inserir a carga acadêmica uma única vez sem sobrescrever dados existentes.
