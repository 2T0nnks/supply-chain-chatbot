"""
NLU — Natural Language Understanding
Usa Ollama local para interpretar mensagens em linguagem natural,
extraindo intenção e entidades sem precisar de comandos rígidos.
"""
import json
import os
import re
import logging
from typing import Dict, Optional
import requests

logger = logging.getLogger(__name__)

# Suporta Docker Compose (OLLAMA_HOST=http://ollama:11434) e local (http://localhost:11434)
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Intenções reconhecidas pelo sistema
INTENTS = {
    "saudacao":        "Cumprimento ou início de conversa",
    "buscar_produto":  "Cliente quer encontrar/ver produtos disponíveis",
    "ver_estoque":     "Cliente quer saber se tem disponibilidade de um item",
    "adicionar_item":  "Cliente quer colocar item no carrinho / fazer pedido",
    "ver_carrinho":    "Cliente quer ver o que já tem no carrinho",
    "gerar_proposta":  "Cliente quer receber uma proposta formal",
    "negociar":        "Cliente quer negociar preço, desconto ou condições",
    "aceitar":         "Cliente aceita a proposta ou oferta",
    "rejeitar":        "Cliente recusa a proposta ou oferta",
    "prazo_entrega":   "Cliente pergunta sobre prazo de entrega",
    "condicao_pagto":  "Cliente pergunta sobre formas ou condições de pagamento",
    "limpar_carrinho": "Cliente quer cancelar ou limpar o carrinho",
    "ajuda":           "Cliente pede ajuda ou lista de comandos",
    "debug":           "Cliente quer ver o raciocínio da IA",
    "alertas_estoque": "Cliente quer ver alertas de estoque baixo",
    "outro":           "Mensagem não identificada",
}


class NLUResult:
    """Resultado estruturado da análise de linguagem natural."""

    def __init__(self, raw: Dict):
        self.intent: str = raw.get("intent", "outro")
        self.confidence: float = raw.get("confidence", 0.5)
        self.product_name: Optional[str] = raw.get("product_name")
        self.sku: Optional[str] = raw.get("sku")
        self.quantity: Optional[int] = raw.get("quantity")
        self.discount_percent: Optional[float] = raw.get("discount_percent")
        self.payment_condition: Optional[str] = raw.get("payment_condition")
        self.proposal_id: Optional[str] = raw.get("proposal_id")
        self.raw_text: str = raw.get("raw_text", "")
        self.entities: Dict = raw.get("entities", {})

    def __repr__(self):
        return (
            f"NLUResult(intent={self.intent}, confidence={self.confidence:.2f}, "
            f"product={self.product_name}, sku={self.sku}, qty={self.quantity}, "
            f"discount={self.discount_percent}%)"
        )


