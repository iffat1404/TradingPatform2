from typing import Dict, Any
import os
import re
import json

try:
    import anthropic
except Exception:  # pragma: no cover - optional dependency
    anthropic = None


from app.core.config import settings

# Single source of truth for the model name. The training proxy serves nova-micro /
# claude-haiku-4-5 / claude-sonnet-4-6 — the old hardcoded "claude-3-5-sonnet-20241022"
# does not exist there and would 404 every call.
GENAI_MODEL = settings.GENAI_MODEL


def capped_max_tokens(requested: int) -> int:
    """Clamp a call's tuned max_tokens to the configured budget ceiling."""
    return min(requested, settings.GENAI_MAX_TOKENS)


GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Gemini's flash models spend maxOutputTokens on internal "thinking" BEFORE emitting any
# text, and thinkingBudget=0 is rejected (400) by gemini-flash-latest. Measured overhead is
# ~80 tokens for a one-word reply but 780-850 for a coaching prompt — so a 1024 budget left
# only ~120 tokens of real output and truncated narratives mid-sentence. Floor high enough
# that thinking cannot starve the answer; billing is on tokens actually produced, and
# responses still stop naturally at finishReason=STOP.
GEMINI_MIN_OUTPUT_TOKENS = 2048


def provider_label() -> str:
    """
    What actually generated a response, for the `generated_by` field.
    Historically hardcoded to "claude"; now reports the real provider.
    """
    provider = (settings.GENAI_PROVIDER or "gemini").strip().lower()
    return "gemini" if provider == "gemini" else "claude"


def extract_json_block(text: str):
    """
    Pull a JSON object out of a model response.

    Models wrap JSON in ```json fences and prose, and the old `\\{[^}]+\\}` pattern could not
    match nested objects. This strips fences, then takes the outermost balanced {...}.
    """
    if not text:
        return None

    cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()

    start = cleaned.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start:i + 1])
                except Exception:
                    return None
    return None


class _TextBlock:
    """Mimics an Anthropic content block so call sites can read `.text`."""

    def __init__(self, text: str):
        self.text = text


class _AdaptedResponse:
    """Mimics an Anthropic response so call sites can read `.content[0].text`."""

    def __init__(self, text: str):
        self.content = [_TextBlock(text)] if text else []


class _GeminiMessages:
    """
    Translates the Anthropic `messages.create(...)` call this codebase already uses into a
    Gemini REST request, so swapping providers needs no changes at any call site.
    """

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    @staticmethod
    def _to_parts(content) -> list:
        # Anthropic accepts either a plain string or a list of typed blocks (text/image).
        if isinstance(content, str):
            return [{"text": content}]

        parts = []
        for block in content or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append({"text": block.get("text", "")})
            elif block.get("type") == "image":
                source = block.get("source", {}) or {}
                parts.append({
                    "inline_data": {
                        "mime_type": source.get("media_type", "image/png"),
                        "data": source.get("data", ""),
                    }
                })
        return parts or [{"text": ""}]

    def create(self, model=None, max_tokens=512, messages=None, **_kwargs):
        import httpx  # already a hard dependency of this project

        parts = []
        for message in messages or []:
            parts.extend(self._to_parts(message.get("content")))

        response = httpx.post(
            GEMINI_ENDPOINT.format(model=self._model),
            headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
            json={
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "maxOutputTokens": max(max_tokens, GEMINI_MIN_OUTPUT_TOKENS),
                },
            },
            timeout=45.0,
        )
        if response.status_code != 200:
            # Surface Google's own message — raise_for_status hides the useful part.
            try:
                detail = (response.json().get("error", {}).get("message") or "")[:200]
            except Exception:
                detail = response.text[:200]
            raise RuntimeError(f"Gemini HTTP {response.status_code}: {detail}")
        payload = response.json()

        candidates = payload.get("candidates") or []
        if not candidates:
            # Usually a safety block; surface it as "no content" so callers fall back.
            return _AdaptedResponse("")
        # A thinking-only response has no `parts` at all — treat as empty so callers fall back.
        out_parts = (candidates[0].get("content") or {}).get("parts") or []
        return _AdaptedResponse("".join(p.get("text", "") for p in out_parts))


