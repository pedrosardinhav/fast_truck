# FasTruck — Requisitos da área do cliente, pedidos e checkout

Data: 25/11/2026.

## 1. Objetivo e escopo

Permitir que uma empresa se cadastre, entre na loja, escolha um caminhão, selecione personalizações, confirme um pedido, escolha a forma de pagamento e acompanhe a compra até a venda.

O checkout é o processo comercial principal da aplicação. Personalização, preço, pagamento e venda pertencem ao pedido; não há etapa separada de proposta administrativa.

## 2. Atores

- Visitante: consulta catálogo e cria uma conta.
- Cliente PJ: personaliza, compra e consulta seus pedidos.
- Administrador: acompanha pedidos, pagamentos, estoque e vendas.
- Sistema: calcula valores, controla reserva e processa transições automáticas.

## 3. Requisitos funcionais

| ID | Requisito |
|---|---|
| LOJ-RF01 | Exibir no catálogo apenas veículos disponíveis, não arquivados, não vendidos e sem reserva ativa. |
| LOJ-RF02 | Permitir pesquisa, ordenação e consulta dos detalhes do caminhão. |
| LOJ-RF03 | Criar conta PJ com CNPJ, razão social, contato, endereço, e-mail e senha. |
| LOJ-RF04 | Permitir login e logout e identificar a empresa autenticada. |
| LOJ-RF05 | Exibir personalizações e preços definidos pelo servidor. |
| LOJ-RF06 | Permitir escolher itens, quantidades e observações antes do checkout. |
| LOJ-RF07 | Exibir revisão com empresa, veículo, adicionais, retirada e total. |
| LOJ-RF08 | Criar um pedido e reservar o caminhão por 15 minutos. |
| LOJ-RF09 | Permitir cartão, Pix ou boleto e processar o resultado automaticamente. |
| LOJ-RF10 | Exibir estados Pendente, Processando, Aprovado, Recusado ou Cancelado. |
| LOJ-RF11 | Permitir nova tentativa após recusa enquanto o pedido continuar elegível. |
| LOJ-RF12 | Concluir venda e alterar o caminhão para Vendido quando o pagamento for aprovado. |
| LOJ-RF13 | Listar apenas os pedidos da empresa autenticada e mostrar seus detalhes. |
| LOJ-RF14 | Permitir cancelamento antes da aprovação e liberar a reserva proprietária. |
| LOJ-RF15 | Disponibilizar comprovante para pedido aprovado. |
| LOJ-RF16 | Permitir ao administrador consultar pedidos, tentativas, clientes e vendas. |
| LOJ-RF17 | Expirar reservas e tentativas pendentes que ultrapassarem o prazo. |
| LOJ-RF18 | Aceitar chaves idempotentes para pedido, pagamento e venda. |
| LOJ-RF19 | Exibir, sob demanda, o acesso administrativo da instalação local e permitir preencher o formulário de login. |

## 4. Regras de negócio

| ID | Regra |
|---|---|
| LOJ-RN01 | CNPJ é único e uma conta pertence a uma empresa. |
| LOJ-RN02 | Empresa inativa não entra na loja, cria pedido ou recebe venda. |
| LOJ-RN03 | Cada cliente acessa somente sua conta e seus pedidos. |
| LOJ-RN04 | Senhas das empresas nunca são retornadas pela API e permanecem armazenadas como hash. |
| LOJ-RN05 | Preços e total são recalculados no servidor em centavos inteiros. |
| LOJ-RN06 | Um pedido possui exatamente um caminhão e zero ou mais personalizações. |
| LOJ-RN07 | Item inválido, quantidade fora do limite ou valor enviado pelo navegador não altera o cálculo. |
| LOJ-RN08 | Somente veículo disponível, ativo e não reservado pode originar pedido. |
| LOJ-RN09 | A reserva é exclusiva e pertence ao pedido que a criou por 15 minutos. |
| LOJ-RN10 | Repetir a mesma chave e intenção devolve o registro existente; conteúdo diferente gera conflito. |
| LOJ-RN11 | Um pedido tem no máximo um pagamento aprovado. |
| LOJ-RN12 | O resultado financeiro é decidido pelo processamento do servidor, nunca por campo do navegador. |
| LOJ-RN13 | Cartão final 4242 aprova e cartão final 0002 recusa após processamento. |
| LOJ-RN14 | Pix e boleto são confirmados automaticamente pelo processador interno. |
| LOJ-RN15 | Aprovação grava pagamento, pedido, venda, evento e status Vendido na mesma transação. |
| LOJ-RN16 | Cancelamento ou expiração libera somente a reserva do próprio pedido. |
| LOJ-RN17 | Pedido aprovado não pode ser cancelado ou receber nova tentativa. |
| LOJ-RN18 | Alterações posteriores em empresa, veículo ou adicionais não reescrevem snapshots antigos. |
| LOJ-RN19 | Administrador consulta pagamentos, mas não escolhe manualmente o resultado. |
| LOJ-RN20 | O atalho administrativo retorna apenas a credencial inicial gerada localmente; não retorna senhas de clientes e não substitui autenticação. |

## 5. Requisitos não funcionais

