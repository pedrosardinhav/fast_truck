# FasTruck — Módulo de cadastro de veículos

## 1. Objetivo e escopo

Entregar um CRUD simples para cadastrar e gerenciar caminhões da FasTruck, incluindo informações de personalização. O front-end usa HTML, CSS e JavaScript; o back-end usa Python e a biblioteca SQLite incluída no Python. O módulo não contempla autenticação, venda, pagamento ou integração com serviços externos.

## 2. Premissas

- O sistema é executado localmente por uma pessoa em um computador.
- A aplicação é aberta pelo endereço local servido pelo Python; abrir o HTML como arquivo não conecta à API.
- A inicialização do banco inclui treze registros iniciais. Eles podem ser editados e excluídos pela interface; a carga adicional é aplicada uma única vez também a bancos já existentes.
- A base de dados é o arquivo `data/fasttruck.db`, criado automaticamente na primeira execução.
- O operador informa as características e personalizações; o sistema não confirma sua exatidão.
- A API só escuta em `127.0.0.1` por padrão e não se destina a acesso pela internet.

## 3. Requisitos funcionais

| ID | Requisito |
|---|---|
| RF01 | Cadastrar veículo com placa, marca, modelo, ano de fabricação/modelo, cor, status e valor anunciado. |
| RF02 | Registrar opcionalmente carroceria, tração, combustível, quilometragem e observações de personalização. |
| RF03 | Listar os veículos cadastrados com identificação, placa, ano, personalização, status e preço. |
| RF04 | Editar os dados de um veículo existente. |
| RF05 | Solicitar confirmação antes de excluir veículo. |
| RF06 | Pesquisar por placa, marca ou modelo e filtrar por status. |
| RF07 | Mostrar total de veículos, disponíveis, personalizados e valor anunciado somado. |
| RF08 | Persistir e recuperar os cadastros em banco SQLite por meio da API Python. |
| RF09 | Exibir mensagens de sucesso ou erro nas operações do CRUD. |
| RF10 | Disponibilizar endpoints HTTP para listar, criar, atualizar e excluir veículos. |

## 4. Regras de negócio

| ID | Regra |
|---|---|
| RN01 | A placa é obrigatória e deve corresponder ao padrão antigo (`ABC-1234`) ou Mercosul (`ABC-1D23`); letras são convertidas para maiúsculas. |
| RN02 | A placa é única no banco. Hífen e espaços não alteram a identificação normalizada da placa. |
| RN03 | Marca, modelo, ano, cor, status e valor anunciado são obrigatórios. |
| RN04 | Status permitido: “Disponível”, “Reservado” ou “Vendido”. |
| RN05 | Quilometragem e valor anunciado devem ser números iguais ou maiores que zero. |
| RN06 | Personalização recebe “sim” ou “não”; observações são opcionais. |
| RN07 | Atualizar um veículo mantém seu identificador e valida novamente todos os dados e a unicidade da placa. |
| RN08 | Excluir remove o veículo somente após confirmação na interface. |
| RN09 | O total anunciado soma todos os preços cadastrados, independentemente do status. |
| RN10 | Os registros iniciais são inseridos uma única vez, identificados por metadado no banco; excluí-los não faz com que reapareçam. |

## 5. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF01 | Interface responsiva e utilizável em desktop e telas estreitas. |
| RNF02 | Campos e botões têm rótulos e foco visível; mensagens são anunciadas às tecnologias assistivas. |
| RNF03 | Conteúdo de texto do usuário é escapado antes de ser inserido como conteúdo HTML da lista. |
| RNF04 | O servidor usa somente a biblioteca padrão do Python, sem dependências externas obrigatórias. |
| RNF05 | O SQLite persiste dados entre reinicializações do servidor; uma cópia de segurança depende de copiar `data/fasttruck.db`. |
| RNF06 | A API valida dados no servidor, além da validação básica no navegador. |
| RNF07 | O servidor local responde em `http://127.0.0.1:8000` e serve a interface e a API na mesma origem. |

## 6. Restrições

