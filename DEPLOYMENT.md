# 🚀 Guia de Deploy - Supply Chain Chatbot

## Opções de Deploy

### 1. Deploy Local (Desenvolvimento)

```bash
cd /caminho/para/supply-chain-chatbot
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Deploy em Servidor Linux (Produção)

#### Pré-requisitos
- Ubuntu 20.04+
- Python 3.8+
- Nginx (opcional, para proxy reverso)

#### Passos

1. **Clonar repositório**
```bash
git clone seu-repo-url
cd chatbot-supply-chain
```

2. **Instalar dependências**
```bash
pip install -r requirements.txt
```

3. **Configurar variáveis de ambiente**
```bash
cp .env.example .env
nano .env  # Editar com seu token Telegram
```

4. **Criar serviço systemd**
```bash
sudo nano /etc/systemd/system/chatbot.service
```

Conteúdo:
```ini
[Unit]
Description=Supply Chain Chatbot
After=network.target

[Service]
Type=notify
User=ubuntu
WorkingDirectory=/caminho/para/supply-chain-chatbot
ExecStart=/usr/bin/python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

5. **Ativar serviço**
```bash
sudo systemctl daemon-reload
sudo systemctl enable chatbot
sudo systemctl start chatbot
sudo systemctl status chatbot
```

### 3. Deploy com Docker

#### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TELEGRAM_TOKEN=""
ENV PORT=8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  chatbot:
    build: .
    ports:
      - "8000:8000"
    environment:
      TELEGRAM_TOKEN: ${TELEGRAM_TOKEN}
    volumes:
      - ./logs:/app/logs
    restart: always
```

#### Executar
```bash
docker-compose up -d
```

### 4. Deploy em Plataformas Cloud

#### Google Cloud Run
```bash
gcloud run deploy chatbot \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars TELEGRAM_TOKEN=seu_token
```

#### DigitalOcean App Platform
- Conectar repositório GitHub
- Configurar variáveis de ambiente
- Deploy automático

---

## Configuração do Webhook

### Após Deploy

```bash
TELEGRAM_TOKEN="seu_token"
WEBHOOK_URL="https://seu-dominio.com/webhook/telegram"

curl -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"${WEBHOOK_URL}\"}"
```

### Verificar Status

```bash
curl -X GET "https://api.telegram.org/bot${TELEGRAM_TOKEN}/getWebhookInfo"
```

---

## Monitoramento

### Logs
```bash
tail -f logs/server.log
```

### Health Check
```bash
curl https://seu-dominio.com/health
```

---

## Checklist de Deploy

- [ ] Variáveis de ambiente configuradas
- [ ] Webhook configurado
- [ ] SSL/TLS ativo
- [ ] Logs funcionando
- [ ] Health check respondendo

---

**Pronto para produção! 🚀**
