"""
Lógica Principal do Chatbot
Integra IA local (Ollama), motor de regras YAML, monitor de estoque e NLU.
"""
import re
import logging
from typing import Dict, List, Optional
from backend.inventory import InventoryManager
from backend.negotiation import NegotiationManager
from backend.rules_engine import RulesEngine
from backend.stock_monitor import StockMonitor
from backend.ai_agent import AIAgent
from backend.nlu import NLUEngine

logger = logging.getLogger(__name__)


class ChatbotLogic:
    def __init__(self):
        self.inventory = InventoryManager()
        self.negotiation = NegotiationManager()
        self.rules = RulesEngine()
        self.stock_monitor = StockMonitor(self.inventory, self.rules)
        self.ai = AIAgent(self.rules)
        self.nlu = NLUEngine(model=self.ai.model)  # Usa mesmo modelo da IA
        self.user_contexts: Dict[str, Dict] = {}
        logger.info("✅ ChatbotLogic inicializado com IA local (Ollama) + NLU + motor de regras.")

    # ------------------------------------------------------------------
    # CONTEXTO DO USUÁRIO
    # ------------------------------------------------------------------

    def _get_user_context(self, user_id: str) -> Dict:
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = {
                "session_id": self.negotiation.create_session(user_id),
                "last_search": None,
                "last_product": None,
                "state": "idle",
                "history": [],          # Histórico para a IA
                "counter_round": 0,     # Rodadas de contra-proposta
                "last_proposal_id": None,
            }
        return self.user_contexts[user_id]

    def _add_to_history(self, user_id: str, role: str, content: str):
        ctx = self._get_user_context(user_id)
        ctx["history"].append({"role": role, "content": content})
        # Mantém apenas as últimas 10 mensagens
        if len(ctx["history"]) > 10:
            ctx["history"] = ctx["history"][-10:]

    def _get_order_context(self, user_id: str, requested_discount: float = 0) -> Dict:
        """Monta contexto do pedido atual para a IA."""
        ctx = self._get_user_context(user_id)
        session = self.negotiation.user_sessions.get(ctx["session_id"], {})
        items = session.get("items", [])
        total = sum(i.get("total_price", 0) for i in items)
        discount = session.get("additional_discount_percent", 0)
        final_total = total * (1 - discount / 100)
        return {
            "items": items,
            "total": total,
            "applied_discount_percent": discount,
            "final_total": final_total,
            "requested_discount_percent": requested_discount,
        }

    # ------------------------------------------------------------------
    # ROTEADOR PRINCIPAL COM NLU
    # ------------------------------------------------------------------

    def process_message(self, user_id: str, user_name: str, message: str) -> Dict:
        """Processa mensagem em linguagem natural usando NLU + IA."""
        ctx = self._get_user_context(user_id)
        msg = message.strip()

        # Registra no histórico
        self._add_to_history(user_id, "user", msg)

        # Analisa intenção com NLU
        nlu = self.nlu.parse(msg)
        logger.info(f"🧠 NLU: intent={nlu.intent} | conf={nlu.confidence:.2f} | "
                    f"produto={nlu.product_name} | sku={nlu.sku} | qty={nlu.quantity} | "
                    f"desconto={nlu.discount_percent}%")

        # Armazena último NLU no contexto para debug
        ctx["last_nlu"] = {
            "intent": nlu.intent,
            "confidence": nlu.confidence,
            "product_name": nlu.product_name,
            "sku": nlu.sku,
            "quantity": nlu.quantity,
            "discount_percent": nlu.discount_percent,
            "raw_text": msg,
        }

        # Roteamento por intenção
        if nlu.intent == "saudacao":
            return self._handle_greeting(user_id, user_name)

        if nlu.intent == "ajuda":
            return self._handle_help()

        if nlu.intent == "ver_carrinho":
            return self._handle_show_cart(user_id)

        if nlu.intent == "gerar_proposta":
            return self._handle_generate_proposal(user_id)

        if nlu.intent == "limpar_carrinho":
            return self._handle_clear_cart(user_id)

        if nlu.intent == "alertas_estoque":
            return self._handle_stock_alerts()

        if nlu.intent == "debug":
            return self._handle_debug(user_id)

        if nlu.intent == "buscar_produto":
            query = nlu.product_name or nlu.sku or msg
            return self._handle_search(user_id, query)

        if nlu.intent == "ver_estoque":
            return self._handle_check_availability_nlu(user_id, nlu)

        if nlu.intent == "adicionar_item":
            return self._handle_add_to_cart_nlu(user_id, nlu)

        if nlu.intent == "negociar":
            return self._handle_negotiation_nlu(user_id, msg, nlu)

        if nlu.intent == "aceitar":
            return self._handle_accept_proposal(user_id, msg)

        if nlu.intent == "rejeitar":
            return self._handle_reject_proposal(user_id, msg)

        if nlu.intent == "prazo_entrega":
            return self._handle_delivery_info(user_id, nlu)

        if nlu.intent == "condicao_pagto":
            return self._handle_payment_info(user_id, nlu)

        # Fallback: IA responde livremente
        return self._handle_ai_fallback(user_id, user_name, msg)

    # HANDLERS
    # ------------------------------------------------------------------

    def _handle_greeting(self, user_id: str, user_name: str) -> Dict:
        # Verifica alertas de estoque para incluir na saudação
        alerts = self.stock_monitor.get_critical_products()
        alert_note = ""
        if alerts:
            alert_note = f"\n\n⚠️ *{len(alerts)} produto(s) com estoque crítico.* Digite `/estoque` para ver."

        text = (
            f"👋 Olá, *{user_name}*! Bem-vindo ao assistente de supply chain.\n\n"
            f"Posso ajudar você a:\n"
            f"• 🔍 Buscar produtos no estoque\n"
            f"• 📦 Verificar disponibilidade\n"
            f"• 💰 Negociar preços e condições\n"
            f"• 📋 Gerar propostas comerciais"
            f"{alert_note}\n\n"
            f"Digite `/help` para ver todos os comandos."
        )
        response = {"type": "greeting", "text": text}
        self._add_to_history(user_id, "assistant", text)
        return response

    def _handle_help(self) -> Dict:
        text = (
            "📋 *Comandos disponíveis:*\n\n"
            "🔍 *Busca:*\n"
            "• `buscar [nome/SKU]` — Procura produtos\n"
            "• `/categorias` — Lista categorias\n\n"
            "📦 *Estoque:*\n"
            "• `disponível [SKU] [qtd]` — Verifica disponibilidade\n"
            "• `/estoque` — Alertas de estoque crítico\n\n"
            "🛒 *Carrinho:*\n"
            "• `adicionar [SKU] [qtd]` — Adiciona ao carrinho\n"
            "• `/carrinho` — Ver itens\n"
            "• `/limpar` — Limpar carrinho\n\n"
            "💰 *Negociação:*\n"
            "• `/proposta` — Gera proposta\n"
            "• `desconto [%]` — Solicita desconto\n"
            "• `aceitar [ID]` — Aceita proposta\n"
            "• `rejeitar [ID]` — Rejeita proposta"
        )
        return {"type": "help", "text": text}

    def _handle_search(self, user_id: str, query: str) -> Dict:
        ctx = self._get_user_context(user_id)
        ctx["last_search"] = query
        results = self.inventory.search_product(query)

        if not results:
            text = (
                f"❌ Nenhum produto encontrado para *'{query}'*.\n\n"
                f"Tente outro termo ou use `/categorias` para navegar."
            )
            return {"type": "search_result", "text": text}

        text = f"✅ *{len(results)} produto(s) encontrado(s) para '{query}':*\n\n"
        for p in results[:5]:
            # Avalia nível de estoque
            status = self.stock_monitor.scan_product(p["id"])
            level_icon = {"critical": "🔴", "low": "🟡", "medium": "🟠", "normal": "🟢"}.get(
                status.level.value if status else "normal", "⚪"
            )
            text += (
                f"*{p['name']}*\n"
                f"  SKU: `{p['id']}` | Preço: R$ {p['price']:.2f}\n"
                f"  Estoque: {level_icon} {p['stock']} {p['unit']} | Prazo: {p['lead_time_days']}d\n\n"
            )

        if len(results) > 5:
            text += f"_...e mais {len(results) - 5} produto(s)_\n\n"

        text += "💡 `disponível [SKU] [qtd]` para checar | `adicionar [SKU] [qtd]` para comprar"
        self._add_to_history(user_id, "assistant", text)
        return {"type": "search_result", "text": text, "products": results[:5]}

    def _handle_check_availability_from_message(self, user_id: str, message: str) -> Dict:
        parts = message.split()
        sku = None
        quantity = 1
        for part in parts:
            if part.upper().startswith("SKU"):
                sku = part.upper()
            elif part.isdigit():
                quantity = int(part)
        if not sku and len(parts) >= 2:
            sku = parts[1].upper()
        if not sku:
            return {"type": "error", "text": "❌ Informe o SKU. Ex: `disponível SKU001 500`"}
        return self._handle_check_availability(user_id, sku, quantity)

    def _handle_check_availability(self, user_id: str, sku: str, quantity: int) -> Dict:
        ctx = self._get_user_context(user_id)
        ctx["last_product"] = sku

        # Verifica viabilidade pelo monitor de estoque (com regras)
        feasibility = self.stock_monitor.check_quantity_feasibility(sku, quantity)

        if not feasibility["feasible"]:
            # Sugere alternativas via IA
            alt_text = self.ai.suggest_alternatives(sku, self.inventory)
            text = f"❌ *{sku}* — {feasibility['reason']}"
            if alt_text:
                text += f"\n\n{alt_text}"
            return {"type": "availability_check", "text": text}

        # Calcula preço com markup de escassez se aplicável
        pricing = self.inventory.calculate_price(sku, quantity)
        markup = feasibility.get("price_markup_percent", 0)
        if markup > 0:
            pricing["unit_price"] *= (1 + markup / 100)
            pricing["total_price"] = pricing["unit_price"] * quantity
            pricing["subtotal"] = pricing["total_price"]

        status = self.stock_monitor.scan_product(sku)
        level_icon = {"critical": "🔴", "low": "🟡", "medium": "🟠", "normal": "🟢"}.get(
            status.level.value if status else "normal", "⚪"
        )

        text = (
            f"✅ *{pricing['product_name']}* (SKU: `{sku}`)\n\n"
            f"📦 Estoque: {level_icon} {feasibility['available']} {pricing['unit']}\n"
            f"📋 Solicitado: {quantity} {pricing['unit']}\n"
            f"💰 Preço unitário: R$ {pricing['unit_price']:.2f}"
        )
        if markup > 0:
            text += f" _(+{markup:.0f}% escassez)_"
        text += f"\n💵 *Total: R$ {pricing['total_price']:.2f}*\n"
        if pricing.get("discount_percent", 0) > 0:
            text += f"🎁 Desconto volume: {pricing['discount_percent']}%\n"
        text += f"⏱️ Prazo: {self.inventory.get_product(sku).get('lead_time_days', 3)} dias\n"

        if feasibility.get("show_alert"):
            text += f"\n{feasibility['alert_message']}\n"

        text += f"\n💡 `adicionar {sku} {quantity}` para adicionar ao carrinho"
        self._add_to_history(user_id, "assistant", text)
        return {"type": "availability_check", "text": text, "pricing": pricing}

    def _handle_add_to_cart(self, user_id: str, message: str) -> Dict:
        parts = message.split()
        if len(parts) < 2:
            return {"type": "error", "text": "❌ Use: `adicionar [SKU] [quantidade]`\nEx: `adicionar SKU001 100`"}

        sku = parts[1].upper()
        quantity = 1
        for part in parts[2:]:
            if part.isdigit():
                quantity = int(part)
                break

        feasibility = self.stock_monitor.check_quantity_feasibility(sku, quantity)
        if not feasibility["feasible"]:
            return {"type": "error", "text": f"❌ {feasibility['reason']}"}

        pricing = self.inventory.calculate_price(sku, quantity)
        ctx = self._get_user_context(user_id)
        self.negotiation.add_item_to_negotiation(ctx["session_id"], pricing)

        text = (
            f"✅ *{pricing['product_name']}* adicionado!\n\n"
            f"📦 {quantity} {pricing['unit']} — R$ {pricing['total_price']:.2f}\n\n"
            f"💡 `/carrinho` para ver | `/proposta` para negociar"
        )
        self._add_to_history(user_id, "assistant", text)
        return {"type": "add_to_cart", "text": text}

    def _handle_show_cart(self, user_id: str) -> Dict:
        ctx = self._get_user_context(user_id)
        session = self.negotiation.user_sessions.get(ctx["session_id"], {})
        items = session.get("items", [])

        if not items:
            return {"type": "cart", "text": "🛒 Carrinho vazio.\n\n💡 `buscar [produto]` para encontrar itens."}

        text = f"🛒 *Carrinho ({len(items)} item(ns)):*\n\n"
        total = 0
        for i, item in enumerate(items, 1):
            text += f"{i}. *{item['product_name']}* (`{item['sku']}`)\n"
            text += f"   {item['quantity']} {item['unit']} — R$ {item['total_price']:.2f}\n\n"
            total += item["total_price"]

        text += f"💵 *Total: R$ {total:.2f}*\n\n"
        text += "💡 `/proposta` para gerar proposta | `/limpar` para limpar"
        return {"type": "cart", "text": text}

    def _handle_generate_proposal(self, user_id: str) -> Dict:
        ctx = self._get_user_context(user_id)
        proposal = self.negotiation.generate_proposal(ctx["session_id"], self.inventory)

        if not proposal:
            return {"type": "error", "text": "❌ Carrinho vazio. Adicione itens antes de gerar proposta."}

        ctx["last_proposal_id"] = proposal["proposal_id"]
        ctx["counter_round"] = 0

        # Aplica condições de pagamento das regras
        order_ctx = self._get_order_context(user_id)
        neg_ctx = self.rules.evaluate_negotiation(order_ctx["total"], 0, 0)
        payment_terms = ", ".join(neg_ctx.payment_terms)

        text = (
            f"📋 *Proposta #{proposal['proposal_id']}*\n"
            f"Data: {proposal['created_at'][:10]}\n\n"
            f"📦 *Itens:*\n"
        )
        for item in proposal["items"]:
            text += f"• {item['product_name']} (`{item['sku']}`)\n"
            text += f"  {item['quantity']} {item['unit']} × R$ {item['unit_price']:.2f}\n"

        text += (
            f"\n💰 *Valores:*\n"
            f"Subtotal: R$ {proposal['subtotal']:.2f}\n"
        )
        if proposal.get("additional_discount_percent", 0) > 0:
            text += f"Desconto: {proposal['additional_discount_percent']}% (-R$ {proposal['additional_discount_amount']:.2f})\n"

        text += (
            f"*Total: R$ {proposal['final_total']:.2f}*\n\n"
            f"📅 *Condições:*\n"
            f"Entrega: {proposal['delivery_date']}\n"
            f"Pagamento: {payment_terms}\n"
            f"Validade: {proposal['validity_days']} dias\n\n"
            f"Responda:\n"
            f"• `aceitar {proposal['proposal_id']}` — Confirmar\n"
            f"• `desconto [%]` — Solicitar desconto\n"
            f"• `rejeitar {proposal['proposal_id']}` — Recusar"
        )
        self._add_to_history(user_id, "assistant", text)
        return {"type": "proposal", "text": text, "proposal": proposal}

    def _handle_accept_proposal(self, user_id: str, message: str) -> Dict:
        ctx = self._get_user_context(user_id)
        order_ctx = self._get_order_context(user_id)
        text = (
            f"✅ *Proposta aceita!*\n\n"
            f"Pedido confirmado — R$ {order_ctx['final_total']:.2f}\n"
            f"Nossa equipe entrará em contato para finalizar.\n\n"
            f"Obrigado pela preferência! 🎉"
        )
        # Limpa carrinho após aceite
        self.negotiation.clear_session(ctx["session_id"])
        ctx["session_id"] = self.negotiation.create_session(user_id)
        ctx["counter_round"] = 0
        self._add_to_history(user_id, "assistant", text)
        return {"type": "accepted", "text": text}

    def _handle_reject_proposal(self, user_id: str, message: str) -> Dict:
        text = (
            "❌ *Proposta recusada.*\n\n"
            "Entendemos. Se mudar de ideia ou quiser renegociar, estamos à disposição.\n\n"
            "💡 `buscar [produto]` para recomeçar"
        )
        self._add_to_history(user_id, "assistant", text)
        return {"type": "rejected", "text": text}

    def _handle_negotiation(self, user_id: str, message: str) -> Dict:
        """Processa pedido de desconto usando IA + regras."""
        ctx = self._get_user_context(user_id)

        # Extrai percentual ou valor solicitado
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*%?", message)
        requested_discount = 0.0
        if match:
            try:
                requested_discount = float(match.group(1).replace(",", "."))
                # Se for valor absoluto grande, converte para %
                if requested_discount > 100:
                    order_ctx = self._get_order_context(user_id)
                    total = order_ctx.get("total", 1)
                    requested_discount = (requested_discount / total) * 100
            except Exception:
                pass

        order_ctx = self._get_order_context(user_id, requested_discount)

        if not order_ctx["items"]:
            return {"type": "error", "text": "❌ Adicione itens ao carrinho antes de negociar."}

        # Contexto de estoque dos itens do carrinho
        stock_lines = []
        for item in order_ctx["items"]:
            sc = self.stock_monitor.format_product_stock_context(item["sku"])
            stock_lines.append(sc)
        stock_context = "\n".join(stock_lines)

        # Avalia desconto pelas regras
        first_item = order_ctx["items"][0]
        sku = first_item.get("sku", "")
        product = self.inventory.get_product(sku) or {"category": "Geral", "id": sku}
        disc_decision = self.rules.calculate_allowed_discount(
            product,
            first_item.get("quantity", 1),
            order_ctx["total"],
            requested_discount,
        )

        # Chama IA para gerar resposta de negociação
        ai_response = self.ai.negotiate(
            user_message=message,
            conversation_history=ctx["history"],
            order_context=order_ctx,
            stock_context=stock_context,
            counter_round=ctx["counter_round"],
        )

        ctx["counter_round"] += 1

        # Adiciona info de escalação se necessário
        response_text = ai_response["text"]
        if ai_response.get("escalation_required") and "escalação" not in response_text.lower():
            contact = self.rules.get_escalation_contact()
            response_text += (
                f"\n\n📞 *Contato:* {contact.get('name','Equipe Comercial')} — "
                f"{contact.get('whatsapp','')}"
            )

        # Rodapé de transparência da IA
        decision = ai_response.get("decision", "?")
        decision_icons = {
            "accept": "✅ ACEITAR",
            "counter": "🔄 CONTRA-PROPOSTA",
            "reject": "❌ REJEITAR",
            "escalate": "📈 ESCALAR",
            "hold": "⏸️ AGUARDAR",
        }
        decision_label = decision_icons.get(decision, f"❓ {decision.upper()}")
        model_name = ai_response.get("model", self.ai.model)
        elapsed = ai_response.get("elapsed_ms", 0)
        max_disc = ai_response.get("max_discount", 0)
        style = self.rules.get_negotiation_style()

        transparency_footer = (
            f"\n\n────────────────────"
            f"\n🤖 *Decisão da IA:* {decision_label}"
            f"\n📊 *Desconto máx. permitido:* {max_disc:.0f}%"
            f"\n📝 *Desconto solicitado:* {requested_discount:.0f}%"
            f"\n🎯 *Estilo de negociação:* {style}"
            f"\n⚡ *Modelo:* `{model_name}` ({elapsed}ms)"
            f"\n🔍 `/debug` para ver raciocínio completo"
        )
        full_response = response_text + transparency_footer

        self._add_to_history(user_id, "assistant", response_text)
        return {
            "type": "negotiation",
            "text": full_response,
            "decision": decision,
            "max_discount": disc_decision.allowed_percent,
            "trace": ai_response.get("trace", {}),
        }

    def _handle_stock_alerts(self) -> Dict:
        """Mostra alertas de estoque crítico e baixo."""
        alerts = self.stock_monitor.get_low_products()
        text = self.stock_monitor.format_alert_message(alerts)
        return {"type": "stock_alerts", "text": text}

    def _handle_debug(self, user_id: str) -> Dict:
        """Mostra o raciocínio completo da última decisão da IA."""
        trace = self.ai.last_decision_trace

        if not trace:
            return {
                "type": "debug",
                "text": (
                    "🔍 *Nenhuma decisão registrada ainda.*\n\n"
                    "Faça uma negociação primeiro (ex: `desconto 15%`) e depois use `/debug`."
                )
            }

        decision_icons = {
            "accept": "✅ ACEITAR",
            "counter": "🔄 CONTRA-PROPOSTA",
            "reject": "❌ REJEITAR",
            "escalate": "📈 ESCALAR",
            "hold": "⏸️ AGUARDAR",
        }
        decision_label = decision_icons.get(trace.get("decision", ""), trace.get("decision", "?").upper())
        rules = trace.get("rules_applied", {})

        text = (
            f"🔍 *Raciocínio da última decisão da IA*\n"
            f"────────────────────\n\n"
            f"💬 *Mensagem do cliente:*\n`{trace.get('user_message', '?')}`\n\n"
            f"📊 *Contexto do pedido:*\n"
            f"  Total: R$ {trace.get('order_total', 0):.2f}\n"
            f"  Desconto solicitado: {trace.get('requested_discount_percent', 0):.0f}%\n"
            f"  Rodada de negociação: {trace.get('counter_round', 0) + 1}\n\n"
            f"⚙️ *Regras aplicadas:*\n"
            f"  Estilo: `{rules.get('negotiation_style', '?')}`\n"
            f"  Desconto máx. autônomo: `{rules.get('max_autonomous_discount', '?')}%`\n"
            f"  Limite de escalação: `{rules.get('escalation_threshold', '?')}%`\n"
            f"  Rodadas máximas: `{rules.get('max_rounds', '?')}`\n\n"
            f"🤖 *Decisão da IA:* {decision_label}\n"
            f"  Desconto máx. permitido: `{trace.get('max_discount_allowed', 0):.0f}%`\n"
            f"  Pode ceder mais: `{'Sim' if trace.get('can_concede') else 'Não'}`\n"
            f"  Escalação: `{'Sim' if trace.get('escalation_required') else 'Não'}`\n\n"
            f"📝 *Resposta bruta da IA:*\n`{trace.get('raw_ai_response', '?')[:200]}`\n\n"
            f"⚡ *Performance:*\n"
            f"  Modelo: `{trace.get('model', '?')}`\n"
            f"  Tempo de resposta: `{trace.get('elapsed_ms', 0)}ms`\n"
            f"  Timestamp: `{trace.get('timestamp', '?')[:19]}`"
        )
        return {"type": "debug", "text": text}

    def _handle_clear_cart(self, user_id: str) -> Dict:
        ctx = self._get_user_context(user_id)
        self.negotiation.clear_session(ctx["session_id"])
        ctx["session_id"] = self.negotiation.create_session(user_id)
        ctx["counter_round"] = 0
        return {"type": "cart_cleared", "text": "🗑️ Carrinho limpo!\n\n💡 `buscar [produto]` para recomeçar."}

    def _handle_show_categories(self) -> Dict:
        categories = self.inventory.get_all_categories()
        text = "📂 *Categorias disponíveis:*\n\n"
        for cat in categories:
            products = self.inventory.get_products_by_category(cat)
            text += f"• *{cat}* ({len(products)} produto(s))\n"
        text += "\n💡 `buscar [categoria]` para ver produtos"
        return {"type": "categories", "text": text}

    # ------------------------------------------------------------------
    # HANDLERS NLU — Usam entidades extraídas pelo NLU
    # ------------------------------------------------------------------

    def _handle_check_availability_nlu(self, user_id: str, nlu) -> Dict:
        """Verifica disponibilidade usando entidades do NLU."""
        sku = nlu.sku
        quantity = nlu.quantity or 1

        # Se não tem SKU mas tem nome, busca primeiro
        if not sku and nlu.product_name:
            results = self.inventory.search_product(nlu.product_name)
            if results:
                sku = results[0]["id"]
            else:
                return self._handle_search(user_id, nlu.product_name)

        if not sku:
            return {
                "type": "error",
                "text": "❓ Qual produto você quer verificar? Me diga o nome ou SKU."
            }
        return self._handle_check_availability(user_id, sku.upper(), quantity)

    def _handle_add_to_cart_nlu(self, user_id: str, nlu) -> Dict:
        """Adiciona ao carrinho usando entidades do NLU."""
        sku = nlu.sku
        quantity = nlu.quantity or 1

        # Se não tem SKU mas tem nome, busca
        if not sku and nlu.product_name:
            results = self.inventory.search_product(nlu.product_name)
            if results:
                sku = results[0]["id"]
                if not nlu.quantity:
                    # Pergunta quantidade se não foi mencionada
                    ctx = self._get_user_context(user_id)
                    ctx["pending_sku"] = sku
                    ctx["state"] = "waiting_quantity"
                    product = results[0]
                    return {
                        "type": "ask_quantity",
                        "text": (
                            f"📦 Encontrei *{product['name']}* (SKU: `{sku}`)\n"
                            f"Preço: R$ {product['price']:.2f}/{product['unit']}\n\n"
                            f"Quantas unidades você precisa?"
                        )
                    }
            else:
                return self._handle_search(user_id, nlu.product_name)

        if not sku:
            return {
                "type": "error",
                "text": "❓ Qual produto você quer adicionar? Me diga o nome ou SKU."
            }

        # Verifica se estava aguardando quantidade
        ctx = self._get_user_context(user_id)
        if ctx.get("state") == "waiting_quantity" and nlu.quantity:
            sku = ctx.get("pending_sku", sku)
            ctx["state"] = "idle"

        return self._handle_add_to_cart(user_id, f"adicionar {sku.upper()} {quantity}")

    def _handle_negotiation_nlu(self, user_id: str, message: str, nlu) -> Dict:
        """Negocia usando entidades extraídas pelo NLU."""
        # Se NLU extraiu percentual, injeta na mensagem para o handler de negociação
        if nlu.discount_percent and nlu.discount_percent > 0:
            # Usa mensagem original mas garante que o handler vai encontrar o desconto
            return self._handle_negotiation(user_id, message)
        return self._handle_negotiation(user_id, message)

    def _handle_delivery_info(self, user_id: str, nlu) -> Dict:
        """Responde sobre prazo de entrega."""
        sku = nlu.sku
        product = None

        if sku:
            product = self.inventory.get_product(sku.upper())
        elif nlu.product_name:
            results = self.inventory.search_product(nlu.product_name)
            if results:
                product = results[0]

        if product:
            lead = product.get("lead_time_days", 3)
            text = (
                f"⏱️ *Prazo de entrega — {product['name']}*\n\n"
                f"📦 Prazo padrão: *{lead} dias úteis*\n"
                f"🚚 A partir da confirmação do pedido\n\n"
                f"💡 Prazos podem variar conforme volume e localidade."
            )
        else:
            text = (
                "⏱️ *Prazos de entrega padrão:*\n\n"
                "• Até 100 unidades: *3 dias úteis*\n"
                "• 100–500 unidades: *5 dias úteis*\n"
                "• Acima de 500: *7 dias úteis*\n\n"
                "💡 Me diga o produto para um prazo exato."
            )
        self._add_to_history(user_id, "assistant", text)
        return {"type": "delivery_info", "text": text}

    def _handle_payment_info(self, user_id: str, nlu) -> Dict:
        """Responde sobre condições de pagamento."""
        rules = self.rules.rules.get("payment_conditions", {})
        tiers = rules.get("tiers", [])

        ctx = self._get_user_context(user_id)
        session = self.negotiation.user_sessions.get(ctx["session_id"], {})
        total = sum(i.get("total_price", 0) for i in session.get("items", []))

        text = "💳 *Condições de pagamento disponíveis:*\n\n"

        if tiers and total > 0:
            # Mostra condição específica para o valor do pedido
            for tier in tiers:
                if tier.get("min_value", 0) <= total <= tier.get("max_value", float("inf")):
                    terms = tier.get("payment_terms", [])
                    text += f"Para seu pedido de *R$ {total:.2f}*:\n"
                    for t in terms:
                        text += f"  ✅ {t}\n"
                    break
        else:
            text += (
                "• Pedidos até R$ 1.000: À vista ou 30 dias\n"
                "• R$ 1.000 – R$ 5.000: 30/60 dias\n"
                "• Acima de R$ 5.000: 30/60/90 dias\n"
                "• Acima de R$ 10.000: 30/60/90/120 dias\n"
            )

        text += "\n💡 `/proposta` para ver condições do seu pedido atual."
        self._add_to_history(user_id, "assistant", text)
        return {"type": "payment_info", "text": text}

    def _handle_ai_fallback(self, user_id: str, user_name: str, message: str) -> Dict:
        """Usa IA para responder mensagens não reconhecidas pelos comandos fixos."""
        ctx = self._get_user_context(user_id)
        order_ctx = self._get_order_context(user_id)

        # Análise de intenção
        intent_data = self.ai.analyze_intent(message, ctx["history"])
        intent = intent_data.get("intent", "outro")

        # Redireciona para handlers específicos se a intenção for clara
        if intent == "buscar_produto":
            return self._handle_search(user_id, message)
        if intent == "ver_carrinho":
            return self._handle_show_cart(user_id)
        if intent == "gerar_proposta":
            return self._handle_generate_proposal(user_id)
        if intent == "aceitar_proposta":
            return self._handle_accept_proposal(user_id, message)
        if intent == "rejeitar_proposta":
            return self._handle_reject_proposal(user_id, message)
        if intent in ("negociar_preco", "contra_proposta"):
            return self._handle_negotiation(user_id, message)

        # Resposta livre da IA com contexto do pedido
        stock_context = ""
        if order_ctx["items"]:
            lines = [self.stock_monitor.format_product_stock_context(i["sku"]) for i in order_ctx["items"]]
            stock_context = "\n".join(lines)

        ai_response = self.ai.negotiate(
            user_message=message,
            conversation_history=ctx["history"],
            order_context=order_ctx,
            stock_context=stock_context,
            counter_round=ctx["counter_round"],
        )

        text = ai_response["text"]
        if not text:
            text = (
                "Não entendi sua solicitação. 😅\n\n"
                "Digite `/help` para ver os comandos disponíveis."
            )

        self._add_to_history(user_id, "assistant", text)
        return {"type": "ai_response", "text": text}
