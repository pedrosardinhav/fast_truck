# FasTruck — Plano e integração dos módulos

Data: 25/11/2026.

## 1. Objetivo

Transformar o cadastro de caminhões em um e-commerce local para empresas, mantendo um único caminho comercial: catálogo, personalização, pedido, checkout, pagamento, venda e histórico.

Os antigos módulos administrativos de propostas e pagamentos de proposta deixaram de fazer parte da navegação. A personalização e a decisão de compra agora acontecem diretamente no pedido da loja.

## 2. Módulos ativos

| Módulo | Responsabilidade |
|---|---|
| Estoque de veículos | Cadastrar, consultar, editar, vender, arquivar e consultar arquivados. |
| Clientes PJ | Cadastrar empresas, autenticar contas e manter dados empresariais. |
| Loja e personalização | Exibir caminhões disponíveis, adicionais e total calculado pelo servidor. |
| Pedidos e checkout | Reservar estoque, revisar a compra, processar pagamento e acompanhar o pedido. |
| Vendas e histórico | Registrar venda, comprador, valor, eventos e situação do veículo. |

Documentos relacionados:

- [Cadastro de veículos](REQUISITOS-CADASTRO-VEICULOS.md)
- [Clientes PJ](REQUISITOS-CLIENTES-PJ.md)
- [Área do cliente, pedidos e checkout](REQUISITOS-AREA-CLIENTE.md)
- [Guia para montar a apresentação](GUIA-APRESENTACAO.md)
- [Validação](VALIDACAO-MODULOS.md)

## 3. Fluxo integrado

1. A empresa cria uma conta ou entra na loja.
2. Consulta caminhões disponíveis e escolhe personalizações.
3. O servidor recalcula o total e cria o pedido com snapshots dos dados.
4. O caminhão é reservado para o pedido por 15 minutos.
5. O cliente escolhe cartão, Pix ou boleto.
6. O servidor processa a tentativa automaticamente.
7. Na aprovação, pagamento, venda, pedido, evento e status `Vendido` são confirmados na mesma transação.
8. Cliente e administrador acompanham o pedido em suas respectivas áreas.

O processamento financeiro é interno ao projeto acadêmico e não representa integração com banco, adquirente ou rede Pix. A interface comercial apresenta o fluxo como uma compra contínua, sem avisos repetidos que prejudiquem a experiência.

## 4. Dados e persistência

| Migração | Conteúdo principal |
|---|---|
| `001`–`003` | Estruturas administrativas originais preservadas para compatibilidade histórica. |
| `004_shop_accounts.sql` | Contas, sessões e vínculo com empresa. |
| `005_shop_orders.sql` | Catálogo, personalizações e pedidos. |
| `006_inventory_lifecycle.sql` | Exclusão lógica, reservas, vendas e eventos do veículo. |
| `007_checkout_v2.sql` | Snapshot de cobrança, prazo de reserva e tentativas de pagamento do checkout. |

Valores do checkout são armazenados em centavos inteiros. Pedidos guardam snapshots para que alterações futuras no cadastro não reescrevam a compra já realizada. A placa continua única mesmo após o arquivamento. A carga versionada em `src/backend/demo_data.py` cria sete empresas e uma conta compradora em bancos novos, enquanto `app.py` cria treze caminhões de exemplo. As cargas são idempotentes e não substituem registros existentes.

## 5. APIs principais

| Método e rota | Finalidade |
|---|---|
| `GET /api/shop/catalog` | Listar veículos disponíveis para compra. |
| `GET /api/shop/customizations` | Listar adicionais com preços definidos no servidor. |
| `POST /api/shop/register` | Criar empresa e conta de acesso. |
| `GET /api/shop/admin-access` | Consultar o acesso administrativo gerado na instalação local. |
| `POST /api/shop/orders` | Criar pedido e reservar o caminhão. |
| `GET /api/shop/orders` | Consultar pedidos da empresa autenticada. |
| `POST /api/shop/orders/{id}/payment` | Iniciar o processamento de cartão, Pix ou boleto. |
| `POST /api/shop/orders/{id}/cancel` | Cancelar pedido ainda não aprovado e liberar sua reserva. |
| `GET /api/shop/admin/orders` | Consultar pedidos e pagamentos no painel. |
| `GET /api/vehicles?view=active\|deleted\|all` | Consultar estoque ativo, arquivado ou completo. |
| `POST /api/vehicles/{id}/sell` | Registrar venda administrativa. |
| `DELETE /api/vehicles/{id}` | Arquivar o veículo sem remover histórico. |

## 6. Requisitos comuns

### Funcionais

