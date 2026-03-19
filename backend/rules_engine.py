"""
Motor de Regras de Negócio
Lê e aplica as regras definidas no arquivo YAML de configuração.
"""
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Caminho relativo ao arquivo atual — funciona tanto local quanto no Docker
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "business_rules.yaml"


class StockLevel(Enum):
    CRITICAL = "critical"
    LOW = "low"
    MEDIUM = "medium"
    NORMAL = "normal"


class NegotiationDecision(Enum):
    ACCEPT = "accept"
    COUNTER_OFFER = "counter_offer"
    REJECT = "reject"
    ESCALATE = "escalate"


@dataclass
class StockStatus:
    sku: str
    name: str
    current_stock: int
    unit: str
    level: StockLevel
    percent_remaining: float
    max_sellable_qty: int
    price_markup_percent: float
    show_alert: bool
    alert_message: str
    is_priority: bool


@dataclass
class DiscountDecision:
    allowed_percent: float
    reason: str
    requires_escalation: bool
    escalation_reason: str


@dataclass
class NegotiationContext:
    decision: NegotiationDecision
    max_discount: float
    current_round: int
    max_rounds: int
    can_concede: bool
    concession_available: float
    payment_terms: List[str]
    closing_message: str
    escalation_required: bool
    escalation_message: str


