"""
Monitor de Estoque
Verifica continuamente os níveis de estoque e dispara alertas
conforme as regras definidas no YAML.
"""
import logging
from typing import List, Dict, Optional
from backend.rules_engine import RulesEngine, StockLevel, StockStatus

logger = logging.getLogger(__name__)


class StockMonitor:
    def __init__(self, inventory_manager, rules_engine: RulesEngine):
        self.inventory = inventory_manager
        self.rules = rules_engine
        self._last_alerts: Dict[str, StockLevel] = {}

    def scan_all(self) -> List[StockStatus]:
        """Escaneia todos os produtos e retorna os que têm alertas."""
        products = self.inventory.data["products"]
        return self.rules.get_all_stock_alerts(products)

    def scan_product(self, sku: str) -> Optional[StockStatus]:
        """Escaneia um produto específico."""
        product = self.inventory.get_product(sku)
        if not product:
            return None
        return self.rules.evaluate_stock(product)

    def get_critical_products(self) -> List[StockStatus]:
        """Retorna apenas produtos em nível crítico."""
        return [s for s in self.scan_all() if s.level == StockLevel.CRITICAL]

    def get_low_products(self) -> List[StockStatus]:
        """Retorna produtos em nível baixo ou crítico."""
        return [s for s in self.scan_all() if s.level in (StockLevel.CRITICAL, StockLevel.LOW)]

    def format_alert_message(self, alerts: List[StockStatus]) -> str:
        """Formata mensagem de alerta para o usuário."""
        if not alerts:
            return "✅ Todos os produtos estão com estoque adequado."

        critical = [a for a in alerts if a.level == StockLevel.CRITICAL]
        low = [a for a in alerts if a.level == StockLevel.LOW]

        lines = ["📊 *Relatório de Estoque*\n"]

        if critical:
            lines.append("🔴 *CRÍTICO — Ação Imediata Necessária:*")
            for s in critical:
                priority_tag = " ⭐" if s.is_priority else ""
                lines.append(
                    f"  • {s.name} (SKU: `{s.sku}`){priority_tag}\n"
                    f"    Estoque: {s.current_stock} {s.unit} ({s.percent_remaining:.0f}%)\n"
                    f"    Máx. vendável: {s.max_sellable_qty} {s.unit}"
                )
                if s.show_alert:
                    lines.append(f"    {s.alert_message}")

        if low:
            lines.append("\n🟡 *BAIXO — Atenção:*")
            for s in low:
                priority_tag = " ⭐" if s.is_priority else ""
                lines.append(
                    f"  • {s.name} (SKU: `{s.sku}`){priority_tag}\n"
                    f"    Estoque: {s.current_stock} {s.unit} ({s.percent_remaining:.0f}%)"
                )

        return "\n".join(lines)

    def format_product_stock_context(self, sku: str) -> str:
        """Formata contexto de estoque de um produto para a IA."""
        status = self.scan_product(sku)
        if not status:
            return f"Produto {sku} não encontrado."

        product = self.inventory.get_product(sku)
        level_labels = {
            StockLevel.CRITICAL: "CRÍTICO",
            StockLevel.LOW: "BAIXO",
            StockLevel.MEDIUM: "MÉDIO",
            StockLevel.NORMAL: "NORMAL",
        }
        label = level_labels.get(status.level, "DESCONHECIDO")

        context = (
            f"Produto: {status.name} (SKU: {status.sku})\n"
            f"Estoque atual: {status.current_stock} {status.unit} ({status.percent_remaining:.0f}% do máximo)\n"
            f"Nível: {label}\n"
            f"Máximo vendável nesta negociação: {status.max_sellable_qty} {status.unit}\n"
        )

        if status.price_markup_percent > 0:
            context += f"Markup de escassez aplicado: +{status.price_markup_percent:.0f}%\n"

        if status.show_alert:
            context += f"Alerta: {status.alert_message}\n"

        return context

    def check_quantity_feasibility(self, sku: str, requested_qty: int) -> Dict:
        """Verifica se uma quantidade solicitada é viável dado o estoque."""
        status = self.scan_product(sku)
        if not status:
            return {"feasible": False, "reason": "Produto não encontrado."}

        if requested_qty > status.current_stock:
            return {
                "feasible": False,
                "reason": f"Estoque insuficiente. Disponível: {status.current_stock} {status.unit}.",
                "available": status.current_stock,
            }

        if requested_qty > status.max_sellable_qty:
            return {
                "feasible": False,
                "reason": (
                    f"Quantidade acima do limite de venda para estoque {status.level.value}. "
                    f"Máximo permitido: {status.max_sellable_qty} {status.unit}."
                ),
                "available": status.max_sellable_qty,
            }

        return {
            "feasible": True,
            "stock_level": status.level.value,
            "available": status.current_stock,
            "max_sellable": status.max_sellable_qty,
            "show_alert": status.show_alert,
            "alert_message": status.alert_message,
            "price_markup_percent": status.price_markup_percent,
        }
