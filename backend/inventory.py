import json
from pathlib import Path
from typing import Optional, Dict, List

# Caminho relativo ao arquivo atual — funciona tanto local quanto no Docker
_BASE_DIR = Path(__file__).resolve().parent.parent

class InventoryManager:
    def __init__(self, data_file: str = None):
        if data_file is None:
            data_file = str(_BASE_DIR / "data" / "products.json")
        self.data_file = data_file
        self.data = self._load_data()
        self.products = {p["id"]: p for p in self.data["products"]}
        self.discount_tiers = self.data["discount_tiers"]

    def _load_data(self) -> dict:
        with open(self.data_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def search_product(self, query: str) -> List[Dict]:
        """Busca produtos por nome ou SKU"""
        query_lower = query.lower()
        results = []
        
        for product in self.data["products"]:
            if (query_lower in product["id"].lower() or 
                query_lower in product["name"].lower() or
                query_lower in product["category"].lower()):
                results.append(product)
        
        return results

    def get_product(self, sku: str) -> Optional[Dict]:
        """Obtém um produto específico pelo SKU"""
        return self.products.get(sku)

    def check_availability(self, sku: str, quantity: int) -> Dict:
        """Verifica disponibilidade de um produto"""
        product = self.get_product(sku)
        
        if not product:
            return {
                "available": False,
                "reason": "Produto não encontrado",
                "sku": sku
            }
        
        if product["stock"] < quantity:
            return {
                "available": False,
                "reason": f"Quantidade insuficiente. Disponível: {product['stock']} {product['unit']}",
                "sku": sku,
                "requested": quantity,
                "available_stock": product["stock"]
            }
        
        return {
            "available": True,
            "sku": sku,
            "product_name": product["name"],
            "requested": quantity,
            "available_stock": product["stock"],
            "lead_time_days": product["lead_time_days"]
        }

    def calculate_price(self, sku: str, quantity: int) -> Optional[Dict]:
        """Calcula preço com desconto baseado na quantidade"""
        product = self.get_product(sku)
        
        if not product:
            return None
        
        unit_price = product["price"]
        discount_percent = 0
        
        # Encontra o desconto apropriado
        for tier in self.discount_tiers:
            if tier["min_quantity"] <= quantity:
                if tier["max_quantity"] is None or quantity <= tier["max_quantity"]:
                    discount_percent = tier["discount_percent"]
                    break
        
        discount_amount = (unit_price * quantity * discount_percent) / 100
        total_price = (unit_price * quantity) - discount_amount
        
        return {
            "sku": sku,
            "product_name": product["name"],
            "quantity": quantity,
            "unit": product["unit"],
            "unit_price": unit_price,
            "subtotal": unit_price * quantity,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "total_price": total_price,
            "price_per_unit_with_discount": total_price / quantity if quantity > 0 else 0
        }

    def get_all_categories(self) -> List[str]:
        """Retorna todas as categorias de produtos"""
        categories = set()
        for product in self.data["products"]:
            categories.add(product["category"])
        return sorted(list(categories))

    def get_products_by_category(self, category: str) -> List[Dict]:
        """Retorna produtos de uma categoria específica"""
        return [p for p in self.data["products"] if p["category"].lower() == category.lower()]

    def get_low_stock_products(self, threshold: int = 50) -> List[Dict]:
        """Retorna produtos com estoque baixo"""
        return [p for p in self.data["products"] if p["stock"] < threshold]
