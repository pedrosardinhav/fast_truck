# FasTruck

E-commerce local da FasTruck: empresas criam uma conta, escolhem caminhões e personalizações, fazem pedidos e simulam o pagamento. Há também painel administrativo de veículos, clientes, propostas e pagamentos. Usa Python e SQLite no back-end e HTML, CSS e JavaScript no front-end, sem pacotes Python externos obrigatórios.

## Baixar pelo GitHub

Com o repositório público ou com acesso concedido, clone o projeto e entre na pasta:

```powershell
git clone https://github.com/pedrosardinhav/fast_truck.git
cd fast_truck
```

## Como iniciar

1. Instale o Python 3.10 ou mais recente.
2. Abra um terminal nesta pasta.
3. Inicie o servidor:

   ```powershell
   python src/backend/app.py
   ```

4. Acesse <http://127.0.0.1:8000> no navegador.
5. A página inicial é a **loja do cliente**. Cadastre sua empresa, entre, escolha um caminhão, personalize e acompanhe seus pedidos.
6. Para administração, abra <http://127.0.0.1:8000/admin>. Na primeira inicialização, o sistema gera o e-mail e uma senha aleatória de administrador em `data/.admin-access`. Abra esse arquivo local e use os dados na tela de login. O arquivo é ignorado pelo Git.
7. Para parar o servidor, pressione `Ctrl+C` no terminal. Se estava aberto durante a atualização, reinicie para carregar a loja, a autenticação e as migrações.

## Área da empresa: comprar pela loja

1. Entre na loja e selecione **Criar conta**. Informe CNPJ, dados empresariais, contato, endereço e senha. O cadastro cria a empresa e o acesso juntos.
2. Explore o catálogo de caminhões disponíveis e abra os detalhes do veículo.
3. Escolha as personalizações e quantidades. Os preços dos adicionais vêm do servidor; observações permitem descrever preferências.
4. Confirme o pedido e escolha Pix, boleto ou cartão na etapa financeira.
5. Escolha o resultado da simulação. Uma recusa ou cancelamento da tentativa permite tentar novamente; uma aprovação finaliza o pagamento daquele pedido.
6. Consulte **Meus pedidos**, os detalhes, o histórico de tentativas e o comprovante de simulação. Pedidos sem pagamento aprovado podem ser cancelados.

Cada empresa acessa somente seus próprios pedidos. Dados já cadastrados no painel ou na carga de exemplos não ganham senha automaticamente; o cadastro público não permite assumir uma empresa existente pelo CNPJ. Nesta versão, cadastre uma empresa com CNPJ ainda não utilizado para criar uma conta nova.

Os pagamentos continuam simulados, sem dados reais de cartão, QR Code bancário ou cobrança. Pedidos não reservam nem vendem o caminhão automaticamente. A administração acompanha os pedidos de clientes na aba **Pedidos da loja**; propostas comerciais e seus pagamentos permanecem em seus módulos originais.

## Apresentação do fluxo CRUD

Em outro terminal, também na raiz do projeto, inicie o servidor da apresentação:

```powershell
python src/apresentacao/server.py
```

Abra <http://127.0.0.1:8001>. O script encontra a pasta da apresentação pelo próprio arquivo, evitando o erro 404 causado por iniciar o servidor com uma pasta relativa incorreta. Se um servidor antigo estiver usando essa porta, pare-o com `Ctrl+C` antes de executar o comando.

A apresentação mostra os dados do cadastro, a tabela SQLite, as validações e o fluxo Create, Read, Update e Delete com trechos do código do projeto. Depois vêm as regras de negócio, requisitos, premissas, restrições, riscos e casos de uso. No topo, **Baixar PDF** abre a impressão de todos os slides: escolha **Salvar como PDF**.

Não abra `index.html` diretamente: o front-end precisa do servidor Python para consultar a API e gravar os dados.

## Banco de dados

O servidor usa `data/fasttruck.db` como banco SQLite local; os dados continuam disponíveis depois de fechar e iniciar o servidor novamente. Uma base nova recebe treze caminhões iniciais (três da carga original e dez da carga adicional). Cada carga é aplicada uma vez, inclusive a adicional em bases antigas. Registros removidos pela tela não são recriados.

As migrações em `sql/migrations/` são aplicadas uma única vez na inicialização, preservando os veículos existentes. Antes de migrar uma base com veículos, o sistema cria uma cópia em `data/backups/`. Essa proteção na atualização não substitui cópias periódicas.

Para fazer uma cópia de segurança, pare o servidor e copie o arquivo `data/fasttruck.db` para outro local. A consulta de CNPJ também gera `data/.cnpj-lookup-key`: preserve essa chave local para manter válidos os tokens de consulta ainda não salvos, que expiram em 24 horas. Banco, cópias e chave são ignorados pelo Git. Não apague o banco se quiser manter os cadastros.

