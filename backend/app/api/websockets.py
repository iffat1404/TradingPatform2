import asyncio
from datetime import datetime
from typing import Dict, Any, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.orm import Account
from app.services.feed_simulator import get_current_tick_for_ticker, get_all_current_ticks
from app.services.portfolio_engine import calculate_portfolio_metrics, get_latest_market_prices
from app.services.market_clock import get_market_clock

router = APIRouter()


def _extract_minute_key(dt: datetime) -> Tuple[int, int, int, int, int]:
    """Helper to derive a unique minute key for tick boundary checking."""
    return dt.year, dt.month, dt.day, dt.hour, dt.minute


def _with_session(fn, *args):
    """
    Run a DB call on a short-lived session.

    WebSocket handlers must NOT hold a pooled connection for the lifetime of the socket:
    the pool is small (5 + 10 overflow), so a handful of open sockets would starve every
    HTTP request of a connection and 500 the whole API.
    """
    db: Session = SessionLocal()
    try:
        return fn(*args, db)
    finally:
        db.close()


@router.websocket("/market/{ticker}")
async def market_websocket(websocket: WebSocket, ticker: str):
    await websocket.accept()
    ticker = ticker.upper()
    clock = get_market_clock()

    last_broadcast_minute = None
    client_id = f"{ticker}_{id(websocket)}"

    try:
        print(f"Client {client_id} connected to market websocket for {ticker}")

        while True:
            simulated_now = clock.now()
            current_minute = _extract_minute_key(simulated_now)

            if current_minute != last_broadcast_minute:
                current_tick = await asyncio.to_thread(
                    _with_session, get_current_tick_for_ticker, ticker
                )

                if current_tick:
                    payload = {
                        "type": "tick",
                        "timestamp": simulated_now.isoformat(),
                        "ticker": ticker,
                        "price": current_tick.get("close", 0.0),
                        "open": current_tick.get("open", 0.0),
                        "high": current_tick.get("high", 0.0),
                        "low": current_tick.get("low", 0.0),
                        "volume": current_tick.get("volume", 0),
                        "change": 0.0,
                        "change_percent": 0.0
                    }
                    try:
                        await websocket.send_json(payload)
                        last_broadcast_minute = current_minute
                    except Exception as e:
                        print(f"Error sending data to client {client_id}: {e}")
                        break

            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        # Gracefully handle client tab close / route change
        print(f"Client {client_id} disconnected from market websocket for {ticker}")
    except asyncio.CancelledError:
        print(f"Client {client_id} connection cancelled for {ticker}")
    except Exception as e:
        # Log unexpected errors
        print(f"Unexpected error in market websocket for {ticker} (client {client_id}): {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

@router.websocket("/market/all")
async def all_markets_websocket(websocket: WebSocket):
    """
    Stream real-time market data for all tickers in a single batch.
    Emits snapshots when MarketClock advances to a new simulated minute.
    """
    await websocket.accept()
    clock = get_market_clock()

    last_broadcast_minute = None
    client_id = f"all_markets_{id(websocket)}"

    try:
        print(f"Client {client_id} connected to all markets websocket")
        
        while True:
            simulated_now = clock.now()
            current_minute = _extract_minute_key(simulated_now)

            if current_minute != last_broadcast_minute:
                all_ticks = await asyncio.to_thread(_with_session, get_all_current_ticks)

                tickers_payload: Dict[str, Any] = {}
                if all_ticks:
                    for symbol, tick in all_ticks.items():
                        tickers_payload[symbol] = {
                            "price": tick.get("close", 0.0),
                            "open": tick.get("open", 0.0),
                            "high": tick.get("high", 0.0),
                            "low": tick.get("low", 0.0),
                            "volume": tick.get("volume", 0)
                        }

                payload = {
                    "type": "market_snapshot",
                    "timestamp": simulated_now.isoformat(),
                    "tickers": tickers_payload
                }

                try:
                    await websocket.send_json(payload)
                    last_broadcast_minute = current_minute
                except Exception as e:
                    print(f"Error sending data to client {client_id}: {e}")
                    break

            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        print(f"Client {client_id} disconnected from all markets websocket")
    except asyncio.CancelledError:
        print(f"Client {client_id} connection cancelled for all markets")
    except Exception as e:
        print(f"Error in all markets websocket (client {client_id}): {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/account/{account_id}")
async def account_websocket(websocket: WebSocket, account_id: str):
    """
    Stream account/portfolio valuation updates synced with MarketClock timestamps.
    """
    await websocket.accept()
    clock = get_market_clock()

    last_broadcast_minute = None
    client_id = f"account_{account_id}_{id(websocket)}"

    def _build_snapshot():
        """All three reads share one short-lived session, released before the next tick."""
        db: Session = SessionLocal()
        try:
            current_prices = get_latest_market_prices(db)
            metrics = calculate_portfolio_metrics(db, account_id, current_prices)
            account = db.query(Account).filter(Account.id == account_id).first()
            return metrics, (account.cash_balance if account else 0.0)
        finally:
            db.close()

    try:
        print(f"Client {client_id} connected to account websocket")
        
        while True:
            simulated_now = clock.now()
            current_minute = _extract_minute_key(simulated_now)

            if current_minute != last_broadcast_minute:
                try:
                    metrics, cash = await asyncio.to_thread(_build_snapshot)

                    payload = {
                        "type": "account_update",
                        "timestamp": simulated_now.isoformat(),
                        "account_id": account_id,
                        "cash_balance": cash,
                        "net_worth": metrics.get("net_worth", cash),
                        "market_value": metrics.get("market_value", 0.0),
                        "unrealized_pnl": metrics.get("unrealized_pnl", 0.0),
                        "realized_pnl": metrics.get("realized_pnl", 0.0),
                        "positions_count": len(metrics.get("positions", []))
                    }

                    try:
                        await websocket.send_json(payload)
                        last_broadcast_minute = current_minute
                    except Exception as e:
                        print(f"Error sending data to client {client_id}: {e}")
                        break

                except Exception as e:
                    print(f"Error updating account {account_id}: {e}")

            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        print(f"Client {client_id} disconnected from account websocket for {account_id}")
    except asyncio.CancelledError:
        print(f"Client {client_id} connection cancelled for account {account_id}")
    except Exception as e:
        print(f"Error in account websocket for {account_id} (client {client_id}): {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/session")
async def session_websocket(websocket: WebSocket):
    """
    Global session synchronization WebSocket.
    Pushes MarketClock state every 100ms so UI clocks and speed badges update smoothly.
    """
    await websocket.accept()
    clock = get_market_clock()
    client_id = f"session_{id(websocket)}"

    try:
        print(f"Client {client_id} connected to session websocket")
        
        while True:
            clock_status = clock.get_status()

            payload = {
                "type": "market/session/update",
                "simulated_time": clock_status["simulated_time"],
                "speed_multiplier": clock_status["speed_multiplier"],
                "market_status": clock_status["market_status"],
                "session_id": clock_status["session_id"]
            }

            try:
                await websocket.send_json(payload)
            except Exception as e:
                print(f"Error sending data to client {client_id}: {e}")
                break
                
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        print(f"Client {client_id} disconnected from session websocket")
    except asyncio.CancelledError:
        print(f"Client {client_id} connection cancelled for session")
    except Exception as e:
        print(f"Error in session websocket (client {client_id}): {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/admin/notifications")
async def admin_websocket(websocket: WebSocket):
    """
    Stream admin notifications and MarketClock status updates.
    """
    await websocket.accept()
    clock = get_market_clock()
    client_id = f"admin_{id(websocket)}"

    try:
        print(f"Client {client_id} connected to admin notifications websocket")
        
        while True:
            clock_status = clock.get_status()

            payload = {
                "type": "admin_notification",
                "timestamp": clock.now().isoformat(),
                "message": "System operational",
                "severity": "info",
                "market_clock": clock_status
            }

            try:
                await websocket.send_json(payload)
            except Exception as e:
                print(f"Error sending data to client {client_id}: {e}")
                break
                
            await asyncio.sleep(5)

    except WebSocketDisconnect:
        print(f"Client {client_id} disconnected from admin notifications websocket")
    except asyncio.CancelledError:
        print(f"Client {client_id} connection cancelled for admin notifications")
    except Exception as e:
        print(f"Error in admin notifications websocket (client {client_id}): {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass