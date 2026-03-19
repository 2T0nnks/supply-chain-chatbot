"""
Agente de IA para Negociação — Ollama (Open Source, 100% Local)
Usa LLM local via Ollama (qwen2.5:0.5b por padrão) sem consumo de tokens externos.
Integrado ao motor de regras YAML para decisões de negociação.
"""
import json
import logging
import os
import requests
from typing import List, Dict, Optional
from backend.rules_engine import RulesEngine, NegotiationDecision

logger = logging.getLogger(__name__)

# Suporta Docker Compose (OLLAMA_HOST=http://ollama:11434) e local (http://localhost:11434)
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")


class AIAgent:
    def __init__(self, rules_engine: RulesEngine):
        self.rules = rules_engine
        ai_cfg = rules_engine.get_ai_config()
        # Modelo configurável no YAML — padrão: qwen2.5:0.5b (leve e rápido)
        self.model = ai_cfg.get("model", "qwen2.5:0.5b")
        self.max_tokens = ai_cfg.get("max_tokens", 400)
        self.temperature = ai_cfg.get("temperature", 0.4)
        self.persona = rules_engine.get_persona()
        # Rastreabilidade: armazena última decisão para auditoria
        self.last_decision_trace: Dict = {}
        self._check_ollama()

    # ------------------------------------------------------------------
    # VERIFICAÇÃO DE SAÚDE
    # ------------------------------------------------------------------

    def _check_ollama(self):
        """Verifica se Ollama está disponível e o modelo está carregado."""
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            models = [m["name"] for m in resp.json().get("models", [])]
            if any(self.model.split(":")[0] in m for m in models):
                logger.info(f"✅ Ollama pronto — modelo: {self.model}")
            else:
                logger.warning(f"⚠️ Modelo {self.model} não encontrado. Modelos disponíveis: {models}")
        except Exception as e:
            logger.warning(f"⚠️ Ollama não acessível: {e}. Usando respostas de fallback.")

    def is_available(self) -> bool:
        """Retorna True se Ollama estiver disponível."""
        try:
            requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # CHAMADA AO MODELO LOCAL
    # ------------------------------------------------------------------

    def _call_ollama(self, prompt: str, system: str = "", max_tokens: int = None) -> str:
        """Chama o modelo Ollama localmente via API REST."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens or self.max_tokens,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        }
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout ao chamar Ollama.")
            return ""
        except Exception as e:
            logger.error(f"❌ Erro ao chamar Ollama: {e}")
            return ""

    # ------------------------------------------------------------------
    # SYSTEM PROMPT COM REGRAS
    # ------------------------------------------------------------------

    def _build_system_prompt(self, extra_context: str = "") -> str:
        """Monta o system prompt com persona + regras de negócio + contexto."""
        style = self.rules.get_negotiation_style()
        disc = self.rules.rules.get("discounts", {})
        esc = self.rules.get_escalation_contact()
        contact = f"{esc.get('name','Equipe Comercial')} ({esc.get('whatsapp','')})"

        return f"""{self.persona}

## REGRAS DE NEGÓCIO ATIVAS
- Estilo: {style}
- Desconto máximo autônomo: {disc.get('max_autonomous_discount_percent', 15)}%
- Desconto máximo absoluto: {disc.get('max_absolute_discount_percent', 25)}%
- Limite para escalar: {disc.get('escalation_threshold_percent', 20)}%
- Contato escalação: {contact}

## INSTRUÇÕES
1. Use APENAS os dados de estoque e preço fornecidos no contexto.
2. Nunca invente valores, SKUs ou produtos.
3. Aplique descontos dentro dos limites — nunca ultrapasse.
4. Se precisar escalar, informe o contato e o motivo.
5. Quando estoque estiver crítico, mencione a escassez para criar urgência.
6. Respostas curtas, diretas e em português.
7. Termine sempre com uma chamada para ação clara.

{extra_context}""".strip()

    # ------------------------------------------------------------------
    # NEGOCIAÇÃO PRINCIPAL
    # ------------------------------------------------------------------

    def negotiate(
        self,
        user_message: str,
        conversation_history: List[Dict],
        order_context: Dict,
        stock_context: str = "",
        counter_round: int = 0,
    ) -> Dict:
        """
        Processa mensagem de negociação e retorna resposta da IA local.
        """
        requested_discount = order_context.get("requested_discount_percent", 0)
        order_total = order_context.get("total", 0)
        neg_ctx = self.rules.evaluate_negotiation(order_total, requested_discount, counter_round)
        order_summary = self._format_order_context(order_context)

        extra_context = f"""
## PEDIDO ATUAL
{order_summary}

## STATUS DE ESTOQUE
{stock_context if stock_context else "Estoque normal para todos os itens."}

