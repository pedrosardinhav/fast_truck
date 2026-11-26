# FasTruck

E-commerce local de caminhões para empresas. A loja permite criar uma conta PJ, consultar o catálogo, personalizar um caminhão, concluir o checkout e acompanhar pedidos. O painel administrativo concentra veículos, clientes, pedidos, pagamentos e histórico de vendas.

O projeto usa Python e SQLite no back-end e HTML, CSS e JavaScript no front-end, sem pacotes Python externos obrigatórios.

## Como iniciar

Requisitos: Python 3.10 ou mais recente.

```powershell
git clone https://github.com/pedrosardinhav/fast_truck.git
cd fast_truck
python src/backend/app.py
```

Acesse:

- Loja: <http://127.0.0.1:8000>
- Administração: <http://127.0.0.1:8000/admin>

Na primeira inicialização, o sistema cria o banco e gera o acesso inicial do administrador em `data/.admin-access`. Esse arquivo e o banco são locais e ignorados pelo Git. Para encerrar o servidor, pressione `Ctrl+C`.

O primeiro início também carrega os caminhões e empresas usados na demonstração. Uma conta de cliente fica pronta para testar a compra:

- e-mail: `compras@horizonteazul.com.br`
- senha: `teste123`

Para consultar o acesso administrativo criado na máquina, use **Admin** no cabeçalho da loja ou execute `Get-Content data/.admin-access` no PowerShell.

## Fluxo de compra

1. A empresa cria a conta com CNPJ, contato, endereço e senha ou entra em uma conta existente.
2. Escolhe um caminhão disponível e as personalizações desejadas.
3. Revisa os dados da empresa, o veículo, os adicionais e o total.
4. Ao confirmar o pedido, o caminhão fica reservado por 15 minutos.
5. Escolhe cartão, Pix ou boleto. O sistema processa o resultado automaticamente.
6. Quando o pagamento é aprovado, pedido, pagamento, venda, status `Vendido` e eventos são gravados na mesma transação.
7. A empresa consulta o andamento e o comprovante em **Meus pedidos**.

Cada empresa acessa apenas os próprios pedidos. Cartão recusado permite nova tentativa enquanto a reserva estiver ativa. Cancelamento ou expiração libera somente a reserva pertencente ao pedido.

O processamento financeiro é interno ao projeto acadêmico: não há comunicação com adquirente, banco ou rede Pix, e o sistema não coleta PAN, CVV ou credenciais bancárias. Essa limitação técnica não é exibida como aviso repetitivo no fluxo comercial.

## Administração

O painel oferece:

- cadastro, consulta, edição, venda e arquivamento lógico de caminhões;
- consulta de veículos ativos, vendidos e arquivados, com eventos e venda preservados;
- gestão de empresas clientes;
- acompanhamento de pedidos e pagamentos;
- registro de venda administrativa para uma empresa ativa;
- indicadores de estoque e histórico comercial.

As personalizações fazem parte do pedido da loja. Os antigos fluxos administrativos de propostas e pagamentos separados foram retirados da navegação porque o checkout passou a concentrar a compra completa.

## Formas de pagamento no ambiente local

- Cartão corporativo final `4242`: aprovado após processamento.
- Cartão alternativo final `0002`: recusado, permitindo uma nova tentativa.
- Pix: confirmado automaticamente após o processamento.
- Boleto: compensado automaticamente após o processamento.

O resultado é determinado pelo servidor; o navegador não envia status, valor ou resultado da tentativa. Todos os valores são recalculados no back-end.

## Apresentação

Em outro terminal:

```powershell
python src/apresentacao/server.py
```

Abra <http://127.0.0.1:8001>. A apresentação reúne o CRUD de veículos, o ciclo de estoque, os requisitos e o checkout. O botão **Baixar PDF** abre a impressão do navegador; escolha **Salvar como PDF**.

## Banco de dados

O banco SQLite fica em `data/fasttruck.db`. As migrações de `sql/migrations/` são aplicadas uma única vez e preservam os dados existentes. Antes de alterar uma base que já contém veículos, o sistema cria uma cópia em `data/backups/`. Os dados acadêmicos compartilhados ficam em `src/backend/demo_data.py` e são incluídos automaticamente sem substituir cadastros já existentes.

Para manter uma cópia manual, pare o servidor e copie `data/fasttruck.db`. Não apague esse arquivo se quiser preservar cadastros, pedidos e histórico.

## Requisitos e validação

- [Cadastro de veículos](docs/REQUISITOS-CADASTRO-VEICULOS.md)
- [Clientes PJ](docs/REQUISITOS-CLIENTES-PJ.md)
- [Área do cliente, pedidos e checkout](docs/REQUISITOS-AREA-CLIENTE.md)
- [Plano e integração dos módulos](docs/PLANO-NOVOS-MODULOS.md)
- [Guia para montar a apresentação](docs/GUIA-APRESENTACAO.md)
- [Registro de validação](docs/VALIDACAO-MODULOS.md)

Os documentos reúnem requisitos funcionais e não funcionais, regras de negócio, premissas, restrições, riscos, casos de uso e critérios de aceite.

## Verificações

```powershell
python -m unittest discover -s tests -v
```

Os testes usam bancos temporários e não alteram `data/fasttruck.db`. A bateria atual cobre autenticação, estoque, concorrência de reserva, checkout, pagamentos, venda e migrações. Consulte o [registro de validação](docs/VALIDACAO-MODULOS.md) para o escopo exato.

## Limites desta entrega

Aplicação local para estudo, com contas de empresa e administrador, sessão por cookie, estoque e checkout. Não inclui hospedagem pública, recuperação de senha por e-mail, confirmação de titularidade do CNPJ, frete, entrega, nota fiscal ou integração bancária. As senhas são armazenadas com hash scrypt.

## Estrutura principal

```text
fasttruck/
├── README.md
├── sql/
│   ├── schema.sql
│   └── migrations/
├── src/
│   ├── backend/
│   │   ├── app.py
│   │   ├── db.py
│   │   ├── common.py
│   │   ├── demo_data.py
│   │   ├── services/
│   │   └── integrations/
│   ├── frontend/
│   │   ├── index.html
│   │   ├── loja.html
│   │   ├── clientes.html
│   │   ├── pedidos.html
│   │   ├── css/
│   │   └── js/
│   └── apresentacao/
│       ├── index.html
│       └── server.py
├── docs/
├── tests/
└── data/
    └── fasttruck.db  (criado localmente; ignorado pelo Git)
```

## Enviar ao GitHub

```powershell
git add .
git diff --cached --stat
git status
git commit -m "Atualiza estoque e checkout da FasTruck"
git push -u origin main
```

Revise o `git status` antes de publicar. Não force a inclusão do banco, backups, credenciais ou chaves locais: as migrações e a carga de demonstração recriam os dados necessários em cada instalação.