class RulesEngine:
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self.rules = self._load_rules()
        logger.info("✅ Motor de regras carregado com sucesso.")

    def _load_rules(self) -> dict:
        """Carrega as regras do arquivo YAML."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                rules = yaml.safe_load(f)
            logger.info(f"📋 Regras carregadas de: {self.config_path}")
            return rules
        except FileNotFoundError:
            logger.error(f"❌ Arquivo de regras não encontrado: {self.config_path}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"❌ Erro ao parsear YAML: {e}")
            return {}

    def reload(self):
        """Recarrega as regras do arquivo (hot reload)."""
        self.rules = self._load_rules()
        logger.info("🔄 Regras recarregadas.")

    # ------------------------------------------------------------------
    # AVALIAÇÃO DE ESTOQUE
    # ------------------------------------------------------------------

    def evaluate_stock(self, product: dict) -> StockStatus:
        """Avalia o nível de estoque de um produto e retorna status completo."""
        stock_rules = self.rules.get("stock", {})
        thresholds = stock_rules.get("thresholds", {"critical": 10, "low": 25, "medium": 50})
        max_refs = stock_rules.get("max_stock_reference", {})
        priority_skus = self.rules.get("alerts", {}).get("priority_skus", [])

        sku = product["id"]
        category = product.get("category", "")
        current_stock = product["stock"]
        unit = product.get("unit", "unidade")
        name = product.get("name", sku)

        # Calcula % restante em relação ao máximo de referência
        max_ref = max_refs.get(category, current_stock * 2)
        percent_remaining = (current_stock / max_ref * 100) if max_ref > 0 else 100.0

        # Classifica o nível
        if percent_remaining <= thresholds["critical"]:
            level = StockLevel.CRITICAL
            behavior_key = "critical_stock_behavior"
        elif percent_remaining <= thresholds["low"]:
            level = StockLevel.LOW
            behavior_key = "low_stock_behavior"
        elif percent_remaining <= thresholds["medium"]:
            level = StockLevel.MEDIUM
            behavior_key = None
        else:
            level = StockLevel.NORMAL
            behavior_key = None

        # Obtém comportamento configurado
        behavior = stock_rules.get(behavior_key, {}) if behavior_key else {}
        max_sell_pct = behavior.get("max_sell_percent", 100)
        markup = behavior.get("price_markup_percent", 0)
        show_alert = behavior.get("show_scarcity_alert", False)
        alert_msg = behavior.get("scarcity_message", "")

        max_sellable = int(current_stock * max_sell_pct / 100)

        return StockStatus(
            sku=sku,
            name=name,
            current_stock=current_stock,
            unit=unit,
            level=level,
            percent_remaining=round(percent_remaining, 1),
            max_sellable_qty=max_sellable,
            price_markup_percent=markup,
            show_alert=show_alert,
            alert_message=alert_msg,
            is_priority=sku in priority_skus,
        )

    def get_all_stock_alerts(self, products: List[dict]) -> List[StockStatus]:
        """Retorna lista de produtos com alertas de estoque (crítico ou baixo)."""
        alerts = []
        for product in products:
            status = self.evaluate_stock(product)
            if status.level in (StockLevel.CRITICAL, StockLevel.LOW):
                alerts.append(status)
        # Prioridades primeiro
        alerts.sort(key=lambda s: (not s.is_priority, s.percent_remaining))
        return alerts

    # ------------------------------------------------------------------
    # CÁLCULO DE DESCONTO
    # ------------------------------------------------------------------

    def calculate_allowed_discount(
        self,
        product: dict,
        quantity: int,
        order_total: float,
        requested_discount: float = 0.0,
    ) -> DiscountDecision:
        """Calcula o desconto máximo permitido pelas regras."""
        discount_rules = self.rules.get("discounts", {})
        category = product.get("category", "")

        # Desconto por volume
        volume_discount = 0.0
        for tier in discount_rules.get("volume_tiers", []):
            max_qty = tier.get("max_qty")
            if tier["min_qty"] <= quantity and (max_qty is None or quantity <= max_qty):
                volume_discount = tier["discount_percent"]
                break

        # Desconto adicional por valor do pedido
        order_discount = 0.0
        for tier in discount_rules.get("order_value_tiers", []):
            max_val = tier.get("max_value")
            if tier["min_value"] <= order_total and (max_val is None or order_total <= max_val):
                order_discount = tier["extra_discount_percent"]
                break

        # Limite por categoria
        cat_rules = discount_rules.get("category_rules", {}).get(category, {})
        cat_max = cat_rules.get("max_discount_percent", discount_rules.get("max_autonomous_discount_percent", 15))

        # Limite autônomo global
        global_max = discount_rules.get("max_autonomous_discount_percent", 15)
        absolute_max = discount_rules.get("max_absolute_discount_percent", 25)
        escalation_threshold = discount_rules.get("escalation_threshold_percent", 20)

        # Desconto base calculado
        base_discount = volume_discount + order_discount
        allowed = min(base_discount, cat_max, global_max)

        # Verifica se requer escalação
        requires_escalation = False
        escalation_reason = ""

        if requested_discount > absolute_max:
            requires_escalation = True
            escalation_reason = f"Desconto solicitado ({requested_discount:.1f}%) excede o máximo absoluto ({absolute_max}%)."
            allowed = absolute_max
        elif requested_discount > escalation_threshold:
            requires_escalation = True
            escalation_reason = f"Desconto acima de {escalation_threshold}% requer aprovação."
            allowed = min(requested_discount, absolute_max)
        elif requested_discount > allowed:
            # Pode conceder até o limite autônomo
            allowed = min(requested_discount, global_max, cat_max)

        reason = (
            f"Volume ({quantity} un): {volume_discount:.0f}% + "
            f"Pedido (R$ {order_total:.0f}): {order_discount:.0f}% = "
            f"{allowed:.0f}% permitido"
        )

        return DiscountDecision(
            allowed_percent=round(allowed, 2),
            reason=reason,
            requires_escalation=requires_escalation,
            escalation_reason=escalation_reason,
        )

    # ------------------------------------------------------------------
    # DECISÃO DE NEGOCIAÇÃO
    # ------------------------------------------------------------------

    def evaluate_negotiation(
        self,
        order_total: float,
        requested_discount: float,
        counter_round: int = 0,
    ) -> NegotiationContext:
        """Avalia a situação de negociação e retorna decisão e contexto."""
        neg_rules = self.rules.get("negotiation", {})
        discount_rules = self.rules.get("discounts", {})
        escalation_rules = self.rules.get("escalation", {})
        ai_rules = self.rules.get("ai", {})

        max_rounds = neg_rules.get("max_counter_offer_rounds", 3)
        max_concession = neg_rules.get("max_concession_per_round_percent", 3)
        global_max = discount_rules.get("max_autonomous_discount_percent", 15)
        absolute_max = discount_rules.get("max_absolute_discount_percent", 25)
        escalation_threshold = discount_rules.get("escalation_threshold_percent", 20)
        style = ai_rules.get("negotiation_style", "neutro")

        # Determina condições de pagamento
        payment_options = ["à vista"]
        for tier in neg_rules.get("payment_terms", []):
            max_val = tier.get("max_value")
            if max_val is None or order_total <= max_val:
                payment_options = tier["options"]
                break

        closing_msg = neg_rules.get("closing_messages", {}).get(style, "Podemos prosseguir?")

        # Verifica escalação
        escalation_required = False
        escalation_message = ""
        for trigger in escalation_rules.get("triggers", []):
            if trigger["condition"] == "discount_above_threshold" and requested_discount > escalation_threshold:
                escalation_required = True
                escalation_message = trigger["message"]
                break
            if trigger["condition"] == "order_value_above":
                threshold = trigger.get("threshold", 50000)
                if order_total > threshold:
                    escalation_required = True
                    escalation_message = trigger["message"]
                    break
            if trigger["condition"] == "counter_offers_exceeded" and counter_round >= max_rounds:
                escalation_required = True
                escalation_message = trigger["message"]
                break

        # Decisão principal
        if escalation_required:
            decision = NegotiationDecision.ESCALATE
        elif requested_discount <= global_max:
            decision = NegotiationDecision.ACCEPT
        elif requested_discount <= absolute_max and counter_round < max_rounds:
            decision = NegotiationDecision.COUNTER_OFFER
        elif requested_discount > absolute_max:
            decision = NegotiationDecision.REJECT
        else:
            decision = NegotiationDecision.COUNTER_OFFER

        # Concessão disponível nesta rodada
        concession = min(max_concession, absolute_max - global_max) if counter_round < max_rounds else 0.0

        return NegotiationContext(
            decision=decision,
            max_discount=global_max,
            current_round=counter_round,
            max_rounds=max_rounds,
            can_concede=counter_round < max_rounds and not escalation_required,
            concession_available=concession,
            payment_terms=payment_options,
            closing_message=closing_msg,
            escalation_required=escalation_required,
            escalation_message=escalation_message,
        )

    # ------------------------------------------------------------------
    # HELPERS PARA A IA
    # ------------------------------------------------------------------

    def get_ai_config(self) -> dict:
        """Retorna configurações da IA."""
        return self.rules.get("ai", {})

    def get_negotiation_style(self) -> str:
        return self.rules.get("ai", {}).get("negotiation_style", "neutro")

    def get_persona(self) -> str:
        return self.rules.get("ai", {}).get("persona", "Você é um assistente de vendas.")

    def get_escalation_contact(self) -> dict:
        return self.rules.get("escalation", {}).get("contact", {})

    def format_stock_alert_for_ai(self, status: StockStatus) -> str:
        """Formata alerta de estoque para incluir no contexto da IA."""
        level_emoji = {"critical": "🔴", "low": "🟡", "medium": "🟠", "normal": "🟢"}
        emoji = level_emoji.get(status.level.value, "⚪")
        return (
            f"{emoji} {status.name} (SKU: {status.sku}) — "
            f"Estoque: {status.current_stock} {status.unit} "
            f"({status.percent_remaining:.0f}% restante) — "
            f"Nível: {status.level.value.upper()}"
        )
