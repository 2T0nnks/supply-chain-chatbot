from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid

class NegotiationManager:
    def __init__(self):
        self.negotiations = {}  # Armazena negociações por ID
        self.user_sessions = {}  # Armazena sessões de usuário

    def create_session(self, user_id: str, user_name: str = "Cliente") -> str:
        """Cria uma nova sessão de negociação"""
        session_id = str(uuid.uuid4())
        self.user_sessions[session_id] = {
            "user_id": user_id,
            "user_name": user_name,
            "created_at": datetime.now().isoformat(),
            "items": [],
            "total_value": 0
        }
        return session_id

    def add_item_to_negotiation(self, session_id: str, item: Dict) -> Dict:
        """Adiciona um item à negociação"""
        if session_id not in self.user_sessions:
            return {"success": False, "error": "Sessão não encontrada"}
        
        session = self.user_sessions[session_id]
        session["items"].append(item)
        session["total_value"] += item.get("total_price", 0)
        
        return {
            "success": True,
            "items_count": len(session["items"]),
            "total_value": session["total_value"]
        }

    def generate_proposal(self, session_id: str, inventory_manager) -> Optional[Dict]:
        """Gera uma proposta de negociação com base nos itens"""
        if session_id not in self.user_sessions:
            return None
        
        session = self.user_sessions[session_id]
        
        if not session["items"]:
            return None
        
        proposal_id = str(uuid.uuid4())[:8].upper()
        
        # Calcula prazos e condições
        max_lead_time = max([item.get("lead_time_days", 0) for item in session["items"]])
        delivery_date = (datetime.now() + timedelta(days=max_lead_time)).strftime("%d/%m/%Y")
        
        # Oferece condições especiais baseado no valor total
        total_value = session["total_value"]
        payment_terms = self._get_payment_terms(total_value)
        additional_discount = self._get_volume_discount(total_value)
        
        proposal = {
            "proposal_id": proposal_id,
            "created_at": datetime.now().isoformat(),
            "client_name": session["user_name"],
            "items": session["items"],
            "subtotal": total_value,
            "additional_discount_percent": additional_discount,
            "additional_discount_amount": (total_value * additional_discount) / 100,
            "final_total": total_value - ((total_value * additional_discount) / 100),
            "delivery_date": delivery_date,
            "payment_terms": payment_terms,
            "validity_days": 7,
            "notes": self._generate_proposal_notes(total_value, len(session["items"]))
        }
        
        self.negotiations[proposal_id] = proposal
        return proposal

    def _get_payment_terms(self, total_value: float) -> str:
        """Define condições de pagamento baseado no valor"""
        if total_value > 10000:
            return "30/60/90 dias"
        elif total_value > 5000:
            return "15/30 dias"
        else:
            return "À vista ou 15 dias"

    def _get_volume_discount(self, total_value: float) -> float:
        """Oferece desconto adicional baseado no valor total"""
        if total_value > 20000:
            return 5
        elif total_value > 10000:
            return 3
        elif total_value > 5000:
            return 2
        else:
            return 0

    def _generate_proposal_notes(self, total_value: float, items_count: int) -> str:
        """Gera notas personalizadas para a proposta"""
        notes = f"Proposta para {items_count} item(ns) no valor total de R$ {total_value:,.2f}. "
        
        if total_value > 10000:
            notes += "Condições especiais para grande volume. "
        
        notes += "Validade: 7 dias. Sujeito a confirmação de estoque."
        
        return notes

    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        """Recupera uma proposta específica"""
        return self.negotiations.get(proposal_id)

    def accept_proposal(self, proposal_id: str) -> Dict:
        """Marca uma proposta como aceita"""
        proposal = self.get_proposal(proposal_id)
        
        if not proposal:
            return {"success": False, "error": "Proposta não encontrada"}
        
        proposal["status"] = "accepted"
        proposal["accepted_at"] = datetime.now().isoformat()
        
        order_id = str(uuid.uuid4())[:8].upper()
        
        return {
            "success": True,
            "order_id": order_id,
            "proposal_id": proposal_id,
            "message": f"Proposta aceita! Seu pedido #{order_id} foi criado com sucesso.",
            "delivery_date": proposal["delivery_date"]
        }

    def reject_proposal(self, proposal_id: str, reason: str = "") -> Dict:
        """Marca uma proposta como rejeitada"""
        proposal = self.get_proposal(proposal_id)
        
        if not proposal:
            return {"success": False, "error": "Proposta não encontrada"}
        
        proposal["status"] = "rejected"
        proposal["rejected_at"] = datetime.now().isoformat()
        proposal["rejection_reason"] = reason
        
        return {
            "success": True,
            "message": "Proposta rejeitada. Estamos à disposição para novas negociações."
        }

    def counter_offer(self, proposal_id: str, counter_value: float) -> Dict:
        """Registra uma contra-proposta"""
        proposal = self.get_proposal(proposal_id)
        
        if not proposal:
            return {"success": False, "error": "Proposta não encontrada"}
        
        original_value = proposal["final_total"]
        discount_percent = ((original_value - counter_value) / original_value) * 100
        
        return {
            "success": True,
            "message": f"Contra-proposta recebida: R$ {counter_value:,.2f}",
            "discount_percent": discount_percent,
            "original_value": original_value,
            "counter_value": counter_value,
            "note": "Sua contra-proposta foi registrada. Analisaremos e retornaremos em breve."
        }

    def clear_session(self, session_id: str) -> Dict:
        """Limpa uma sessão de negociação"""
        if session_id in self.user_sessions:
            del self.user_sessions[session_id]
            return {"success": True, "message": "Sessão limpa."}
        
        return {"success": False, "error": "Sessão não encontrada"}
