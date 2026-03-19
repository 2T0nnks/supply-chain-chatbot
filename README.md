# Supply Chain Chatbot com IA (MVP)

Chatbot inteligente para **Telegram** que valida itens de estoque (simulando SAP/TOTVS) e realiza negociação autônoma com clientes de supply chain, utilizando **IA local Open Source** e **Compreensão de Linguagem Natural (NLU)**.

---

## Portas utilizadas

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| API FastAPI (Chatbot) | `8000` | Recebe mensagens do Telegram via webhook |
| Ollama (IA local) | `11434` | Motor de IA — comunicação interna entre containers |

> A porta `11434` do Ollama é exposta apenas para uso interno. A única porta que precisa ser acessível externamente é a `8000`.

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/install/) instalados
- Pelo menos **2 GB de RAM livre**
- Um **token de bot do Telegram** (veja o [SETUP_GUIDE.md](./SETUP_GUIDE.md) para criar o seu)
- Uma forma de expor a porta `8000` para a internet (ngrok, Cloudflare Tunnel, etc.)

---

## Início rápido (Docker)

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/supply-chain-chatbot.git
cd supply-chain-chatbot
```

### 2. Configure o token do Telegram

```bash
cp .env.example .env
```

Abra o arquivo `.env` e preencha com o seu token:

```env
TELEGRAM_TOKEN=seu_token_do_botfather_aqui
```

### 3. Suba os containers

```bash
docker-compose up -d
```

Na primeira execução, o Docker vai:
- Baixar a imagem do Ollama (~1 GB)
- Baixar o modelo de IA `qwen2.5:0.5b` (~400 MB)
- Construir e iniciar a API na porta `8000`

Acompanhe os logs até ver `Application startup complete`:

```bash
docker-compose logs -f chatbot
```

### 4. Exponha a porta 8000 para a internet

O Telegram precisa conseguir enviar mensagens para a sua API. Use o **ngrok** para isso:

```bash
# Instale o ngrok: https://ngrok.com/download
ngrok http 8000
```

O ngrok vai gerar uma URL pública como `https://abcd-1234.ngrok-free.app`.

### 5. Configure o webhook do Telegram

Substitua `SEU_TOKEN` e `SUA_URL_NGROK` pelos seus valores:

```bash
curl -X POST "https://api.telegram.org/botSEU_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://SUA_URL_NGROK/webhook/telegram"}'
```

Resposta esperada:
```json
{"ok": true, "result": true, "description": "Webhook was set"}
```

### 6. Teste no Telegram

Abra o Telegram, encontre o seu bot e envie `/start`. Pronto!

---

## Como rodar localmente (sem Docker)

Útil para desenvolvimento e depuração.

### 1. Instale o Ollama e baixe o modelo

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull qwen2.5:0.5b
```

### 2. Instale as dependências Python

```bash
pip install -r requirements.txt
```

### 3. Configure as variáveis de ambiente

```bash
export TELEGRAM_TOKEN="seu_token_aqui"
export OLLAMA_HOST="http://localhost:11434"
```

### 4. Inicie o servidor

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

A API estará disponível em `http://localhost:8000`.  
A documentação interativa (Swagger) em `http://localhost:8000/docs`.

---

## Configuração das regras de negócio

Nenhuma linha de código precisa ser alterada para mudar o comportamento da IA. Basta editar o arquivo `config/business_rules.yaml`:

```yaml
ai:
  model: "qwen2.5:0.5b"        # Modelo Ollama a ser usado
  negotiation_style: "neutro"  # agressivo | neutro | conservador

discounts:
  max_autonomous_discount_percent: 15   # IA aceita até 15% sozinha
  escalation_threshold_percent: 20      # Acima de 20%, escala para humano

stock_alerts:
  critical_threshold_percent: 10        # Estoque crítico abaixo de 10%
  low_threshold_percent: 20             # Estoque baixo abaixo de 20%
  scarcity_markup_percent: 8            # Markup automático em escassez
```

Após editar, reinicie o container do chatbot:

```bash
docker-compose restart chatbot
```

---

## Como a IA funciona (NLU em 3 camadas)