class _GeminiClient:
    def __init__(self, api_key: str, model: str):
        self.messages = _GeminiMessages(api_key, model)


class _AnthropicHTTPMessages:
    """
    Anthropic Messages API over plain HTTP.

    The official SDK is deliberately not used here: the Echios proxy's WAF rejects the
    SDK's requests with 403 "Your request was blocked", while an identical plain-HTTP call
    succeeds. Going direct also removes a hard dependency on the SDK version — the pinned
    0.7.8 predated `client.messages` entirely, so every call silently fell back.

    The request/response shape is Anthropic's own, so message content (including image
    blocks) passes straight through.
    """

    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._base_url = (base_url or "https://api.anthropic.com").rstrip("/")

    def create(self, model=None, max_tokens=512, messages=None, **_kwargs):
        import httpx

        response = httpx.post(
            f"{self._base_url}/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={"model": model, "max_tokens": max_tokens, "messages": messages or []},
            timeout=45.0,
        )
        if response.status_code != 200:
            try:
                detail = str(response.json().get("error", {}).get("message", ""))[:200]
            except Exception:
                detail = response.text[:200]
            raise RuntimeError(f"Anthropic HTTP {response.status_code}: {detail}")

        blocks = response.json().get("content") or []
        return _AdaptedResponse("".join(b.get("text", "") for b in blocks if isinstance(b, dict)))


class _AnthropicHTTPClient:
    def __init__(self, api_key: str, base_url: str):
        self.messages = _AnthropicHTTPMessages(api_key, base_url)


def _get_claude_client():
    """
    Return an LLM client for the configured provider, or None to force deterministic
    fallbacks. Despite the legacy name, this may return a Gemini adapter — both expose the
    same `.messages.create(...)` surface, so no call site needs to know the difference.

    Settings are read first (so backend/.env works), with the raw environment as a fallback
    for shell-exported keys.
    """
    provider = (settings.GENAI_PROVIDER or "gemini").strip().lower()

    if provider == "none":
        return None

    if provider == "gemini":
        api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        try:
            return _GeminiClient(api_key, settings.GEMINI_MODEL or "gemini-2.0-flash")
        except Exception:
            return None

    # provider == "anthropic": Echios LiteLLM proxy (or Anthropic direct if base_url unset)
    api_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    base_url = settings.ANTHROPIC_BASE_URL or os.getenv("ANTHROPIC_BASE_URL")
    try:
        return _AnthropicHTTPClient(api_key, base_url)
    except Exception:
        return None


def active_model() -> str:
    """The model name currently in use, for diagnostics and logging."""
    provider = (settings.GENAI_PROVIDER or "gemini").strip().lower()
    if provider == "gemini":
        return settings.GEMINI_MODEL or "gemini-2.0-flash"
    if provider == "none":
        return "(disabled)"
    return GENAI_MODEL


def _fallback_extraction() -> Dict[str, Any]:
    return {
        "extracted_full_name": None,
        "extracted_dob": None,
        "extracted_id_number": None,
        "extracted_expiry_date": None,
        "extracted_issuing_country": None,
        "extraction_confidence": None,
    }


