# Supply Chain Chatbot com IA (MVP)

Um chatbot inteligente para Telegram e WhatsApp que valida itens de estoque (simulando SAP/TOTVS) e realiza negociação autônoma com clientes de supply chain, utilizando **IA local Open Source** e **Compreensão de Linguagem Natural (NLU)**.

## 🧠 Inteligência Artificial e NLU

O chatbot não depende de comandos rígidos. Ele entende linguagem natural através de uma arquitetura de NLU (Natural Language Understanding) em 3 camadas:

### Como funciona a compreensão de mensagens (NLU)

1. **Camada 1: Regras Rápidas (Regex)**
   - Processamento instantâneo (< 1ms) para intenções óbvias.
   - Exemplo: *"aceita pix?"*, *"qual o prazo?"*, *"quero ver meu carrinho"*.
   - Garante respostas rápidas e determinísticas para o fluxo básico.

2. **Camada 2: LLM Local (Ollama - qwen2.5:0.5b)**
   - Processamento semântico para frases complexas e ambíguas.
   - Extrai a intenção real e as entidades (produto, quantidade, desconto).
   - Exemplo: *"preciso de uns 500 parafusos M8"*, *"esse preço tá alto, consegue melhorar?"*
   - Roda 100% local, sem consumir tokens de APIs externas.

3. **Camada 3: Fallback Heurístico**
   - Caso o LLM falhe ou o usuário digite algo muito fora do padrão, o sistema usa algoritmos de busca de palavras-chave para não deixar o cliente sem resposta.

### Motor de Negociação Autônoma

A IA toma decisões de negociação baseadas em um motor de regras configurável via YAML (`config/business_rules.yaml`):

- **Descontos autônomos:** A IA decide se aceita ou rejeita propostas até um limite pré-definido (ex: 15%).
- **Escalação:** Pedidos de desconto acima do limite são automaticamente escalados para aprovação humana.
- **Transparência:** O comando `/debug` permite auditar exatamente qual regra a IA aplicou e por que tomou determinada decisão.

---

## 🎯 Funcionalidades

- **Linguagem Natural**: Converse livremente, sem precisar decorar comandos.
- **Consulta de Estoque**: Busca produtos e verifica disponibilidade em tempo real.
- **Negociação com IA**: A IA avalia pedidos de desconto com base em regras de negócio.
- **Carrinho de Compras**: Adiciona múltiplos itens para montar propostas complexas.
- **Alertas de Estoque**: Monitoramento automático de níveis críticos de estoque.

---

## 🚀 Como Rodar com Docker Compose (Recomendado)

A forma mais fácil de rodar o projeto completo (Chatbot + Ollama + API) é usando Docker.

### Pré-requisitos
- Docker e Docker Compose instalados
- Pelo menos 2GB de RAM livre

### Passos

1. **Clone o repositório:**
```bash
git clone https://github.com/seu-usuario/supply-chain-chatbot.git
cd chatbot-supply-chain
```

2. **Configure o token do Telegram:**
Crie um arquivo `.env` na raiz do projeto:
```env
TELEGRAM_TOKEN=seu_token_do_botfather_aqui
```

3. **Suba os containers:**
```bash
docker-compose up -d
```

O Docker Compose vai:
- Subir o container do Ollama e baixar o modelo `qwen2.5:0.5b` automaticamente.
- Subir a API FastAPI na porta 8000.
- Conectar a API ao Ollama.

4. **Configure o Webhook do Telegram:**
Exponha a porta 8000 para a internet (usando ngrok, cloudflare, etc) e configure o webhook:
```bash
curl -X POST https://api.telegram.org/bot{SEU_TOKEN}/setWebhook \
  -H "Content-Type: application/json" \
  -d '{"url": "https://seu-dominio.com/webhook/telegram"}'
```

---

## 💻 Como Rodar Localmente (Sem Docker)

### Pré-requisitos
- Python 3.8+
- Ollama instalado localmente (`curl -fsSL https://ollama.com/install.sh | sh`)

### Passos

1. **Inicie o Ollama e baixe o modelo:**
```bash
ollama serve &
ollama pull qwen2.5:0.5b
```

2. **Instale as dependências Python:**
```bash
pip install -r requirements.txt
```

3. **Configure a variável de ambiente:**
```bash
export TELEGRAM_TOKEN="seu_token_aqui"
```

4. **Inicie o servidor:**
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

---

## ⚙️ Configuração das Regras de Negócio

Você não precisa alterar o código para mudar o comportamento da IA. Basta editar o arquivo `config/business_rules.yaml`:

```yaml
ai:
  model: "qwen2.5:0.5b"
  negotiation_style: "neutro"

discounts:
  max_autonomous_discount_percent: 15
  escalation_threshold_percent: 20

stock_alerts:
  critical_threshold_percent: 10
```

---

## 📱 Exemplos de Interação no Telegram

Você pode falar naturalmente com o bot:

**Buscando e Adicionando:**
> *"vocês têm corrente de aço?"*
> *"preciso de 500 parafusos M8"*
> *"quero comprar 300 metros de correia"*

**Negociando:**
> *"esse preço tá alto, consegue me dar 15% de desconto?"*
> *(A IA avalia a regra e aceita)*
> *"quero 30% de desconto"*
> *(A IA avalia a regra e avisa que precisa escalar para a gerência)*

**Fechando negócio:**
> *"pode fechar, topei"*
> *"aceita boleto parcelado?"*
> *"qual o prazo de entrega pra São Paulo?"*

**Auditoria:**
> `"/debug"` *(Mostra o raciocínio completo da IA na última decisão)*

---

## 📁 Estrutura do Projeto

```
chatbot-supply-chain/
├── backend/
│   ├── main.py                 # API FastAPI e Webhooks
│   ├── chatbot_logic.py        # Lógica central e roteamento
│   ├── nlu.py                  # Motor de Linguagem Natural (Regex + Ollama)
│   ├── ai_agent.py             # Agente de negociação IA
│   ├── rules_engine.py         # Processador do YAML de regras
│   ├── stock_monitor.py        # Alertas de estoque
│   ├── inventory.py            # Gerenciamento de estoque mockado
│   └── negotiation.py          # Gerenciamento de propostas
├── config/
│   └── business_rules.yaml     # Regras de negócio configuráveis
├── data/
│   └── products.json           # Banco de dados mockado
├── Dockerfile                  # Imagem da API
├── docker-compose.yml          # Orquestração (API + Ollama)
├── requirements.txt            # Dependências Python
└── README.md                   # Documentação
```

---

**Desenvolvido para Supply Chain B2B** 🚀