- Uso local, um único operador e sem controle de acesso ou autenticação.
- Sem cópia de segurança automática, sincronização entre dispositivos ou hospedagem pública.
- Sem validação oficial de placa, documentação, procedência, valor de mercado ou especificações mecânicas.
- Sem upload de fotos, catálogo público, carrinho, proposta, reserva online ou pagamento.
- Os registros iniciais representam dados de referência e podem ser editados ou excluídos.
- O servidor simples de desenvolvimento não substitui configuração de produção, HTTPS, monitoramento ou hardening.

## 7. Riscos e respostas

| Risco | Resposta / limite desta etapa |
|---|---|
| Perda da base por exclusão ou dano ao arquivo SQLite | Manter cópia periódica de `data/fasttruck.db`; não há backup automático nesta etapa. |
| Placa duplicada por variação de escrita | Normalizar placa e aplicar restrição `UNIQUE` no banco, com validação de formato. |
| Banco inacessível ou servidor parado | Mostrar erro de conexão e orientar a iniciar `python backend/app.py` na raiz do projeto. |
| Personalização ou características informadas incorretamente | Tratar os campos como informação declarada pelo operador, sem verificação externa. |
| Acesso indevido caso o servidor seja exposto na rede | Manter escuta local em `127.0.0.1`; a aplicação não foi projetada para acesso remoto. |
| Erro ao gravar um cadastro | Validar no back-end e devolver resposta de erro sem confirmar a operação. |

## 8. Casos de uso

### UC01 — Cadastrar caminhão

**Ator:** operador do estoque.

**Pré-condições:** servidor Python iniciado; banco acessível; página aberta pelo endereço local.

**Fluxo principal:**

1. O operador aciona “Novo caminhão”.
2. Preenche placa, marca, modelo, ano, cor, status e valor; pode preencher os demais campos e personalizações.
3. Aciona “Cadastrar caminhão”.
4. O navegador envia os dados à API Python.
5. A API valida os campos e grava o caminhão no SQLite.
6. A interface atualiza a lista e os indicadores e informa sucesso.

**Alternativas:** campos inválidos recebem mensagem; placa repetida é rejeitada pelo servidor; falha de conexão ou persistência informa erro sem confirmar o cadastro.

**Pós-condição:** o veículo consta na lista e na base SQLite.

### UC02 — Consultar e localizar caminhão

**Ator:** operador do estoque.

**Fluxo principal:** a interface consulta a API e mostra os veículos do SQLite; o operador busca por placa, marca ou modelo e/ou seleciona um status; a lista é filtrada e os indicadores continuam representando o estoque total.

**Pós-condição:** nenhum registro é alterado.

### UC03 — Editar caminhão

**Ator:** operador do estoque.

**Pré-condição:** veículo existe no SQLite.

**Fluxo principal:** o operador aciona editar; a interface preenche o formulário; o operador modifica os dados e salva; a API valida os dados e a placa; o SQLite atualiza o registro mantendo seu identificador; lista e indicadores são atualizados.

**Alternativas:** se a validação, unicidade da placa ou conexão falhar, a interface mostra a mensagem e não confirma a atualização.

### UC04 — Excluir caminhão

**Ator:** operador do estoque.

**Pré-condição:** veículo existe no SQLite.

**Fluxo principal:** o operador aciona excluir; a interface solicita confirmação; após confirmar, envia a exclusão à API; a API remove o registro do SQLite e a interface atualiza a lista e os indicadores.

**Fluxo alternativo:** “Manter veículo”, clique fora do diálogo ou tecla Esc fecham a confirmação sem excluir.

## 9. Rastreabilidade resumida

| Caso de uso | Requisitos e regras principais |
|---|---|
| UC01 | RF01, RF02, RF08–RF10; RN01–RN06; RNF04–RNF06 |
| UC02 | RF03, RF06, RF07, RF10; RN09 |
| UC03 | RF04, RF08–RF10; RN02, RN07 |
| UC04 | RF05, RF08–RF10; RN08 |