- COM-RF01 — Autenticar clientes e administradores com papéis separados.
- COM-RF02 — Validar campos, vínculos, preços e estados no servidor.
- COM-RF03 — Calcular pedido e pagamento a partir dos dados persistidos.
- COM-RF04 — Preservar snapshots, eventos e histórico de venda.
- COM-RF05 — Garantir idempotência em criação de pedido, tentativa de pagamento e venda.
- COM-RF06 — Automatizar o processamento das três formas de pagamento disponíveis.
- COM-RF07 — Impedir que dois pedidos comprem o mesmo caminhão.
- COM-RF08 — Disponibilizar, no cabeçalho da instalação local, o acesso administrativo gerado naquele computador.

### Não funcionais

- COM-RNF01 — Usar Python 3.10+, SQLite e tecnologias web sem dependências externas obrigatórias.
- COM-RNF02 — Manter interface responsiva e navegação por teclado nas ações principais.
- COM-RNF03 — Armazenar senhas com scrypt e usar cookie HttpOnly e SameSite.
- COM-RNF04 — Exigir CSRF nas mutações autenticadas.
- COM-RNF05 — Executar mudanças de estoque e venda em transação SQLite.
- COM-RNF06 — Persistir datas em UTC e apresentar valores em BRL.
- COM-RNF07 — Escapar textos fornecidos pelo usuário antes de exibi-los.
- COM-RNF08 — Aplicar migrações uma vez e criar backup antes de alterar base existente.
- COM-RNF09 — Não armazenar em cache a resposta com o acesso administrativo e manter o servidor padrão restrito a `127.0.0.1`.

## 7. Regras de integração

- Um pedido possui um caminhão e pode conter várias personalizações.
- Apenas empresa ativa pode criar pedido ou receber uma venda administrativa.
- Apenas veículo disponível, não arquivado e sem reserva ativa entra no catálogo.
- Reserva pertence ao pedido que a criou e expira após 15 minutos.
- Expiração ou cancelamento libera somente a reserva proprietária.
- Pagamento aprovado é único por pedido.
- Aprovação altera o veículo para `Vendido` e registra a venda atomicamente.
- O navegador não define preço, valor final, resultado ou status do pagamento.
- Veículo vendido pode ser arquivado sem perder comprador, venda ou eventos.
- Administrador acompanha pagamentos; não precisa aprová-los manualmente.

## 8. Premissas, restrições e riscos

### Premissas

- Operação local em um único banco SQLite gravável.
- Empresas usam um CNPJ por conta nesta etapa.
- Retirada ocorre na unidade indicada no checkout.
- O relógio do computador está razoavelmente correto para reservas.

### Restrições

- Sem frete, entrega, nota fiscal, parcelamento, estorno ou recuperação de senha por e-mail.
- Sem integração bancária externa, webhooks ou conciliação financeira.
- Sem garantia de disponibilidade pública ou operação distribuída.
- Consulta externa de CNPJ é opcional; o cadastro manual continua disponível.
- O atalho que mostra o acesso administrativo atende à apresentação local e não deve ser exposto em uma implantação pública.

### Riscos e respostas

| Risco | Tratamento |
|---|---|
| Dois clientes escolherem o mesmo caminhão | Atualização condicional e transação de reserva. |
| Reenvio criar duplicidade | Chaves UUID e idempotência. |
| Pagamento concluir após expiração | Ordem temporal e propriedade da reserva revalidadas. |
| Falha parcial deixar estados divergentes | Pagamento, venda, evento e pedido gravados na mesma transação. |
| Perda do arquivo SQLite | Backup pré-migração e recomendação de cópias periódicas. |
| Alteração de cadastro mudar compra antiga | Snapshots imutáveis no pedido e na venda. |
| Exposição do acesso administrativo | Servidor restrito ao computador local, resposta sem cache e arquivo de credenciais fora do Git. |

## 9. Casos de uso consolidados

- UC01 — Empresa cria conta e entra na loja.
- UC02 — Cliente consulta e personaliza um caminhão.
- UC03 — Cliente cria pedido e obtém reserva temporária.
- UC04 — Cliente escolhe pagamento e acompanha o processamento automático.
- UC05 — Cliente consulta ou cancela um pedido ainda elegível.
- UC06 — Administrador acompanha pedidos, pagamentos e vendas.
- UC07 — Administrador cadastra, edita, vende ou arquiva um veículo.
- UC08 — Administrador consulta veículo arquivado com eventos e venda.
- UC09 — Apresentador abre **Admin** no cabeçalho e preenche o login administrativo local.

## 10. Aceite

O produto é aceito nesta etapa quando permite concluir o fluxo empresa → caminhão → personalização → pedido → pagamento → venda; preserva o histórico; bloqueia conflito de estoque; automatiza os estados financeiros; mantém isolamento entre empresas; e apresenta a loja e o painel sem transbordamento nas larguras verificadas.