## SITUAÇÃO DA NEGOCIAÇÃO
- Rodada: {counter_round + 1}/{neg_ctx.max_rounds}
- Desconto solicitado: {requested_discount:.1f}%
- Desconto máximo permitido agora: {neg_ctx.max_discount:.1f}%
- Pode ceder mais: {"Sim, até " + str(neg_ctx.concession_available) + "% adicional" if neg_ctx.can_concede else "Não"}
- Decisão recomendada: {neg_ctx.decision.value.upper()}
- Condições de pagamento: {", ".join(neg_ctx.payment_terms)}
{"- ESCALAÇÃO NECESSÁRIA: " + neg_ctx.escalation_message if neg_ctx.escalation_required else ""}
"""
        system_prompt = self._build_system_prompt(extra_context)

        # Monta histórico recente como texto para o prompt
        history_text = ""
        for msg in conversation_history[-4:]:
            role = "Cliente" if msg["role"] == "user" else "Assistente"
            history_text += f"{role}: {msg['content']}\n"

        prompt = f"""{history_text}Cliente: {user_message}
Assistente:"""

        if not self.is_available():
            return {
                "text": self._fallback_response(order_context, neg_ctx),
                "decision": neg_ctx.decision.value,
                "escalation_required": neg_ctx.escalation_required,
                "payment_terms": neg_ctx.payment_terms,
                "model": "fallback",
            }

        import time
        t0 = time.time()
        response_text = self._call_ollama(prompt, system=system_prompt)
        elapsed_ms = int((time.time() - t0) * 1000)

        used_fallback = False
        if not response_text:
            response_text = self._fallback_response(order_context, neg_ctx)
            used_fallback = True

        # Salva trace completo para auditoria/debug
        self.last_decision_trace = {
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "model": self.model if not used_fallback else "fallback",
            "used_fallback": used_fallback,
            "elapsed_ms": elapsed_ms,
            "user_message": user_message,
            "requested_discount_percent": requested_discount,
            "order_total": order_total,
            "counter_round": counter_round,
            "rules_applied": {
                "negotiation_style": self.rules.get_negotiation_style(),
                "max_autonomous_discount": self.rules.rules.get("discounts", {}).get("max_autonomous_discount_percent", 15),
                "escalation_threshold": self.rules.rules.get("discounts", {}).get("escalation_threshold_percent", 20),
                "max_rounds": neg_ctx.max_rounds,
            },
            "decision": neg_ctx.decision.value,
            "max_discount_allowed": neg_ctx.max_discount,
            "can_concede": neg_ctx.can_concede,
            "escalation_required": neg_ctx.escalation_required,
            "payment_terms": neg_ctx.payment_terms,
            "system_prompt_preview": system_prompt[:400] + "...",
            "prompt_sent": prompt[:300] + "...",
            "raw_ai_response": response_text,
        }
        logger.info(f"🤖 IA decidiu: {neg_ctx.decision.value.upper()} | desconto máx: {neg_ctx.max_discount}% | {elapsed_ms}ms")

        return {
            "text": response_text,
            "decision": neg_ctx.decision.value,
            "max_discount": neg_ctx.max_discount,
            "escalation_required": neg_ctx.escalation_required,
            "payment_terms": neg_ctx.payment_terms,
            "model": self.model if not used_fallback else "fallback",
            "elapsed_ms": elapsed_ms,
            "trace": self.last_decision_trace,
        }

    # ------------------------------------------------------------------
    # ANÁLISE DE INTENÇÃO (leve, sem IA — baseada em regras)
    # ------------------------------------------------------------------

    def analyze_intent(self, message: str, conversation_history: List[Dict] = None) -> Dict:
        """
        Analisa intenção da mensagem usando regras simples + LLM local.
        Rápido e sem overhead para mensagens simples.
        """
        msg_lower = message.lower().strip()

        # Regras rápidas (sem LLM) para intenções óbvias
        quick_rules = [
            (["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "start"], "saudacao"),
            (["ajuda", "help", "comandos", "o que você faz"], "ajuda"),
            (["buscar", "procurar", "pesquisar", "tem ", "possui "], "buscar_produto"),
            (["disponível", "disponivel", "estoque", "quantidade"], "verificar_estoque"),
            (["carrinho", "meu pedido", "itens"], "ver_carrinho"),
            (["proposta", "orçamento", "orcamento", "cotação", "cotacao"], "gerar_proposta"),
            (["aceito", "aceitar", "confirmo", "confirmar", "fechado", "ok", "sim"], "aceitar_proposta"),
            (["não aceito", "nao aceito", "recuso", "muito caro", "caro demais"], "rejeitar_proposta"),
            (["desconto", "% de desconto", "reduzir", "baixar preço", "melhor preço"], "negociar_preco"),
            (["adicionar", "adiciona", "quero", "comprar"], "adicionar_item"),
        ]

        for keywords, intent in quick_rules:
            if any(kw in msg_lower for kw in keywords):
                return {"intent": intent, "entities": [], "sentiment": "neutro", "urgency": "media"}

        # Para mensagens ambíguas, usa LLM local
        if self.is_available():
            system = """Classifique a intenção em JSON com campos:
