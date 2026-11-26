# FasTruck — Registro de validação

Data: 25/11/2026.

## 1. Escopo atual

A validação principal cobre o produto ativo: clientes PJ, autenticação, estoque, catálogo, personalização, pedidos, checkout, pagamentos, vendas, histórico e apresentação.

Os antigos módulos de propostas e pagamentos administrativos deixaram a navegação. Estruturas históricas podem permanecer no banco por compatibilidade de migração, mas não representam o fluxo comercial atual.

## 2. Ambiente e isolamento

- Windows 10, Python 3.14.6, SQLite 3.50.4 e Node.js 24.18 na execução registrada.
- Compatibilidade mínima prevista: Python 3.10.
- Testes usam diretórios temporários e `FASTRUCK_DB_PATH`.
- Fluxos automatizados não alteram `data/fasttruck.db`.
- A aplicação não exige pacotes Python externos.

## 3. Verificações automatizadas registradas

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src/backend tests
```

Resultado da revisão final: **26 testes aprovados** em **53,213 s**. A bateria ativa incluiu:

| Área | Cenários principais |
|---|---|
| Autenticação | Cadastro PJ, login, logout, papéis, cookie, CSRF e isolamento entre empresas. |
| Veículos | Cadastro, edição, placa única, venda, arquivamento lógico e consulta histórica. |
| Estoque | Reserva exclusiva, expiração, liberação proprietária e conflito entre compradores. |
| Checkout | Cálculo no servidor, snapshots, idempotência, cancelamento e novas tentativas. |
| Pagamento | Aprovação, recusa, Pix, boleto, rejeição de campos forjados e uma aprovação por pedido. |
| Integridade | Venda, pagamento, pedido, evento e status atômicos; rollback em falha induzida. |
| Migrações | Aplicação única, backup e preservação de veículos existentes. |

Os cenários dos módulos administrativos aposentados deixaram a bateria ativa. Um teste de compatibilidade confirma que suas rotas retornam 404 e que as tabelas históricas continuam disponíveis para migração de bases existentes.

## 4. Verificação no navegador

Os fluxos funcionais completos foram exercitados com banco temporário. Eles cobrem:

1. Cadastro de empresa.
2. Escolha do caminhão e das personalizações.
3. Checkout em três etapas.
4. Cartão final 4242 aprovado.
5. Cartão final 0002 recusado e nova tentativa aprovada no mesmo pedido.
6. Pix confirmado automaticamente.
7. Boleto processado e aprovado automaticamente.
8. Cadastro, edição, venda, arquivamento e histórico de veículo no painel.
9. Consulta dos pedidos pela administração.

Na revisão visual final em Edge headless, a loja, **Pedidos da loja** e a apresentação foram abertas em 1440 × 900 px; **Pedidos da loja** também foi conferida em 390 × 844 px. O contador ficou dentro do cabeçalho do painel, a página não apresentou transbordamento horizontal e o menu exibiu somente Veículos, Clientes PJ, Pedidos da loja e Ver loja. A tabela usa rolagem interna no celular.

## 5. Banco local e migrações

As migrações 006 e 007 foram aplicadas preservando os 14 veículos. Na revisão final, o banco continha 14 veículos, 7 empresas e 2 pedidos; `PRAGMA integrity_check` retornou `ok` e `PRAGMA foreign_key_check` retornou zero linhas.

Nenhuma operação de criação, venda ou arquivamento foi executada no banco do usuário durante essa verificação. Os fluxos funcionais usaram bases temporárias.

## 6. Apresentação

A apresentação respondeu HTTP 200 na porta 8001. A revisão final confirmou 19 slides, 19 links de navegação, JavaScript válido e ausência de transbordamento na tela inicial em 1440 × 900 px. O botão **Baixar PDF** usa a impressão do navegador.

Na revisão documental de 25/11/2026, nomes de migração, rotas ativas, carga inicial, estados do checkout e acesso administrativo foram comparados com o código atual. O [guia da apresentação](GUIA-APRESENTACAO.md) registra a sequência sugerida e indica a fonte de cada grupo de slides.

## 7. Controles relevantes

- valores e estados são determinados no servidor;
- UUIDs impedem duplicação por reenvio;
- autorização separa cliente e administrador;
- consultas da loja aplicam propriedade da empresa;
- venda e estoque usam transação SQLite;
- soft delete preserva placa, venda e eventos;
- strings da interface são escapadas;
- backup é criado antes de migrações em base com veículos.
- acesso administrativo é gerado localmente, fica fora do Git e é retornado sem cache pelo atalho **Admin** no servidor em loopback.

## 8. Limites da validação

- Não houve auditoria completa com leitor de tela.
- Não houve matriz de versões de Python, navegadores e sistemas operacionais.
- A medição local não representa carga de produção.
- A aplicação não foi homologada para processamento bancário, operação pública ou dados financeiros reais.
- O atalho que revela a credencial administrativa existe para execução e apresentação local; ele não é adequado para exposição pública.
- Consulta externa de CNPJ foi testada com respostas controladas, sem comprovar disponibilidade ao vivo.
- Resultados descritos cobrem apenas os cenários e versões explicitamente registrados.

## 9. Comandos de revisão final

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src/backend tests
git diff --check
```

Além dos comandos, revisar manualmente loja, checkout, pedidos, painel, apresentação e impressão em largura desktop e mobile.

## 10. Documentos relacionados

- [Plano e integração](PLANO-NOVOS-MODULOS.md)
- [Cadastro de veículos](REQUISITOS-CADASTRO-VEICULOS.md)
- [Clientes PJ](REQUISITOS-CLIENTES-PJ.md)
- [Área do cliente, pedidos e checkout](REQUISITOS-AREA-CLIENTE.md)
- [Guia para montar a apresentação](GUIA-APRESENTACAO.md)