## Dados de exemplo dos novos módulos

Para preencher clientes, propostas e pagamentos com exemplos, execute na raiz:

```powershell
python src/backend/seed_examples.py
```

A carga opcional acrescenta **6 empresas fictícias** (uma inativa), **8 propostas** (rascunhos, enviada, aprovadas e cancelada) e **5 pagamentos simulados** (aprovado, pendentes, recusado e cancelado). Há personalizações, histórico e uma nova tentativa após recusa. A validade inicial das propostas fica entre 30 e 37 dias a partir da carga.

Os exemplos usam os caminhões Disponíveis já cadastrados, sem mudar seu preço ou status. É necessário ter pelo menos um Disponível com valor positivo. A carga preserva os registros existentes, cria uma cópia antes de inserir e grava tudo em uma transação. Rodar novamente não duplica os exemplos nem recria registros excluídos. Ela não roda automaticamente ao iniciar o servidor.

Empresas, contatos e documentos dos exemplos são sintéticos; os CNPJs têm dígitos calculados localmente e não foram consultados em serviço oficial. Após executar, atualize a página do sistema. O banco não é enviado pelo Git: quem clonar pode executar o mesmo comando.

## O que o sistema faz

- Cadastra caminhões com identificação, características, status, preço e observações de personalização.
- Lista, pesquisa, filtra, edita e exclui veículos.
- Impede placas duplicadas e valida os campos obrigatórios no servidor.
- Exibe indicadores do estoque.
- Permite autocadastro e login da empresa, catálogo público, personalização e pedidos na loja.
- Mantém os pedidos de cada empresa isolados e permite acompanhamento pela administração.
- Cadastra empresas, valida CNPJ numérico ou alfanumérico e permite consulta opcional à BrasilAPI para auxiliar no preenchimento. O cadastro manual funciona sem internet.
- Cria propostas com um cliente, um caminhão e até 30 personalizações; calcula valores no servidor, registra envio/aprovação/cancelamento e preserva os dados comerciais enviados.
- Simula pagamentos por Pix, boleto ou cartão, com tentativas, motivos, histórico e comprovante para impressão sem valor financeiro.
- Bloqueia exclusão de empresa com conta, proposta ou pedido e de caminhão com proposta ou pedido; impede duplicidade das operações financeiras conforme as regras de cada fluxo.

## Fluxo administrativo de propostas

1. Cadastre uma empresa em **Clientes PJ**. Consultar CNPJ é opcional e não salva o formulário automaticamente.
2. Em **Propostas**, selecione cliente ativo e caminhão Disponível, informe validade e adicione personalizações se desejar.
3. Salve, abra os detalhes e registre o envio; depois registre a aprovação. Envio e aprovação são registros manuais do operador.
4. Em **Pagamentos**, crie uma tentativa para a proposta aprovada e vigente. Escolha o resultado da simulação.
5. Se aprovada, imprima o comprovante. Se recusada ou cancelada, uma nova tentativa pode ser criada enquanto a proposta continuar elegível.

Pagamentos não movimentam dinheiro, não pedem dados reais de cartão e não alteram automaticamente o estoque. Propostas não reservam caminhões. A consulta matemática do CNPJ não comprova existência ou situação cadastral da empresa; o retorno externo pode estar indisponível ou desatualizado.

## Requisitos e validação

O [plano de evolução](docs/PLANO-NOVOS-MODULOS.md) registra decisões de integração e requisitos comuns. Os módulos implementados têm documentação própria:

- [Área do cliente](docs/REQUISITOS-AREA-CLIENTE.md): contas, acesso, catálogo, personalizações, pedidos e checkout simulado.
- [Cadastro de veículos](docs/REQUISITOS-CADASTRO-VEICULOS.md): estoque administrativo e dados dos caminhões.
- [Clientes PJ](docs/REQUISITOS-CLIENTES-PJ.md): gestão administrativa das empresas, validação local e consulta opcional de CNPJ.
- [Propostas e personalizações](docs/REQUISITOS-PROPOSTAS-PERSONALIZACOES.md): empresa, caminhão, adicionais, valores e acompanhamento da negociação.
- [Pagamentos simulados](docs/REQUISITOS-PAGAMENTOS-SIMULADOS.md): tentativas, aprovação/recusa/cancelamento, histórico e comprovante sem valor financeiro.

Cada documento reúne requisitos funcionais e não funcionais, regras de negócio, premissas, restrições, riscos, casos de uso e critérios de aceite.