class NLUEngine:
    """Motor de NLU usando Ollama para compreensão de linguagem natural."""

    def __init__(self, model: str = "qwen2.5:0.5b"):
        self.model = model
        self._quick_rules = self._build_quick_rules()

    # ------------------------------------------------------------------
    # REGRAS RÁPIDAS (sem LLM) para intenções óbvias
    # ------------------------------------------------------------------

    def _build_quick_rules(self):
        """Regras determinísticas para casos simples — evita chamar LLM desnecessariamente."""
        return [
            # Saudações
            (r"^(oi|olá|ola|ei|e aí|eai|bom dia|boa tarde|boa noite|hello|hi|start|/start|hey)[\s!.,]*$",
             "saudacao"),

            # Ajuda (sem "como funciona" genérico para não conflitar com pagamento)
            (r"(^ajuda$|^help$|socorro|comandos|o que (você|vc) (faz|pode)|^menu$|/help|/ajuda)",
             "ajuda"),

            # Carrinho
            (r"(/carrinho|ver carrinho|meu carrinho|o que (tenho|tem) no carrinho|mostra (o )?carrinho)",
             "ver_carrinho"),

            # Proposta / orçamento
            (r"(/proposta|gerar proposta|quero (uma )?proposta|me (manda|envia) (uma )?proposta|orçamento|orcamento|quero orçar)",
             "gerar_proposta"),

            # Debug / raciocínio
            (r"(/debug|debug|como decidiu|racioc[ií]nio|explicar|por que (aceitou|recusou|escalou)|mostra a decisão)",
             "debug"),

            # Alertas de estoque
            (r"(/estoque|alertas?|estoque (baixo|cr[ií]tico)|produtos? (acabando|esgotando))",
             "alertas_estoque"),

            # Limpar carrinho
            (r"(/limpar|limpar (o )?carrinho|cancelar (tudo|pedido)|recomeçar|começar de novo|zerar carrinho)",
             "limpar_carrinho"),

            # Aceitar proposta
            (r"(topei|aceito|aceitar|pode fechar|tá bom|ta bom|fechado|combinado|confirmado|vamos fechar|bora fechar|ok[,!]? (pode|vamos))",
             "aceitar"),

            # Rejeitar proposta
            (r"(não quero|nao quero|recuso|muito caro|desistir|cancelar|não vou|nao vou|tá caro demais|ta caro demais|não tenho interesse)",
             "rejeitar"),

            # Prazo de entrega
            (r"(prazo|entrega|quando (chega|entrega|vem)|demora (quanto|muito)|quantos dias|tempo de entrega)",
             "prazo_entrega"),

            # Condição de pagamento
            (r"(pagamento|pagar|parcel|boleto|pix|cartão|cartao|à vista|a vista|30/60|forma(s)? de pag|como (eu )?pago|aceita (pix|boleto|cartão)|como funciona o pag|como (posso|quero) pagar|como funciona (o )?pag)",
             "condicao_pagto"),

            # Negociar preço (ANTES de adicionar_item para capturar "quero X%")
            (r"(desconto|tá caro|ta caro|muito caro|melhor preço|melhor valor|reduz|abaixa|negocia|contra.proposta|\d+\s*% de desconto)",
             "negociar"),

            # Adicionar item (preciso de, quero comprar, etc.)
            (r"(preciso de \d|quero comprar|quero pedir|quero \d+\s*(un|pc|kg|m|caixa|parafuso|corrente|rolamento|correia|polia|mancal)|comprar \d|pedir \d|separar \d|adicionar \d|add \d)",
             "adicionar_item"),
        ]

    def _quick_match(self, text: str) -> Optional[str]:
        """Tenta identificar intenção via regex sem chamar LLM."""
        text_lower = text.lower().strip()
        for pattern, intent in self._quick_rules:
            if re.search(pattern, text_lower):
                return intent
        return None

    # ------------------------------------------------------------------
    # CHAMADA AO OLLAMA
    # ------------------------------------------------------------------

    def _call_ollama_nlu(self, text: str) -> Dict:
        """Chama Ollama para extrair intenção e entidades em JSON."""

        intents_desc = "\n".join([f'  - "{k}": {v}' for k, v in INTENTS.items()])

        system_prompt = f"""Você é um classificador de intenções para chatbot de supply chain B2B.
Retorne APENAS JSON válido, sem explicações ou markdown.

INTENÇÕES:
{intents_desc}

EXEMPLOS:
- "oi" / "bom dia" / "olá" → saudacao
- "tem parafuso?" / "vocês têm corrente?" / "o que tem no estoque?" → buscar_produto
- "tem 500 unidades de SKU001?" / "tem disponível?" → ver_estoque
- "quero 500 parafusos" / "preciso de 1000 unidades" / "adiciona SKU001" → adicionar_item
- "ver carrinho" / "meu carrinho" / "o que tenho" → ver_carrinho
- "quero proposta" / "me manda orçamento" / "gera proposta" → gerar_proposta
- "tá caro" / "consegue 15% de desconto?" / "melhor preço" / "reduz o valor" → negociar
- "topei" / "aceito" / "pode fechar" / "fechado" → aceitar
- "não quero" / "muito caro" / "desisto" → rejeitar
- "qual o prazo?" / "quando entrega?" / "demora quanto?" → prazo_entrega
- "como pago?" / "tem parcelamento?" / "aceita boleto?" → condicao_pagto
- "limpar carrinho" / "cancelar tudo" / "recomeçar" → limpar_carrinho
- "ajuda" / "help" / "o que você faz?" → ajuda
- "/debug" / "como decidiu?" / "explica" → debug

ENTIDADES A EXTRAIR:
- product_name: nome do produto (string ou null)
- sku: código SKU como SKU001 (string ou null)
- quantity: quantidade numérica (integer ou null)
- discount_percent: percentual de desconto (float ou null)
- payment_condition: condição de pagamento (string ou null)
- proposal_id: ID de proposta PROP-XXX (string ou null)

FORMATO DE SAÍDA (JSON puro):
{{"intent": "nome", "confidence": 0.95, "product_name": null, "sku": null, "quantity": null, "discount_percent": null, "payment_condition": null, "proposal_id": null, "entities": {{}}}}"""

        prompt = f'Mensagem do cliente: "{text}"\n\nJSON:'

        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,   # Baixo para respostas determinísticas
                        "num_predict": 200,
                        "top_p": 0.9,
                    },
                },
                timeout=20,
            )
            resp.raise_for_status()
            raw_response = resp.json().get("response", "").strip()
            logger.debug(f"NLU raw response: {raw_response}")

            # Extrai JSON da resposta (pode vir com texto ao redor)
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                parsed["raw_text"] = text
                return parsed

        except json.JSONDecodeError as e:
            logger.warning(f"NLU JSON parse error: {e} | response: {raw_response[:200]}")
        except requests.exceptions.Timeout:
            logger.warning("NLU timeout — usando fallback heurístico")
        except Exception as e:
            logger.warning(f"NLU error: {e}")

        return {}

    # ------------------------------------------------------------------
    # FALLBACK HEURÍSTICO (quando LLM falha ou demora)
    # ------------------------------------------------------------------

    def _heuristic_parse(self, text: str) -> Dict:
        """Extrai intenção e entidades via heurísticas simples como fallback."""
        text_lower = text.lower()
        result = {"intent": "outro", "confidence": 0.4, "raw_text": text}

        # Detecta desconto
        discount_match = re.search(
            r'(\d+(?:[.,]\d+)?)\s*%', text_lower
        )
        if discount_match:
            result["discount_percent"] = float(discount_match.group(1).replace(",", "."))
            if any(w in text_lower for w in ["desconto", "abat", "reduz", "baixa", "menos", "barato", "caro"]):
                result["intent"] = "negociar"
                result["confidence"] = 0.75

        # Detecta SKU
        sku_match = re.search(r'\b(sku\s*0*\d+)\b', text_lower)
        if sku_match:
            result["sku"] = sku_match.group(1).upper().replace(" ", "")

        # Detecta quantidade
        qty_match = re.search(r'\b(\d{1,6})\s*(un(?:idades?)?|pç|peças?|metros?|kg|litros?|caixas?)?\b', text_lower)
        if qty_match:
            result["quantity"] = int(qty_match.group(1))

        # Detecta intenção por palavras-chave
        if any(w in text_lower for w in ["buscar", "procurar", "tem ", "vocês têm", "tem parafuso",
                                          "quero ver", "mostrar", "listar", "catálogo"]):
            result["intent"] = "buscar_produto"
            result["confidence"] = 0.7

        if any(w in text_lower for w in ["disponível", "disponibilidade", "tem estoque", "tem em estoque",
                                          "quanto tem", "quantos tem"]):
            result["intent"] = "ver_estoque"
            result["confidence"] = 0.7

        if any(w in text_lower for w in ["adicionar", "quero", "preciso", "comprar", "pedir",
                                          "colocar", "incluir", "separar"]):
            if result.get("quantity") or result.get("sku"):
                result["intent"] = "adicionar_item"
                result["confidence"] = 0.7

        if any(w in text_lower for w in ["aceito", "aceitar", "topei", "fechado", "pode fechar",
                                          "tá bom", "ta bom", "ok", "combinado", "confirmado"]):
            result["intent"] = "aceitar"
            result["confidence"] = 0.75

        if any(w in text_lower for w in ["não quero", "nao quero", "recuso", "muito caro",
                                          "desistir", "cancelar", "não vou", "nao vou"]):
            result["intent"] = "rejeitar"
            result["confidence"] = 0.75

        if any(w in text_lower for w in ["prazo", "entrega", "quando chega", "demora", "dias"]):
            result["intent"] = "prazo_entrega"
            result["confidence"] = 0.7

        if any(w in text_lower for w in ["pagamento", "pagar", "parcel", "boleto", "pix",
                                          "cartão", "cartao", "à vista", "a vista", "30/60"]):
            result["intent"] = "condicao_pagto"
            result["confidence"] = 0.7

        # Extrai nome de produto por heurística
        product_keywords = ["parafuso", "corrente", "rolamento", "correia", "polia",
                             "mancal", "lubrificante", "fixação", "fixacao"]
        for kw in product_keywords:
            if kw in text_lower:
                result["product_name"] = kw
                if result["intent"] == "outro":
                    result["intent"] = "buscar_produto"
                    result["confidence"] = 0.65
                break

        return result

    # ------------------------------------------------------------------
    # INTERFACE PRINCIPAL
    # ------------------------------------------------------------------

    def parse(self, text: str) -> NLUResult:
        """
        Analisa mensagem e retorna NLUResult com intenção e entidades.
        Fluxo: regras rápidas → Ollama LLM → fallback heurístico
        """
        if not text or not text.strip():
            return NLUResult({"intent": "outro", "confidence": 1.0, "raw_text": text})

        # 1. Tenta regras rápidas (sem LLM)
        quick_intent = self._quick_match(text)
        if quick_intent:
            logger.debug(f"NLU quick match: '{text}' → {quick_intent}")
            return NLUResult({
                "intent": quick_intent,
                "confidence": 1.0,
                "raw_text": text,
            })

        # 2. Tenta Ollama LLM
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
            ollama_ok = resp.status_code == 200
        except Exception:
            ollama_ok = False

        if ollama_ok:
            llm_result = self._call_ollama_nlu(text)
            if llm_result and llm_result.get("intent") and llm_result.get("intent") != "outro":
                logger.info(f"NLU LLM: '{text[:50]}' → {llm_result.get('intent')} ({llm_result.get('confidence', 0):.2f})")
                llm_result["raw_text"] = text
                return NLUResult(llm_result)

        # 3. Fallback heurístico
        heuristic = self._heuristic_parse(text)
        logger.info(f"NLU heuristic: '{text[:50]}' → {heuristic.get('intent')} ({heuristic.get('confidence', 0):.2f})")
        return NLUResult(heuristic)