O chatbot não depende de comandos rígidos. Toda mensagem passa por um pipeline de **NLU (Natural Language Understanding)** antes de ser processada:

### Camada 1 — Regras Rápidas (Regex)

Processamento instantâneo (< 1ms) para intenções diretas e previsíveis. Garante respostas rápidas e determinísticas para o fluxo básico do negócio, sem depender de IA.

Exemplos reconhecidos: *"aceita pix?"*, *"qual o prazo?"*, *"quero ver meu carrinho"*, *"quero 15% de desconto"*.

### Camada 2 — LLM Local (Ollama)

Para frases mais complexas ou ambíguas que não casam com nenhuma regra, o modelo `qwen2.5:0.5b` extrai a intenção real e as entidades da mensagem (produto, quantidade, desconto solicitado). Roda **100% local**, sem consumir tokens de APIs externas.

Exemplos reconhecidos: *"preciso de uns 500 parafusos M8"*, *"esse preço tá alto, consegue melhorar?"*, *"bora fechar negócio"*.

### Camada 3 — Fallback Heurístico

Se o LLM falhar ou a mensagem for muito fora do padrão, um algoritmo de busca por palavras-chave garante que o cliente sempre receba uma resposta, sem travar a conversa.

### Motor de Negociação Autônoma

A IA toma decisões de negociação com base nas regras do YAML:

- **Aceita** propostas de desconto dentro do limite configurado.
- **Escala** automaticamente pedidos acima do limite para aprovação humana.
- **Transparência total:** o comando `/debug` mostra o raciocínio completo da IA na última decisão — qual regra foi aplicada, qual foi a decisão e por quê.

---

## Exemplos de interação

Você pode falar naturalmente com o bot:

**Consultando estoque:**
> *"vocês têm corrente de aço?"*
> *"tem rolamento 6203 disponível?"*
> *"quero ver os produtos de fixação"*

**Adicionando ao carrinho:**
> *"preciso de 500 parafusos M8"*
> *"quero comprar 300 metros de correia"*
> *"adiciona 10 rolamentos pra mim"*

**Negociando:**
> *"esse preço tá alto, consegue me dar 15% de desconto?"*
> *(A IA avalia a regra e aceita)*
> *"quero 30% de desconto"*
> *(A IA avalia e escala para a gerência)*

**Fechando negócio:**
> *"pode fechar, topei"*
> *"aceita boleto parcelado?"*
> *"qual o prazo de entrega?"*

**Auditando a IA:**
> `/debug` — Mostra o raciocínio completo da última decisão

---

## Estrutura do projeto

```
supply-chain-chatbot/
├── backend/
│   ├── main.py              # API FastAPI e webhook do Telegram
│   ├── chatbot_logic.py     # Lógica central e roteamento de mensagens
│   ├── nlu.py               # Motor NLU (Regex + Ollama + Heurística)
│   ├── ai_agent.py          # Agente de negociação com IA
│   ├── rules_engine.py      # Lê e aplica as regras do YAML
│   ├── stock_monitor.py     # Alertas automáticos de estoque crítico
│   ├── inventory.py         # Gerenciamento de estoque mockado
│   └── negotiation.py       # Gerenciamento de propostas comerciais
├── config/
│   └── business_rules.yaml  # Regras de negócio configuráveis (sem código)
├── data/
│   └── products.json        # Produtos mockados (substitua por SAP/TOTVS)
├── .env.example             # Modelo de configuração de variáveis
├── Dockerfile               # Imagem Docker da API
├── docker-compose.yml       # Orquestração completa (API + Ollama)
├── requirements.txt         # Dependências Python
├── SETUP_GUIDE.md           # Guia para criar o bot no Telegram
└── README.md                # Este arquivo
```

---

## Roadmap

- [ ] Integração real com SAP via RFC/BAPI
- [ ] Integração real com TOTVS via REST API
- [ ] Persistência de histórico de negociações (banco de dados)
- [ ] Sistema de autenticação de clientes
- [ ] Dashboard de acompanhamento de propostas
- [ ] Suporte a WhatsApp Business API

---

**Desenvolvido para Supply Chain B2B**