intent: buscar_produto|verificar_estoque|negociar_preco|gerar_proposta|aceitar_proposta|rejeitar_proposta|contra_proposta|ver_carrinho|saudacao|ajuda|outro
sentiment: positivo|neutro|negativo
urgency: alta|media|baixa
Responda APENAS com JSON válido."""
            prompt = f'Mensagem: "{message}"\nJSON:'
            raw = self._call_ollama(prompt, system=system, max_tokens=80)
            try:
                # Extrai JSON da resposta
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(raw[start:end])
            except Exception:
                pass

        return {"intent": "outro", "entities": [], "sentiment": "neutro", "urgency": "baixa"}

    # ------------------------------------------------------------------
    # ALERTAS DE ESTOQUE
    # ------------------------------------------------------------------

    def generate_stock_alert_message(self, alerts: List[Dict]) -> str:
        """Gera mensagem de alerta de estoque com tom adequado."""
        if not alerts:
            return ""

        # Fallback rápido sem LLM
        critical = [a for a in alerts if a.get("level") == "critical"]
        low = [a for a in alerts if a.get("level") == "low"]

        lines = ["⚠️ *Alerta de Estoque*"]
        if critical:
            lines.append(f"🔴 {len(critical)} produto(s) em nível CRÍTICO!")
            for a in critical[:3]:
                lines.append(f"  • {a['name']}: apenas {a['stock']} {a.get('unit','un')} restantes")
        if low:
            lines.append(f"🟡 {len(low)} produto(s) com estoque BAIXO")

        lines.append("Recomenda-se reposição imediata.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # SUGESTÃO DE ALTERNATIVAS
    # ------------------------------------------------------------------

    def suggest_alternatives(self, sku: str, inventory_manager) -> str:
        """Sugere produtos alternativos quando estoque está indisponível."""
        product = inventory_manager.get_product(sku)
        if not product:
            return ""

        category = product.get("category", "")
        alternatives = [
            p for p in inventory_manager.data["products"]
            if p["category"] == category and p["id"] != sku and p["stock"] > 0
        ]

        if not alternatives:
            return f"Não há alternativas disponíveis na categoria {category} no momento."

        lines = [f"💡 *Alternativas para {product['name']}:*"]
        for p in alternatives[:3]:
            lines.append(
                f"  • *{p['name']}* (SKU: `{p['id']}`)\n"
                f"    R$ {p['price']:.2f} | {p['stock']} {p['unit']} disponíveis"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _format_order_context(self, order_context: Dict) -> str:
        items = order_context.get("items", [])
        total = order_context.get("total", 0)
        discount = order_context.get("applied_discount_percent", 0)
        final_total = order_context.get("final_total", total)

        if not items:
            return "Nenhum item no pedido ainda."

        lines = []
        for item in items:
            lines.append(
                f"- {item.get('product_name', item.get('sku'))}: "
                f"{item.get('quantity')} {item.get('unit','un')} "
                f"x R$ {item.get('unit_price', 0):.2f} = R$ {item.get('total_price', 0):.2f}"
            )
        summary = "\n".join(lines)
        summary += f"\nSubtotal: R$ {total:.2f}"
        if discount > 0:
            summary += f"\nDesconto: {discount:.1f}%"
        summary += f"\nTotal: R$ {final_total:.2f}"
        return summary

    def _fallback_response(self, order_context: Dict, neg_ctx=None) -> str:
        """Resposta determinística quando Ollama não está disponível."""
        total = order_context.get("total", 0)
        style = self.rules.get_negotiation_style()
        closing = self.rules.rules.get("negotiation", {}).get(
            "closing_messages", {}
        ).get(style, "Podemos prosseguir?")

        if neg_ctx and neg_ctx.escalation_required:
            contact = self.rules.get_escalation_contact()
            return (
                f"Para este pedido de R$ {total:.2f}, precisamos de aprovação especial.\n"
                f"Nossa equipe entrará em contato em até "
                f"{contact.get('response_time_hours', 2)}h. "
                f"Contato: {contact.get('whatsapp', '')}"
            )

        max_disc = neg_ctx.max_discount if neg_ctx else 15
        return (
            f"Para seu pedido de R$ {total:.2f}, posso oferecer até {max_disc:.0f}% de desconto "
            f"conforme nossas políticas comerciais. {closing}"
        )
