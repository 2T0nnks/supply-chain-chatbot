# 🛠️ Guia de Configuração: Crie seu próprio Chatbot

Este guia explica passo a passo como criar um bot no Telegram, obter o token e configurar este projeto para rodar na sua própria máquina usando Docker.

## Passo 1: Criar o Bot no Telegram

1. Abra o aplicativo do **Telegram** (no celular ou computador).
2. Na barra de busca, digite `@BotFather` (é o bot oficial do Telegram com um selo azul de verificação).
3. Inicie uma conversa com ele clicando em **Start** (ou enviando `/start`).
4. Envie o comando `/newbot` para criar um novo bot.
5. O BotFather vai pedir um **nome** para o seu bot (ex: `Meu Supply Bot`).
6. Depois, ele vai pedir um **username** (deve terminar obrigatoriamente com `bot`, ex: `meu_supply_bot`).
7. Se o nome estiver disponível, o BotFather enviará uma mensagem de sucesso contendo o seu **Token de Acesso**.

> ⚠️ **IMPORTANTE:** O token se parece com isso: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`. **Guarde este token com segurança** e não compartilhe com ninguém. Ele é a "senha" do seu bot.

## Passo 2: Preparar o Ambiente

Você precisará do **Docker** e do **Docker Compose** instalados na sua máquina.

1. Clone o repositório do projeto:
```bash
git clone https://github.com/seu-usuario/supply-chain-chatbot.git
cd chatbot-supply-chain
```

2. Crie o arquivo de configuração a partir do exemplo:
```bash
cp .env.example .env
```

3. Abra o arquivo `.env` recém-criado em um editor de texto e cole o seu token:
```env
TELEGRAM_TOKEN=cole_seu_token_aqui
```

## Passo 3: Subir a Aplicação (Docker)

Com o token configurado, você já pode subir toda a infraestrutura (Chatbot + IA Local) com um único comando:

```bash
docker-compose up -d
```

**O que vai acontecer agora?**
- O Docker vai baixar a imagem do **Ollama** (motor de IA).
- O serviço `ollama-setup` vai baixar automaticamente o modelo `qwen2.5:0.5b` (isso pode demorar alguns minutos dependendo da sua internet).
- O serviço `chatbot` (a API FastAPI) será construído e iniciado na porta `8000`.

Para acompanhar o processo e ver se tudo deu certo, use:
```bash
docker-compose logs -f
```
Quando você vir a mensagem `Application startup complete` e `Modelo baixado com sucesso`, o sistema estará pronto!

## Passo 4: Configurar o Webhook (Conectar a API ao Telegram)

Para que o Telegram consiga enviar mensagens para o seu bot, sua API (que está rodando na porta 8000) precisa estar acessível na internet.

Se você está rodando localmente (no seu PC), a forma mais fácil é usar o **Ngrok**:

1. Instale e rode o ngrok apontando para a porta 8000:
```bash
ngrok http 8000
```
2. O ngrok vai gerar uma URL pública segura (ex: `https://abcd-123.ngrok-free.app`).
3. Configure o webhook do Telegram com essa URL usando o seguinte comando no terminal (substitua o token e a URL pelos seus):

```bash
curl -X POST "https://api.telegram.org/botSEU_TOKEN_AQUI/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://SUA_URL_NGROK/webhook/telegram"}'
```

Se retornar `{"ok":true,"result":true,"description":"Webhook was set"}`, **está tudo pronto!**

## Passo 5: Testar! 🎉

Abra o Telegram, procure pelo seu bot (pelo username que você criou no Passo 1) e envie:
```
/start
```
Depois tente falar com ele naturalmente:
```
"vocês têm parafuso?"
"quero comprar 500 unidades"
"tá caro, consegue um desconto de 15%?"
```

## Personalização (Opcional)

Se quiser mudar o comportamento da IA, os limites de desconto ou as regras de negócio, basta editar o arquivo `config/business_rules.yaml` e reiniciar o container do chatbot:

```bash
docker-compose restart chatbot
```
