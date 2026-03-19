#!/bin/bash
# =============================================================================
# Supply Chain Chatbot — Script de Setup
# =============================================================================
# Execute: bash setup.sh
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "============================================="
echo "  Supply Chain Chatbot — Setup Automático"
echo "============================================="
echo ""

# --- 1. Verificar Docker ---
echo "Verificando dependências..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker não encontrado.${NC}"
    echo "  Instale em: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✓ Docker instalado${NC} ($(docker --version | cut -d' ' -f3 | tr -d ','))"

if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ Docker Compose não encontrado.${NC}"
    echo "  Instale em: https://docs.docker.com/compose/install/"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose disponível${NC}"

# --- 2. Configurar .env ---
echo ""
if [ -f ".env" ]; then
    echo -e "${YELLOW}Arquivo .env já existe.${NC}"
    read -p "  Deseja reconfigurar o token do Telegram? (s/N): " RECONFIG
    if [[ "$RECONFIG" =~ ^[Ss]$ ]]; then
        rm .env
    fi
fi

if [ ! -f ".env" ]; then
    echo "Configurando token do Telegram..."
    echo ""
    echo "  Para obter o token:"
    echo "  1. Abra o Telegram e procure por @BotFather"
    echo "  2. Envie /newbot e siga as instruções"
    echo "  3. Copie o token gerado (formato: 123456:ABC-DEF...)"
    echo ""
    read -p "  Cole o seu TELEGRAM_TOKEN aqui: " TOKEN

    if [ -z "$TOKEN" ]; then
        echo -e "${RED}✗ Token não pode ser vazio.${NC}"
        exit 1
    fi

    echo "TELEGRAM_TOKEN=$TOKEN" > .env
    echo -e "${GREEN}✓ Arquivo .env criado${NC}"
fi

# --- 3. Subir containers ---
echo ""
echo "Subindo containers com Docker Compose..."
echo -e "${YELLOW}  Atenção: na primeira execução o download pode levar alguns minutos (~1.4 GB).${NC}"
echo ""

if command -v docker-compose &> /dev/null; then
    docker-compose up -d --build
else
    docker compose up -d --build
fi

# --- 4. Aguardar API ficar pronta ---
echo ""
echo "Aguardando a API iniciar..."
ATTEMPTS=0
MAX_ATTEMPTS=30

until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    ATTEMPTS=$((ATTEMPTS+1))
    if [ $ATTEMPTS -ge $MAX_ATTEMPTS ]; then
        echo -e "${RED}✗ API não respondeu após ${MAX_ATTEMPTS} tentativas.${NC}"
        echo "  Verifique os logs: docker-compose logs chatbot"
        exit 1
    fi
    printf "."
    sleep 5
done

echo ""
echo -e "${GREEN}✓ API rodando em http://localhost:8000${NC}"
echo -e "${GREEN}✓ Documentação em http://localhost:8000/docs${NC}"

# --- 5. Instruções do webhook ---
echo ""
echo "============================================="
echo "  Próximo passo: configurar o webhook"
echo "============================================="
echo ""
echo "  A porta 8000 está disponível no seu localhost."
echo "  Para o Telegram enviar mensagens ao bot, você precisa"
echo "  expor essa porta para a internet."
echo ""
echo "  Opção 1 — ngrok (recomendado para testes):"
echo "    ngrok http 8000"
echo ""
echo "  Opção 2 — Cloudflare Tunnel:"
echo "    cloudflared tunnel --url http://localhost:8000"
echo ""
echo "  Após obter a URL pública, configure o webhook:"
echo ""

TOKEN_VALUE=$(grep TELEGRAM_TOKEN .env | cut -d'=' -f2)
echo "    curl -X POST \"https://api.telegram.org/bot${TOKEN_VALUE}/setWebhook\" \\"
echo "      -H \"Content-Type: application/json\" \\"
echo "      -d '{\"url\": \"https://SUA_URL_PUBLICA/webhook/telegram\"}'"
echo ""
echo "  Substitua SUA_URL_PUBLICA pela URL gerada pelo ngrok ou Cloudflare."
echo ""
echo "============================================="
echo -e "  ${GREEN}Setup concluído! Bom teste! 🚀${NC}"
echo "============================================="
echo ""
