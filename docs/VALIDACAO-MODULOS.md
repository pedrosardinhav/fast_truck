# FasTruck — Registro de validação

Data: 16/11/2026. Resultados históricos da etapa administrativa e situação de verificação da loja.

**Registro da etapa administrativa anterior.** A loja com contas e pedidos foi acrescentada depois desta validação; os resultados abaixo não se aplicam automaticamente a ela. Consulte [Área do cliente](REQUISITOS-AREA-CLIENTE.md), seção de validação, para os limites da evolução atual. As fixtures administrativas foram adaptadas ao novo login sem reexecutar a suíte nesta etapa.

## 1. Escopo da revisão histórica

A etapa administrativa compreendia clientes PJ, propostas com personalizações e pagamentos simulados de propostas, integrados ao estoque. Houve revisão cruzada das regras e contratos durante a implementação:

| Módulo revisado | Revisão de regras e contratos |
|---|---|
| Clientes PJ | Revisão responsável por propostas |
| Propostas e personalizações | Revisão responsável por pagamentos |
| Pagamentos simulados | Revisão responsável por clientes |

A revisão cruzada usou resumos e trechos de código. Os revisores não executaram testes nem inspecionaram integralmente os arquivos finais; essa revisão não equivale a três execuções independentes da suíte. As verificações de execução descritas abaixo ocorreram durante a integração.

### Ajustes feitos na integração e revisão

- Uniformizados identificadores TEXT e contratos de resposta entre os módulos.
- Preservado preço-base ao editar uma proposta sem trocar o caminhão; congelados os dados comerciais no envio.
- Separadas as condições de troca de cliente e caminhão em rascunhos. Um vínculo mantido que ficou inelegível não impede editar o outro; ações comerciais continuam exigindo ambos elegíveis.
- Valores financeiros novos em centavos, quantidades inteiras e limites verificados no servidor.
- Metadados de consulta CNPJ assinados, vinculados ao documento e com validade de 24 horas; chave local persistente para sobreviver a reinícios.
- Unicidade de tentativa ativa, idempotência, resultados finais imutáveis e gravação de eventos na mesma transação.
- Removida dependência de fontes remotas da página de veículos para carregar a interface sem internet.

## 2. Ambiente e isolamento

Windows 10 (build 19045), Python 3.14.6, SQLite 3.50.4 e Node.js 24.18 para checagem sintática e automação de navegador. O projeto continua exigindo Python 3.10 ou superior e não depende de pacotes Python externos.

Os testes automatizados usam `TemporaryDirectory` e a variável `FASTRUCK_DB_PATH`, com servidor HTTP em porta local temporária. A verificação visual usou uma base sintética em `outputs/preview.db` e um processo separado na porta 18000. Não foram feitas alterações no banco do operador em `data/fasttruck.db` durante as verificações.

## 3. Suíte automatizada

```powershell
python -m unittest discover -s tests -v
```

Resultado histórico, anterior à autenticação e à loja: **17 testes aprovados**. Cada teste agrupa vários cenários e requisições HTTP. As fixtures foram adaptadas depois, mas a suíte atual não foi reexecutada nesta revisão documental.

| Área | Cenários cobertos |
|---|---|
| Clientes | Campos obrigatórios, limites básicos, normalização, CNPJ numérico/alfanumérico, dígitos inválidos, duplicidade, edição, inativação/reativação e exclusão. |
| Consulta CNPJ | Consulta não salva cadastro, metadados não podem ser forjados, token vinculado ao CNPJ, chave recuperada do disco, mapeamento dos campos, timeout, indisponibilidade, limite do provedor e não encontrado. |
| Propostas | Cálculo em centavos, preço-base preservado e recopiado na troca, dados congelados, limites de itens/quantidade/preço, rascunho com vínculo inelegível, estados, validade e motivos. |
| Vínculos | Exclusão bloqueada para empresa/caminhão com proposta, CNPJ vinculado imutável e exclusão de rascunho removendo itens associados. |
| Pagamentos | Valor derivado, rejeição de dados financeiros reais, criação e transições, nova tentativa após resultado permitido, motivos, estados finais, idempotência e dados históricos. |
| Elegibilidade | Revalidação de validade, cliente e situação do caminhão; possibilidade de cancelar/recusar tentativa mesmo quando deixou de ser elegível para aprovação. |
| Concorrência e falhas | Quatro criações simultâneas produzem uma tentativa ativa; falha forçada ao inserir evento desfaz criação ou atualização do pagamento. |
| Persistência | Na execução histórica, reinicialização da camada de banco preservou registros e aplicou uma vez as três migrações administrativas (`001` a `003`); base antiga com veículo próprio foi preservada e recebeu cópia antes da migração. Hoje existem também as versões `004` (contas) e `005` (pedidos), não abrangidas por aquele resultado. |
| Integração HTTP | Páginas, estilos e scripts dos quatro módulos servidos pelo mesmo servidor. |

Os testes da BrasilAPI usam respostas e falhas controladas, sem consulta ao serviço real. A reinicialização automatizada testa a camada de persistência; não é um teste de desligamento abrupto do computador.

