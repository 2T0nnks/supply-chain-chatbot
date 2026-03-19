# 🚀 Início Rápido - Supply Chain Chatbot

## ⚡ Em 5 Minutos

### 1. Acesse o Bot no Telegram

Abra o Telegram e procure por seu bot (o nome que você criou no BotFather).

**Ou clique aqui:** [Abrir Telegram](https://t.me/seu_bot_username)

### 2. Comande o Bot

Envie uma mensagem simples:

```
/start
```

### 3. Teste as Funcionalidades

**Buscar um produto:**
```
buscar parafuso
```

**Verificar disponibilidade:**
```
disponível SKU001 500
```

**Adicionar ao carrinho:**
```
adicionar SKU001 500
```

**Gerar proposta:**
```
/proposta
```

## 📋 Comandos Essenciais

| Comando | O que faz |
|---------|-----------|
| `/start` | Inicia o bot |
| `/help` | Mostra todos os comandos |
| `buscar [termo]` | Procura produtos |
| `/categorias` | Lista categorias |
| `disponível [SKU] [qtd]` | Verifica estoque |
| `adicionar [SKU] [qtd]` | Adiciona ao carrinho |
| `/carrinho` | Mostra carrinho |
| `/proposta` | Gera proposta |
| `/limpar` | Limpa carrinho |

## 🎯 Fluxo Típico

```
1. /start                    → Saudação
2. buscar corrente          → Busca produtos
3. disponível SKU002 100    → Verifica preço e disponibilidade
4. adicionar SKU002 100     → Adiciona ao carrinho
5. /proposta                → Gera proposta comercial
```

## 💡 Dicas

- Use **SKU exato** para melhor resultado (ex: SKU001)
- Quantidades maiores = **descontos automáticos**
- A proposta inclui **prazo de entrega** e **condições de pagamento**
- Você pode **adicionar múltiplos itens** antes de gerar proposta

## 📊 Exemplo Real

```
Você: oi
Bot: 👋 Olá! Bem-vindo ao assistente de estoque...

Você: buscar rolamento
Bot: ✅ Encontrados 1 produto(s):
     Rolamento 6203
     SKU: SKU003
     Preço: R$ 45.00
     Estoque: 120 unidade
     Prazo: 7 dias

Você: disponível SKU003 50
Bot: ✅ Rolamento 6203 disponível!
     Quantidade: 50 unidade
     Preço unitário: R$ 45.00
     Total: R$ 2.250,00
     Prazo: 7 dias

Você: adicionar SKU003 50
Bot: ✅ Rolamento 6203 adicionado ao carrinho!

Você: /proposta
Bot: 📋 Proposta de Negociação
     Proposta #: ABC12345
     Itens: 1
     Total: R$ 2.250,00
     Prazo: 15/04/2026
     Condições: À vista ou 15 dias
```

## 🔗 Links Úteis

- **Documentação Completa:** [README.md](./README.md)
- **Guia de Teste:** [TESTING_GUIDE.md](./TESTING_GUIDE.md)
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

## ❓ Precisa de Ajuda?

### Bot não responde?
1. Verifique se enviou `/start` primeiro
2. Aguarde alguns segundos
3. Tente novamente

### Produto não encontrado?
1. Use `/categorias` para ver o que temos
2. Tente buscar por categoria (ex: "buscar correntes")
3. Use o SKU exato (maiúsculas)

### Quer testar sem Telegram?
```bash
curl -X POST http://localhost:8000/test/message \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "user_name": "Teste", "message": "oi"}'
```

---

**Pronto! Comece a negociar! 💼**
