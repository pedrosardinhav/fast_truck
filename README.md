# FasTruck

Módulo funcional da FasTruck para cadastro e gestão de caminhões. O projeto usa Python e SQLite no back-end, com HTML, CSS e JavaScript no front-end. Não precisa instalar pacotes Python externos.

## Como iniciar

1. Instale o Python 3.10 ou mais recente.
2. Abra um terminal nesta pasta.
3. Inicie o servidor:

   ```powershell
   python src/backend/app.py
   ```

4. Acesse <http://127.0.0.1:8000> no navegador.
5. Para parar o servidor, pressione `Ctrl+C` no terminal.

## Apresentação do fluxo CRUD

Em outro terminal, também na raiz do projeto, inicie o servidor da apresentação:

```powershell
python -m http.server 8001 --bind 127.0.0.1 --directory src/apresentacao
```

Abra <http://127.0.0.1:8001>. A apresentação mostra os dados do cadastro, a tabela SQLite, as validações e o fluxo Create, Read, Update e Delete com trechos do código do projeto. Depois vêm as regras de negócio, requisitos, premissas, restrições, riscos e casos de uso.

Não abra `index.html` diretamente: o front-end precisa do servidor Python para consultar a API e gravar os dados.

## Banco de dados

O servidor usa `data/fasttruck.db` como banco SQLite local; os dados continuam disponíveis depois de fechar e iniciar o servidor novamente. O banco começa com treze registros iniciais para uso no sistema. Os dez novos registros são acrescentados uma única vez também em bancos já iniciados. Registros removidos pela tela não são recriados.

Se o servidor já estiver aberto, pare com `Ctrl+C` e inicie novamente para aplicar a carga dos dez novos caminhões ao banco atual. Os demais cadastros existentes são preservados.

Para fazer uma cópia de segurança, pare o servidor e copie o arquivo `data/fasttruck.db` para outro local. Não apague esse arquivo se quiser manter os cadastros.

## O que o módulo faz

- Cadastra caminhões com identificação, características, status, preço e observações de personalização.
- Lista, pesquisa, filtra, edita e exclui veículos.
- Impede placas duplicadas e valida os campos obrigatórios no servidor.
- Exibe indicadores do estoque.

## Estrutura de pastas

```text
fasttruck/
├── .gitignore
├── README.md
├── sql/
│   └── schema.sql
├── src/
│   ├── backend/
│   │   └── app.py
│   ├── frontend/
│   │   ├── index.html
│   │   └── app.js
│   └── apresentacao/
│       └── index.html
├── docs/
│   └── REQUISITOS-CADASTRO-VEICULOS.md
└── data/
    └── fasttruck.db  (criado localmente; ignorado pelo Git)
```