Também foi executado `node --check` no JavaScript do cadastro de veículos e nos quatro arquivos compartilhado/clientes/propostas/pagamentos, sem erros de sintaxe.

## 4. Verificação no navegador

Executado em Microsoft Edge headless com base sintética:

1. Carregar veículos e conferir navegação entre quatro módulos e os 13 caminhões iniciais.
2. Cadastrar empresa com CNPJ alfanumérico válido pelo formulário.
3. Criar proposta com personalização de quantidade 2 e preço unitário R$ 1.500,50.
4. Registrar envio e aprovação pelos diálogos da interface.
5. Criar e aprovar pagamento simulado pela interface.
6. Conferir comprovante com indicação **SEM VALOR FINANCEIRO** e emular impressão.
7. Abrir clientes, propostas e pagamentos em 360 × 800 px, sem transbordamento horizontal da página. As tabelas têm rolagem própria quando necessário.

Resultado histórico: fluxo administrativo concluído, sem exceções JavaScript capturadas. Capturas temporárias de desktop, mobile e impressão foram geradas em `outputs/`, ignorado pelo Git. Essas capturas e a automação do navegador não são parte versionada do projeto; quem clona pode reproduzir as verificações dos scripts em `tests/`. Essa execução não cobre a loja nem todos os fluxos alternativos por cliques.

## 5. Medição de desempenho — COM-RNF15

```powershell
python tests/benchmark_modules.py
```

Carga sintética com **1.000 clientes, 1.000 propostas e 1.000 pagamentos**, criada por SQL em banco temporário a partir de registros válidos. Foram medidos HTTP local, leitura/gravação e processamento JSON; maior resultado de três execuções, exceto criação de pagamento, executada uma vez para respeitar unicidade.

| Operação | Clientes | Propostas | Pagamentos |
|---|---:|---:|---:|
| Listagem | 0,0472 s | 0,4954 s | 0,1269 s |
| Pesquisa | 0,0474 s | 0,4837 s | 0,1134 s |
| Salvamento | 0,0492 s | 0,0479 s | 0,0462 s |

Resultado histórico: todas as operações medidas ficaram abaixo de 2 segundos. A medição antecede as verificações de sessão administrativa adicionadas depois; não é uma medição do checkout ou da versão atual. O comando imprime o JSON com os tempos e o ambiente ao repetir o ensaio.

Clientes e propostas filtram a lista na interface: a medição equivalente inclui transferência e filtro em Python, sem medir pintura do navegador. O teste não representa carga concorrente, dados com textos no tamanho máximo nem garantia de desempenho em outros computadores. A meta de 2 segundos vale para este ensaio local.

## 6. Limites e pendências de validação

- Não foi comprovada disponibilidade ao vivo nem suporte a CNPJ alfanumérico da BrasilAPI. Falhas preservam cadastro manual e não impedem o fluxo local.
- Foco/diálogos, rótulos e mensagens acessíveis foram implementados; não houve auditoria completa com leitor de tela.
- Python 3.10 é a versão mínima pela sintaxe utilizada; a execução desta entrega ocorreu em Python 3.14.6, sem matriz de versões e sistemas operacionais.
- O ensaio histórico antecede a autenticação. A versão atual tem contas de empresa e administrador, mas permanece local, sem hospedagem pública nem processamento financeiro real. Os testes históricos não constituem auditoria da autenticação ou homologação para produção.
- Os documentos de requisitos mantêm critérios que vão além dos cenários executados. Resultado aprovado na suíte não significa cobertura exaustiva de todos os requisitos não funcionais.

## 7. Documentos relacionados

- [Área do cliente e critérios de aceite do checkout](REQUISITOS-AREA-CLIENTE.md).

- [Plano, integração e requisitos comuns](PLANO-NOVOS-MODULOS.md).
- [Clientes PJ: requisitos, regras, riscos e casos de uso](REQUISITOS-CLIENTES-PJ.md).
- [Propostas e personalizações: requisitos, regras, riscos e casos de uso](REQUISITOS-PROPOSTAS-PERSONALIZACOES.md).
- [Pagamentos simulados: requisitos, regras, riscos e casos de uso](REQUISITOS-PAGAMENTOS-SIMULADOS.md).
- [Veículos e bloqueios por vínculo](REQUISITOS-CADASTRO-VEICULOS.md).

## 8. Verificações posteriores e pendências atuais

Na integração da loja foram feitas checagens sintáticas com `py_compile` e `node --check`; a página inicial e o catálogo públicos responderam HTTP 200. A apresentação também respondeu HTTP 200 após correção de seu servidor. Essas verificações não exercitam o cadastro/login completo, o checkout, a autorização entre duas empresas ou a impressão da nova loja.

Na revisão documental foram comparados textos, código, rotas, campos e limites; também foram conferidos links locais e o conjunto de arquivos que o Git pode incluir. A revisão documental não reexecuta nem amplia os resultados dos testes de aplicação.

Permanecem pendentes os cenários de aceite listados nos requisitos da área do cliente, a reexecução da suíte administrativa adaptada, uma nova medição de desempenho com autenticação e uma auditoria completa de acessibilidade. Portanto, os documentos descrevem o comportamento implementado e os critérios esperados, sem declarar aceite completo da aplicação.
