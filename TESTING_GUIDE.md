# 🧪 Guia de Teste do Chatbot

## ✅ Status do Servidor

O servidor está rodando e configurado para receber mensagens do Telegram via webhook.

**Informações do Servidor:**
- 🌐 URL Local: `http://localhost:8000`
- 🌐 URL Pública: `https://seu-dominio.com`
- 📊 Documentação: `http://localhost:8000/docs`
- 🔗 Webhook Telegram: Configurado e ativo

## 📱 Como Testar no Telegram

### Opção 1: Usar o Bot Criado

1. Abra o Telegram
2. Procure por seu bot (nome que você criou no BotFather)
3. Clique em "Iniciar" ou envie `/start`
4. Comece a conversar!

### Opção 2: Testar via API (sem Telegram)

Use o endpoint de teste para simular mensagens:

```bash
curl -X POST http://localhost:8000/test/message \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "user_name": "João",
    "message": "oi"
  }'
```

## 🎯 Cenários de Teste Recomendados

### Teste 1: Buscar Produtos
```
Usuário: buscar parafuso
Esperado: Lista de produtos com parafuso
```

### Teste 2: Verificar Disponibilidade
```
Usuário: disponível SKU001 500
Esperado: Informações de disponibilidade e preço com desconto
```

### Teste 3: Adicionar ao Carrinho
```
Usuário: adicionar SKU001 500
Esperado: Confirmação de adição ao carrinho
```

### Teste 4: Gerar Proposta
```
Usuário: /proposta
Esperado: Proposta de negociação com ID, valores e condições
```

### Teste 5: Explorar Categorias
```
Usuário: /categorias
Esperado: Lista de todas as categorias de produtos
```

### Teste 6: Ver Ajuda
```
Usuário: /help
Esperado: Lista de todos os comandos disponíveis
```

## 📊 Produtos Disponíveis para Teste

| SKU | Produto | Preço | Estoque | Categoria |
|-----|---------|-------|---------|-----------|
| SKU001 | Parafuso M8x50 | R$ 0.85 | 5000 un | Fixação |
| SKU002 | Corrente de Aço 10mm | R$ 12.50 | 250 m | Correntes |
| SKU003 | Rolamento 6203 | R$ 45.00 | 120 un | Rolamentos |
| SKU004 | Correia Transportadora 500mm | R$ 89.90 | 45 un | Correias |
| SKU005 | Óleo Hidráulico ISO 46 | R$ 28.75 | 800 L | Lubrificantes |
| SKU006 | Polia de Alumínio 100mm | R$ 65.00 | 80 un | Polias |
| SKU007 | Mancal de Ferro Fundido | R$ 150.00 | 30 un | Mancais |
| SKU008 | Corrente de Transmissão #60 | R$ 35.50 | 200 m | Correntes |

## 💰 Tabela de Descontos

| Quantidade | Desconto |
|-----------|----------|
| 100-499 | 5% |
| 500-999 | 10% |
| 1000-4999 | 15% |
| 5000+ | 20% |

## 🔍 Endpoints para Teste Direto

### 1. Listar Categorias
```bash
curl http://localhost:8000/inventory/categories
```

### 2. Buscar Produtos
```bash
curl "http://localhost:8000/inventory/search?q=parafuso"
```

### 3. Obter Produto Específico
```bash
curl http://localhost:8000/inventory/product/SKU001
```

### 4. Verificar Disponibilidade
```bash
curl "http://localhost:8000/inventory/availability/SKU001?quantity=500"
```

### 5. Calcular Preço
```bash
curl "http://localhost:8000/inventory/price/SKU001?quantity=500"
```

### 6. Processar Mensagem
```bash
curl -X POST http://localhost:8000/test/message \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "user_name": "Cliente Teste",
    "message": "buscar rolamento"
  }'
```

## 📋 Fluxo Completo de Negociação

1. **Saudação**
   ```
   /start
   ```

2. **Buscar Produtos**
   ```
   buscar corrente
   ```

3. **Verificar Disponibilidade**
   ```
   disponível SKU002 100
   ```

4. **Adicionar ao Carrinho (múltiplos itens)**
   ```
   adicionar SKU002 100
   adicionar SKU003 50
   ```

5. **Ver Carrinho**
   ```
   /carrinho
   ```

6. **Gerar Proposta**
   ```
   /proposta
   ```

7. **Negociar**
   ```
   negociar 5000
   ```

## 🐛 Troubleshooting

### Problema: Bot não responde no Telegram
**Solução:**
- Verifique se o webhook está configurado: `curl -s -X GET "https://api.telegram.org/bot{TOKEN}/getWebhookInfo"`
- Verifique se o servidor está rodando: `curl http://localhost:8000/health`
- Verifique os logs: `tail -f logs/server.log`

### Problema: Erro "Produto não encontrado"
**Solução:**
- Use `/categorias` para ver produtos disponíveis
- Verifique o SKU exato (maiúsculas)
- Tente buscar por nome: `buscar parafuso`

### Problema: Desconto não está sendo aplicado
**Solução:**
- Verifique se a quantidade atinge o mínimo para desconto (100 un)
- Consulte a tabela de descontos acima

## 📈 Monitoramento

### Ver Logs do Servidor
```bash
tail -f /caminho/para/supply-chain-chatbot/logs/server.log
```

### Verificar Status da Aplicação
```bash
curl http://localhost:8000/health
```

### Listar Todos os Produtos
```bash
curl http://localhost:8000/inventory/products | python -m json.tool
```

## 🎓 Exemplos de Conversas

### Exemplo 1: Cliente Busca Parafusos
```
Cliente: oi
Bot: 👋 Olá! Bem-vindo...

Cliente: buscar parafuso
Bot: ✅ Encontrados 1 produto(s)...

Cliente: disponível SKU001 1000
Bot: ✅ Parafuso M8x50 disponível...

Cliente: adicionar SKU001 1000
Bot: ✅ Adicionado ao carrinho...

Cliente: /proposta
Bot: 📋 Proposta de Negociação...
```

### Exemplo 2: Cliente Negocia Múltiplos Itens
```
Cliente: buscar corrente
Bot: ✅ Encontrados 2 produtos...

Cliente: adicionar SKU002 100
Bot: ✅ Adicionado...

Cliente: adicionar SKU008 50
Bot: ✅ Adicionado...

Cliente: /carrinho
Bot: 🛒 Seu Carrinho (2 itens)...

Cliente: /proposta
Bot: 📋 Proposta com desconto volume...
```

## 📞 Suporte

Para dúvidas técnicas, consulte:
- README.md - Documentação geral
- backend/chatbot_logic.py - Lógica do chatbot
- backend/inventory.py - Gerenciamento de estoque
- backend/negotiation.py - Lógica de negociação

---

**Pronto para testar! 🚀**
