import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
from backend.chatbot_logic import ChatbotLogic

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variáveis de ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "TELEGRAM_TOKEN_REMOVED")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Inicializar FastAPI
app = FastAPI(title="Supply Chain Chatbot", version="1.0.0")

# Inicializar lógica do chatbot
chatbot = ChatbotLogic()

@app.on_event("startup")
async def startup():
    """Evento de inicialização"""
    logger.info("🚀 Chatbot iniciado com sucesso!")
    logger.info(f"Token Telegram configurado: {TELEGRAM_TOKEN[:10]}...")

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "ok",
        "service": "Supply Chain Chatbot",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    """Health check detalhado"""
    ai_ok = chatbot.ai.is_available()
    alerts = chatbot.stock_monitor.get_low_products()
    return {"ai_local": ai_ok, "ai_model": chatbot.ai.model, "stock_alerts": len(alerts),
        "status": "healthy",
        "service": "Supply Chain Chatbot",
        "telegram_configured": bool(TELEGRAM_TOKEN),
        "chatbot_ready": True
    }

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Webhook para receber mensagens do Telegram"""
    try:
        data = await request.json()
        logger.info(f"📨 Mensagem recebida: {data}")
        
        # Verifica se é uma mensagem de texto
        if "message" not in data:
            return JSONResponse({"ok": True})
        
        message = data["message"]
        
        # Extrai informações
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        user_name = message["from"].get("first_name", "Usuário")
        text = message.get("text", "")
        
        logger.info(f"👤 Usuário: {user_name} (ID: {user_id})")
        logger.info(f"💬 Mensagem: {text}")
        
        # Processa mensagem com o chatbot
        response = chatbot.process_message(user_id, user_name, text)
        
        # Envia resposta
        await send_telegram_message(chat_id, response)
        
        return JSONResponse({"ok": True})
    
    except Exception as e:
        logger.error(f"❌ Erro ao processar webhook: {str(e)}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

async def send_telegram_message(chat_id: int, response: dict):
    """Envia mensagem para o Telegram"""
    try:
        # Prepara o texto da mensagem
        text = response.get("text", "")
        
        # Envia mensagem
        async with httpx.AsyncClient() as client:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            
            response_data = await client.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json=payload
            )
            
            if response_data.status_code != 200:
                logger.error(f"❌ Erro ao enviar mensagem: {response_data.text}")
            else:
                logger.info(f"✅ Mensagem enviada para chat {chat_id}")
    
    except Exception as e:
        logger.error(f"❌ Erro ao enviar mensagem Telegram: {str(e)}")

@app.post("/test/message")
async def test_message(user_id: int = 123, user_name: str = "Teste", message: str = "oi"):
    """Endpoint de teste para processar mensagens sem Telegram"""
    try:
        response = chatbot.process_message(user_id, user_name, message)
        return response
    except Exception as e:
        logger.error(f"❌ Erro ao processar mensagem de teste: {str(e)}")
        return {"error": str(e)}, 500

@app.get("/inventory/products")
async def get_products():
    """Lista todos os produtos"""
    return {
        "products": chatbot.inventory.data["products"]
    }

@app.get("/inventory/categories")
async def get_categories():
    """Lista categorias"""
    return {
        "categories": chatbot.inventory.get_all_categories()
    }

@app.get("/inventory/search")
async def search_products(q: str):
    """Busca produtos"""
    results = chatbot.inventory.search_product(q)
    return {
        "query": q,
        "results": results,
        "count": len(results)
    }

@app.get("/inventory/product/{sku}")
async def get_product(sku: str):
    """Obtém detalhes de um produto"""
    product = chatbot.inventory.get_product(sku)
    if not product:
        return {"error": "Produto não encontrado"}, 404
    return product

@app.get("/inventory/availability/{sku}")
async def check_availability(sku: str, quantity: int = 1):
    """Verifica disponibilidade"""
    return chatbot.inventory.check_availability(sku, quantity)

@app.get("/inventory/price/{sku}")
async def get_price(sku: str, quantity: int = 1):
    """Calcula preço"""
    pricing = chatbot.inventory.calculate_price(sku, quantity)
    if not pricing:
        return {"error": "Produto não encontrado"}, 404
    return pricing

@app.get("/debug/last")
async def debug_last_decision():
    """
    Mostra o raciocínio completo da última decisão da IA.
    Inclui: prompt enviado, resposta bruta, regras aplicadas e métricas.
    """
    trace = chatbot.ai.last_decision_trace
    if not trace:
        return {
            "message": "Nenhuma decisão registrada ainda. Faça uma negociação primeiro.",
            "tip": "Use POST /debug/simulate para testar sem Telegram"
        }
    return trace


@app.post("/debug/simulate")
async def debug_simulate(body: dict):
    """
    Simula uma negociação completa e retorna o trace da IA.
    Body: {"user_id": "test", "user_name": "Teste", "messages": ["adicionar SKU001 500", "quero 20% de desconto"]}
    """
    user_id = body.get("user_id", "debug_user")
    user_name = body.get("user_name", "Debug")
    messages = body.get("messages", [])
    results = []
    for msg in messages:
        resp = chatbot.process_message(user_id, user_name, msg)
        results.append({
            "input": msg,
            "response_text": resp.get("text", ""),
            "type": resp.get("type"),
            "decision": resp.get("decision"),
            "max_discount": resp.get("max_discount"),
            "trace": resp.get("trace"),
        })
    return {
        "simulation_results": results,
        "last_ai_trace": chatbot.ai.last_decision_trace,
    }


@app.get("/debug/rules")
async def debug_rules():
    """Mostra as regras de negócio ativas carregadas do YAML."""
    rules = chatbot.rules.rules
    return {
        "source": "config/business_rules.yaml",
        "negotiation_style": chatbot.rules.get_negotiation_style(),
        "ai_model": chatbot.ai.model,
        "discounts": rules.get("discounts", {}),
        "stock_alerts": rules.get("stock_alerts", {}),
        "payment_conditions": rules.get("payment_conditions", {}),
        "escalation_contact": chatbot.rules.get_escalation_contact(),
        "persona_preview": chatbot.rules.get_persona()[:200] + "...",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