| ID | Requisito |
|---|---|
| LOJ-RNF01 | Interface responsiva em desktop e celular, sem transbordamento horizontal. |
| LOJ-RNF02 | Ações principais possuem rótulo, foco visível e mensagens compreensíveis. |
| LOJ-RNF03 | Sessões usam cookie HttpOnly e SameSite; mutações exigem token CSRF. |
| LOJ-RNF04 | Consultas e mutações aplicam autorização por papel e propriedade. |
| LOJ-RNF05 | Regras críticas e cálculo de preço são aplicados no servidor. |
| LOJ-RNF06 | Operações de estoque e venda usam transação SQLite. |
| LOJ-RNF07 | Textos fornecidos pelo usuário são escapados na interface. |
| LOJ-RNF08 | Datas são armazenadas em UTC e valores exibidos em BRL. |
| LOJ-RNF09 | A aplicação funciona localmente com Python 3.10+ e sem pacote externo obrigatório. |
| LOJ-RNF10 | Respostas de autenticação e de acesso administrativo usam `Cache-Control: no-store`; o servidor padrão escuta apenas em `127.0.0.1`. |

## 6. Premissas e restrições

### Premissas

- A empresa informa dados verdadeiros para seu próprio cadastro.
- O caminhão é retirado na unidade indicada no checkout.
- O computador mantém relógio adequado para controlar os 15 minutos.
- O servidor local permanece ativo durante a compra.

### Restrições

- Uma conta por empresa nesta etapa.
- Sem recuperação de senha por e-mail ou confirmação de titularidade do CNPJ.
- Sem frete, entrega, nota fiscal, parcelamento, estorno ou chargeback.
- Sem integração com banco, adquirente ou rede Pix. O processamento acadêmico ocorre inteiramente no servidor local e não coleta PAN, CVV ou credenciais bancárias.
- Sem hospedagem pública e sem sincronização entre instalações.
- O botão **Admin** do cabeçalho é um recurso de apoio à execução local e deve ser removido ou protegido antes de qualquer publicação na internet.

## 7. Riscos

| Risco | Resposta |
|---|---|
| Duas empresas tentarem o mesmo caminhão | Reserva condicional transacional; apenas uma criação é aceita. |
| Duplo clique ou perda de resposta duplicar compra | Chave idempotente por intenção. |
| Navegador adulterar preço ou resultado | Servidor ignora valores e estados fora do contrato. |
| Reserva expirar durante processamento | Revalidação temporal e transação única antes da venda. |
| Cliente consultar pedido alheio | Filtro por `customer_id` e resposta sem revelar existência. |
| Falha no meio da aprovação | Rollback mantém pedido, pagamento, venda e estoque consistentes. |
| Tela pequena esconder ações | Layout responsivo, quebra de códigos e verificação mobile. |
| Credencial administrativa aparecer fora do contexto local | Manter bind em loopback, resposta sem cache e arquivo `.admin-access` ignorado pelo Git. |

## 8. Casos de uso

### LOJ-UC01 — Criar conta e entrar

**Ator:** visitante. **Fluxo:** informa dados PJ e senha → servidor valida CNPJ/e-mail → cria empresa e conta → autentica a sessão. **Alternativas:** documento ou e-mail duplicado, senha fraca e campos inválidos retornam mensagem sem criar dados parciais.

### LOJ-UC02 — Personalizar caminhão

**Ator:** visitante ou cliente. **Fluxo:** consulta catálogo → abre o caminhão → escolhe adicionais e quantidades → confere o total estimado. **Alternativa:** veículo indisponível sai do catálogo e impede continuar.

### LOJ-UC03 — Criar pedido

**Ator:** cliente autenticado. **Fluxo:** revisa empresa, caminhão, adicionais e retirada → confirma → servidor recalcula, grava snapshots e reserva por 15 minutos. **Alternativas:** empresa inativa, veículo reservado ou chave divergente geram bloqueio.

### LOJ-UC04 — Pagar pedido

**Ator:** cliente proprietário. **Fluxo:** escolhe cartão, Pix ou boleto → servidor cria tentativa → interface acompanha o processamento → aprovação registra venda e libera comprovante. **Alternativas:** recusa permite tentar novamente; expiração cancela a tentativa e libera a reserva.

### LOJ-UC05 — Consultar ou cancelar pedido

**Ator:** cliente autenticado. **Fluxo:** abre **Meus pedidos** → consulta itens, total, prazo e pagamento → cancela se ainda estiver aguardando. **Alternativas:** pedido aprovado não cancela; pedido de outra empresa não é acessível.

### LOJ-UC06 — Acompanhar pedidos

**Ator:** administrador. **Fluxo:** abre **Pedidos da loja** → pesquisa e filtra → consulta empresa, caminhão, itens, valor, prazo, pagamentos e venda. O administrador acompanha o resultado, sem aprová-lo manualmente.

### LOJ-UC07 — Recuperar acesso administrativo local

**Ator:** apresentador ou administrador local. **Fluxo:** abre **Admin** no cabeçalho → o servidor lê `data/.admin-access` → mostra e-mail e senha → **Preencher login** abre a tela de entrada com os campos preenchidos. **Alternativa:** arquivo ausente ou incompleto orienta reiniciar o servidor para gerar um novo acesso.

## 9. Critérios de aceite

- Cadastro, login e logout funcionam com isolamento entre empresas.
- Catálogo não exibe caminhão vendido, arquivado ou reservado.
- Total sempre corresponde aos preços persistidos no servidor.
- Dois pedidos concorrentes não reservam o mesmo caminhão.
- Cartão, Pix e boleto avançam sem intervenção administrativa.
- Recusa permite nova tentativa elegível.
- Aprovação cria uma única venda e marca o veículo como Vendido.
- Cancelamento e expiração liberam a reserva correta.
- Cliente consulta somente seus pedidos; admin consulta o conjunto completo.
- Checkout e pedidos permanecem utilizáveis nas larguras desktop e mobile verificadas.
- O acesso administrativo local pode ser consultado pelo cabeçalho sem expor senha de empresa ou incluir credenciais no Git.