def extract_id_document_fields(file_path: str, content_type: str) -> Dict[str, Any]:
    """Extract fields from an ID document using Claude when configured, otherwise a deterministic fallback."""
    if not file_path or not os.path.exists(file_path):
        return _fallback_extraction()

    client = _get_claude_client()
    if not client:
        return _fallback_extraction()

    try:
        with open(file_path, "rb") as uploaded_file:
            # Read file and convert to base64
            file_data = uploaded_file.read()
            import base64
            base64_data = base64.b64encode(file_data).decode('utf-8')
            
            response = client.messages.create(
                model=GENAI_MODEL,
                max_tokens=capped_max_tokens(1024),
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": """Extract the following fields from this ID document and return as JSON:
- extracted_full_name: Full name as shown on document
- extracted_dob: Date of birth in YYYY-MM-DD format
- extracted_id_number: ID/document number
- extracted_expiry_date: Expiry date in YYYY-MM-DD format  
- extracted_issuing_country: Country that issued the document
- extraction_confidence: Your confidence level (high/medium/low)

Return null for any field not present. Do not guess or make up values."""
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": content_type,
                                "data": base64_data
                            }
                        }
                    ],
                }],
            )
        
        text = response.content[0].text if response.content else ""
        parsed = {
            "extracted_full_name": None, 
            "extracted_dob": None, 
            "extracted_id_number": None, 
            "extracted_expiry_date": None, 
            "extracted_issuing_country": None, 
            "extraction_confidence": "low"
        }
        
        if text:
            try:
                extracted = extract_json_block(text)
                if extracted:
                    parsed.update(extracted)
            except Exception:
                pass
        
        return parsed
    except Exception as e:
        # Graceful degradation per principle 14
        print(f"Claude ID extraction failed: {e}")
        return _fallback_extraction()


def parse_order_command(text: str) -> Dict[str, Any]:
    """
    Parse a natural-language order command into a draft order using Claude.
    Falls back to deterministic regex parsing if Claude is unavailable.
    Per principle 2: always returns draft for confirmation, never auto-submits.
    """
    client = _get_claude_client()
    
    # Try Claude first
    if client:
        try:
            response = client.messages.create(
                model=GENAI_MODEL,
                max_tokens=capped_max_tokens(512),
                messages=[{
                    "role": "user",
                    "content": f"""Parse this trading order request and return as JSON:
"{text}"

Return JSON with these exact keys:
- ticker: Stock ticker symbol (uppercase)
- side: "buy" or "sell" 
- qty: Integer quantity
- type: "market" or "limit"
- price: Limit price if limit order, else null
- confidence: "high" or "medium" or "low"
- requires_confirmation: true (always true per principle 2)

If the request is unclear or incomplete, set draft_order to null and include an error message.
Supported tickers: AAPL, GOOG, IBM, MSFT, TSLA, UL, WMT"""
                }],
            )
            
            response_text = response.content[0].text if response.content else ""
            
            try:
                parsed = extract_json_block(response_text)
                if parsed:
                    # Models sometimes wrap the fields in their own "draft_order" key,
                    # which would otherwise nest one inside the other.
                    inner = parsed.get("draft_order")
                    if isinstance(inner, dict):
                        merged = {**inner, **{k: v for k, v in parsed.items() if k != "draft_order"}}
                        parsed = merged
                    parsed.pop("error", None)
                    # Ensure requires_confirmation is always true
                    parsed["requires_confirmation"] = True
                    return {
                        "draft_order": parsed,
                        "confidence": parsed.get("confidence", "medium"),
                        "requires_confirmation": True
                    }
            except Exception as e:
                print(f"Claude order parsing JSON extraction failed: {e}")
                # Fall through to regex parsing
                
        except Exception as e:
            print(f"Claude order parsing failed: {e}")
            # Fall through to regex parsing
    
    # Fallback to deterministic regex parsing
    try:
        normalized = (text or "").strip().lower()
        if not normalized:
            return {
                "draft_order": None,
                "confidence": "low",
                "requires_confirmation": True,
                "error": "No order text provided",
            }

        match = re.search(r"\b(buy|sell)\b\s+(\d+)\s+([a-z]{1,5})\b", normalized)
        if match:
            side = match.group(1)
            qty = int(match.group(2))
            ticker = match.group(3).upper()
            price_match = re.search(r"at\s+(\d+(?:\.\d+)?)", normalized)
            draft_order = {
                "ticker": ticker,
                "side": side,
                "qty": qty,
                "type": "limit",
                "price": float(price_match.group(1)) if price_match else None,
            }
            return {
                "draft_order": draft_order,
                "confidence": "medium",
                "requires_confirmation": True,
            }

        return {
            "draft_order": None,
            "confidence": "low",
            "requires_confirmation": True,
            "error": "Could not parse order text",
        }
    except Exception:
        return {
            "draft_order": None,
            "confidence": "low",
            "requires_confirmation": True,
            "error": "Parsing failed",
        }


def explain_news_sentiment(ticker: str, date: str) -> Dict[str, Any]:
    """
    Explain news sentiment for a ticker on a given date using Claude.
    Uses stored sentiment data as context for the explanation.
    """
    client = _get_claude_client()
    
    # Get sentiment data from database
    sentiment_context = ""
    try:
        from app.core.db import SessionLocal
        from app.models.orm import NewsSentimentDaily
        db = SessionLocal()
        try:
            record = (
                db.query(NewsSentimentDaily)
                .filter(NewsSentimentDaily.ticker == ticker.upper())
                .order_by(NewsSentimentDaily.date.desc())
                .first()
            )
            if record:
                sentiment_context = f"Average sentiment score: {record.avg_sentiment:.2f} based on {record.headline_count} headlines."
        finally:
            db.close()
    except Exception:
        sentiment_context = "Sentiment data unavailable."
    
    # Try Claude for explanation
    if client:
        try:
            response = client.messages.create(
                model=GENAI_MODEL,
                max_tokens=capped_max_tokens(512),
                messages=[{
                    "role": "user",
                    "content": f"""Explain the news sentiment for {ticker.upper()} on {date}.

Context: {sentiment_context}

Provide a concise explanation (2-3 sentences) of what the sentiment means for investors.
Focus on the practical implications rather than just restating the score."""
                }],
            )
            
            explanation = response.content[0].text if response.content else ""
            
            return {
                "ticker": ticker.upper(),
                "date": date,
                "summary": explanation,
                "context": sentiment_context,
                "generated_by": provider_label()
            }
        except Exception as e:
            print(f"Claude sentiment explanation failed: {e}")
            # Fall through to deterministic response
    
    # Fallback to deterministic explanation
    try:
        from app.core.db import SessionLocal
        from app.models.orm import NewsSentimentDaily
        db = SessionLocal()
        try:
            record = (
                db.query(NewsSentimentDaily)
                .filter(NewsSentimentDaily.ticker == ticker.upper())
                .order_by(NewsSentimentDaily.date.desc())
                .first()
            )
            if record:
                sentiment_level = "positive" if record.avg_sentiment > 0.2 else "negative" if record.avg_sentiment < -0.2 else "neutral"
                return {
                    "ticker": ticker.upper(),
                    "date": date,
                    "summary": f"News sentiment for {ticker.upper()} on {date} is {sentiment_level} (score: {record.avg_sentiment:.2f}) based on {record.headline_count} headlines.",
                    "headline_count": record.headline_count,
                    "avg_sentiment": record.avg_sentiment,
                    "generated_by": "deterministic"
                }
        finally:
            db.close()
        
        return {
            "ticker": ticker.upper(),
            "date": date,
            "summary": f"News flow for {ticker.upper()} on {date} appears balanced with no major catalyst flagged.",
            "headline_count": 0,
            "avg_sentiment": 0.0,
            "generated_by": "deterministic"
        }
    except Exception:
        return {
            "ticker": ticker.upper(),
            "date": date,
            "summary": None,
            "headline_count": 0,
            "avg_sentiment": 0.0,
            "error": "Explanation failed",
            "generated_by": "error"
        }


def generate_portfolio_summary(portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate an AI-powered portfolio summary using Claude.
    Falls back to deterministic summary if Claude is unavailable.
    """
    client = _get_claude_client()
    
    # Try Claude for enhanced summary
    if client:
        try:
            positions = portfolio_data.get("positions", [])
            total_value = portfolio_data.get("total_value", 0.0)
            cash_balance = portfolio_data.get("cash_balance", 0.0)
            
            # Build context from portfolio data
            position_summary = "\n".join([
                f"- {pos.get('ticker', 'Unknown')}: {pos.get('signed_qty', 0)} shares @ ${pos.get('avg_cost', 0):.2f}"
                for pos in positions
            ])
            
            context = f"""Portfolio Summary:
Total Value: ${total_value:.2f}
Cash Balance: ${cash_balance:.2f}
Positions: {len(positions)}
{position_summary if position_summary else 'No positions'}"""
            
            response = client.messages.create(
                model=GENAI_MODEL,
                max_tokens=capped_max_tokens(512),
                messages=[{
                    "role": "user",
                    "content": f"""Generate a concise portfolio summary (2-3 sentences) based on this data:

{context}

Focus on overall portfolio health, diversification, and any notable concentrations.
Describe what the account currently holds. Do not recommend buying, selling, holding, or
timing anything, and do not comment on where any price is headed."""
                }],
            )
            
            summary = response.content[0].text if response.content else ""
            
            return {
                "summary": summary,
                "generated_by": provider_label(),
                "portfolio_value": total_value,
                "position_count": len(positions)
            }
        except Exception as e:
            print(f"Claude portfolio summary failed: {e}")
            # Fall through to deterministic summary
    
    # Fallback to deterministic summary
    try:
        positions = portfolio_data.get("positions", [])
        total_value = portfolio_data.get("total_value", 0.0)
        cash_balance = portfolio_data.get("cash_balance", 0.0)
        
        return {
            "summary": f"Portfolio currently values at ${total_value:.2f} with ${cash_balance:.2f} in cash across {len(positions)} positions.",
            "generated_by": "deterministic",
            "portfolio_value": total_value,
            "position_count": len(positions)
        }
    except Exception:
        return {
            "summary": None,
            "error": "Summary generation failed",
            "generated_by": "error"
        }


def explain_order_rejection(
    order_id: str, reason_code: str, reason_detail: str | None = None
) -> Dict[str, Any]:
    """
    Explain order rejection in plain English using Claude for enhanced explanations.
    Falls back to deterministic reason code mapping if Claude is unavailable.

    `reason_code`/`reason_detail` come from the order's own audit trail (resolved by the
    caller, which is where the account scoping lives). The reason is never guessed.
    """
    client = _get_claude_client()
    
    # Deterministic reason mapping (always available)
    reason_map = {
        "KYC_NOT_APPROVED": "identity verification is still pending approval",
        "INVALID_TICKER": "the ticker is unsupported",
        "MARKET_CLOSED": "the simulated market is closed",
        "PRICE_COLLAR_BREACH": "the limit price fell outside the allowed collar",
        "NOTIONAL_LIMIT_EXCEEDED": "the order notional exceeded the cap",
        "CONCENTRATION_LIMIT_EXCEEDED": "the order would breach concentration limits",
        "INSUFFICIENT_BUYING_POWER": "buying power or collateral was insufficient",
        "ORDER_RATE_LIMIT_EXCEEDED": "the account exceeded the order rate limit",
    }
    
    base_reason = reason_map.get(reason_code, reason_code)
    
    # Try Claude for enhanced explanation
    if client:
        try:
            response = client.messages.create(
                model=GENAI_MODEL,
                max_tokens=capped_max_tokens(256),
                messages=[{
                    "role": "user",
                    "content": f"""You explain order rejections on Shunryū STP, a paper-trading
simulator used for training. An order was refused by a deterministic pre-trade risk check.

Reason code: {reason_code}
What that check means: {base_reason}
Message recorded on the order: {reason_detail or base_reason}

Write 2-3 sentences for the trader:
1. What the check is and why it stopped this specific order.
2. What they can change to get it through (smaller size, a different limit price, waiting for
   the market session, completing KYC - whatever actually matches the code above).

Hard rules:
- The reason above is the real, recorded reason. Never call it unknown, a glitch, a bug, or a
  system error, and never suggest contacting support - this is a simulator with no support desk.
- Explain the rule that fired. Do not tell them whether the trade itself was a good idea, and
  do not give any buy/sell/hold or market-timing advice.
- Plain sentences, no headings, no bullet points."""
                }],
            )
            
            enhanced_explanation = response.content[0].text if response.content else ""
            
            return {
                "explanation": enhanced_explanation,
                "reason_code": reason_code,
                "generated_by": provider_label()
            }
        except Exception as e:
            print(f"Claude rejection explanation failed: {e}")
            # Fall through to deterministic explanation
    
    # Fallback to deterministic explanation
    try:
        return {
            "explanation": (
                f"This order was rejected because {base_reason}."
                + (f" {reason_detail}" if reason_detail else "")
            ),
            "reason_code": reason_code,
            "generated_by": "deterministic"
        }
    except Exception:
        return {
            "explanation": None,
            "error": "Explanation failed",
            "reason_code": reason_code,
            "generated_by": "error"
        }