Veja também os [requisitos de veículos](docs/REQUISITOS-CADASTRO-VEICULOS.md) e o [relatório de validação](docs/VALIDACAO-MODULOS.md), com revisão cruzada, testes, medições e limites do aceite. A apresentação em `src/apresentacao/` continua dedicada ao CRUD original de veículos.

### Executar as verificações

Na raiz, usando apenas a biblioteca padrão do Python:

```powershell
python -m unittest discover -s tests -v
python tests/benchmark_modules.py
```

As verificações usam bancos temporários e não alteram `data/fasttruck.db`. A suíte cobre os módulos administrativos, regras, concorrência e migrações; as fixtures já incluem acesso administrativo. A medição cria carga sintética com 1.000 registros por módulo administrativo. Não é necessário iniciar o servidor antes desses comandos.

O resultado histórico de 17 testes aprovados foi obtido antes da loja e da autenticação. Os comandos não foram reexecutados após essa evolução; eles não cobrem o fluxo completo de compra do cliente. Consulte o [registro de validação](docs/VALIDACAO-MODULOS.md) e os critérios de aceite da área do cliente.

## Preparar para enviar ao GitHub

Versione o código em `src/`, o esquema e **todas as migrações** em `sql/`, os documentos, o README e os scripts de verificação em `tests/`. O arquivo do banco e o acesso administrativo não acompanham o clone: cada pessoa cria sua própria base ao iniciar o servidor.

O `.gitignore` exclui `data/*.db*`, `data/backups/`, `data/.admin-access`, `data/.cnpj-lookup-key`, `outputs/`, ambientes virtuais, cache Python, `.env` e `.openai/`. A pasta `outputs/` contém apenas artefatos temporários de validação e não é necessária para iniciar o sistema.

Na raiz, revise o que será enviado antes de publicar:

```powershell
git add .
git diff --cached --stat
git status
git commit -m "Adiciona loja, pedidos e documentação da FasTruck"
git push -u origin main
```

O último comando pressupõe que `origin` já aponta para o repositório e a branch atual é `main`. Não adicione o banco, senhas ou arquivos locais à força com `git add -f`.

## Limites desta entrega

Uso local para estudo, com contas de empresa e de administrador, sessão por cookie e checkout de pedidos com pagamento simulado. Sem hospedagem pública, recuperação de senha por e-mail, verificação de titularidade do CNPJ, frete, nota fiscal, entrega ou integração bancária. O servidor escuta em `127.0.0.1:8000`; quem clonar recebe sua própria base e seu próprio acesso administrativo. As senhas das contas ficam como hash scrypt; a senha inicial de administrador também é escrita no arquivo local de acesso para permitir a primeira entrada.

Os [requisitos da área do cliente](docs/REQUISITOS-AREA-CLIENTE.md) descrevem essa evolução e substituem as antigas restrições de “sem login” e “sem acesso próprio do cliente”. O [relatório anterior de validação](docs/VALIDACAO-MODULOS.md) refere-se à etapa dos módulos administrativos, anterior ao checkout do cliente; não é um aceite da nova loja.

## Estrutura de pastas

```text
fasttruck/
├── .gitignore
├── README.md
├── sql/
│   ├── schema.sql
│   └── migrations/            # cinco versões: módulos, contas e pedidos
├── src/
│   ├── backend/
│   │   ├── app.py             # servidor e rotas
│   │   ├── common.py          # validações, datas e dinheiro
│   │   ├── db.py              # SQLite, transações e migrações
│   │   ├── seed_examples.py   # carga opcional dos novos módulos
│   │   ├── services/          # clientes, propostas, pagamentos, contas e loja
│   │   └── integrations/      # consulta BrasilAPI
│   ├── frontend/
│   │   ├── index.html
│   │   ├── app.js
│   │   ├── loja.html           # catálogo e área da empresa
│   │   ├── clientes.html
│   │   ├── propostas.html
│   │   ├── pagamentos.html
│   │   ├── pedidos.html        # acompanhamento administrativo da loja
│   │   ├── css/               # estilos compartilhados
│   │   └── js/                # interações e API por módulo
│   └── apresentacao/
│       ├── index.html
│       └── server.py           # servidor da apresentação na porta 8001
├── docs/
│   ├── PLANO-NOVOS-MODULOS.md
│   ├── REQUISITOS-CADASTRO-VEICULOS.md
│   ├── REQUISITOS-CLIENTES-PJ.md
│   ├── REQUISITOS-PROPOSTAS-PERSONALIZACOES.md
│   ├── REQUISITOS-PAGAMENTOS-SIMULADOS.md
│   ├── REQUISITOS-AREA-CLIENTE.md
│   └── VALIDACAO-MODULOS.md
├── tests/
│   ├── test_modules.py
│   └── benchmark_modules.py
└── data/
    └── fasttruck.db  (criado localmente; ignorado pelo Git)
```




