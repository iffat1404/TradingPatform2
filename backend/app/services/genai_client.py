from typing import Dict, Any
import os
import re
import json

try:
    import anthropic
except Exception:  # pragma: no cover - optional dependency
    anthropic = None


def _get_claude_client():
    """Get a Claude client if API key is configured, else return None."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or anthropic is None:
        return None
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception:
        return None


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
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
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
                # Try to extract JSON from response
                json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    extracted = json.loads(json_str)
                    parsed.update(extracted)
                else:
                    # Fallback: try parsing entire response as JSON
                    parsed.update(json.loads(text))
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
                model="claude-3-5-sonnet-20241022",
                max_tokens=512,
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
                # Extract JSON from response
                json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
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
                model="claude-3-5-sonnet-20241022",
                max_tokens=512,
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
                "generated_by": "claude"
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
                model="claude-3-5-sonnet-20241022",
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": f"""Generate a concise portfolio summary (2-3 sentences) based on this data:

{context}

Focus on overall portfolio health, diversification, and any notable concentrations."""
                }],
            )
            
            summary = response.content[0].text if response.content else ""
            
            return {
                "summary": summary,
                "generated_by": "claude",
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


def explain_order_rejection(order_id: str, reason_code: str) -> Dict[str, Any]:
    """
    Explain order rejection in plain English using Claude for enhanced explanations.
    Falls back to deterministic reason code mapping if Claude is unavailable.
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
                model="claude-3-5-sonnet-20241022",
                max_tokens=256,
                messages=[{
                    "role": "user",
                    "content": f"""Explain this order rejection in plain, user-friendly language:

Order ID: {order_id}
Reason Code: {reason_code}
Base Reason: {base_reason}

Provide a clear explanation (1-2 sentences) that helps the user understand what went wrong and how to fix it."""
                }],
            )
            
            enhanced_explanation = response.content[0].text if response.content else ""
            
            return {
                "explanation": enhanced_explanation,
                "reason_code": reason_code,
                "generated_by": "claude"
            }
        except Exception as e:
            print(f"Claude rejection explanation failed: {e}")
            # Fall through to deterministic explanation
    
    # Fallback to deterministic explanation
    try:
        return {
            "explanation": f"Order {order_id} was rejected because {base_reason}.",
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