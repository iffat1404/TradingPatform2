import pandas as pd
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from sqlalchemy.orm import Session
from app.models.orm import PriceHistoryDaily, PriceHistoryMinute, NewsSentimentDaily, NewsArticle
from app.core.config import settings

# Supported tickers per Section 2
SUPPORTED_TICKERS = ["AAPL", "GOOG", "IBM", "MSFT", "TSLA", "UL", "WMT"]


def load_historical_daily_data(db: Session, data_dir: str = "data") -> int:
    """
    Load historical daily OHLCV data from CSV files into price_history_daily table.
    
    Expected format: simulation_historical_data/*.csv
    Each CSV should have columns: date, open, high, low, close, adj_close, volume
    """
    historical_dir = Path(data_dir) / "simulation_historical_data"
    
    if not historical_dir.exists():
        print(f"Warning: Historical data directory not found: {historical_dir}")
        return 0
    
    total_rows = 0
    
    for csv_file in historical_dir.glob("*.csv"):
        # Extract ticker from filename (handle "simulated_" prefix)
        ticker = csv_file.stem.upper()
        if ticker.startswith("SIMULATED_"):
            ticker = ticker.replace("SIMULATED_", "")
        
        # Remove any additional suffixes like "_2026_historical"
        ticker = ticker.replace("_2026_HISTORICAL", "").replace("_HISTORICAL", "")
        
        # Skip unsupported tickers
        if ticker not in SUPPORTED_TICKERS:
            continue
        
        try:
            df = pd.read_csv(csv_file)
            
            # Ensure required columns exist
            # Check for either 'date' or 'timestamp' column
            date_col = 'date' if 'date' in df.columns else 'timestamp'
            required_cols = [date_col, 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                print(f"Warning: Skipping {csv_file} - missing required columns")
                print(f"  Available columns: {list(df.columns)}")
                continue
            
            # Process each row
            for _, row in df.iterrows():
                # Parse date (explicitly set to UTC per principle 12)
                date_str = row[date_col]
                if isinstance(date_str, str):
                    date_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                else:
                    date_dt = pd.to_datetime(date_str).to_pydatetime()
                    if date_dt.tzinfo is None:
                        date_dt = date_dt.replace(tzinfo=timezone.utc)
                
                # Check if record already exists
                existing = db.query(PriceHistoryDaily).filter(
                    PriceHistoryDaily.ticker == ticker,
                    PriceHistoryDaily.date == date_dt
                ).first()
                
                if existing:
                    continue
                
                # Create database record
                record = PriceHistoryDaily(
                    ticker=ticker,
                    date=date_dt,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    adj_close=float(row.get('adjusted_close', row.get('adj_close', row['close']))),
                    volume=int(row['volume'])
                )
                
                db.add(record)
                total_rows += 1
            
            print(f"Loaded {len(df)} rows for {ticker} from {csv_file.name}")
            
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")
            continue
    
    db.commit()
    print(f"Total historical daily rows loaded: {total_rows}")
    return total_rows


def load_live_minute_data(db: Session, data_dir: str = "data") -> int:
    """
    Load live minute-level OHLCV data from CSV files into price_history_minute table.
    
    Expected format: simulation_price_data_July_1-Aug_30/*_live.csv
    Each CSV should have columns: timestamp, open, high, low, close, volume
    """
    live_dir = Path(data_dir) / "simulation_price_data_July_1-Aug_30"
    
    if not live_dir.exists():
        print(f"Warning: Live data directory not found: {live_dir}")
        return 0
    
    total_rows = 0
    
    for csv_file in live_dir.glob("*_live.csv"):
        # Extract ticker from filename (e.g., "AAPL_live.csv" -> "AAPL")
        ticker = csv_file.stem.replace("_live", "").upper()
        
        # Handle any additional prefixes like "simulated_"
        if ticker.startswith("SIMULATED_"):
            ticker = ticker.replace("SIMULATED_", "")
        
        # Skip unsupported tickers
        if ticker not in SUPPORTED_TICKERS:
            continue
        
        try:
            df = pd.read_csv(csv_file)
            
            # Ensure required columns exist
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                print(f"Warning: Skipping {csv_file} - missing required columns")
                continue
            
            # Process each row
            for _, row in df.iterrows():
                # Parse timestamp (explicitly set to UTC per principle 12)
                timestamp_str = row['timestamp']
                if isinstance(timestamp_str, str):
                    timestamp_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                else:
                    timestamp_dt = pd.to_datetime(timestamp_str).to_pydatetime()
                    if timestamp_dt.tzinfo is None:
                        timestamp_dt = timestamp_dt.replace(tzinfo=timezone.utc)
                
                # Check if record already exists
                existing = db.query(PriceHistoryMinute).filter(
                    PriceHistoryMinute.ticker == ticker,
                    PriceHistoryMinute.timestamp == timestamp_dt
                ).first()
                
                if existing:
                    continue
                
                # Create database record
                record = PriceHistoryMinute(
                    ticker=ticker,
                    timestamp=timestamp_dt,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume'])
                )
                
                db.add(record)
                total_rows += 1
            
            print(f"Loaded {len(df)} rows for {ticker} from {csv_file.name}")
            
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")
            continue
    
    db.commit()
    print(f"Total live minute rows loaded: {total_rows}")
    return total_rows


def load_news_articles(db: Session, data_dir: str = "data") -> int:
    """
    Load individual news headlines into news_articles.

    One row per (article, ticker) pair, which is the grain the source JSON scores at — a
    single story can mention several tickers with different relevance and sentiment.
    Complements load_news_sentiment_data, which only keeps the daily average.
    """
    import uuid

    news_dirs = [d for d in Path(data_dir).glob("simulation_news_data*") if d.is_dir()]
    if not news_dirs:
        print(f"Warning: No news data directories found in {data_dir}")
        return 0

    # Skip entirely if already seeded, so this is safe to re-run on every startup.
    if db.query(NewsArticle).count() > 0:
        print(f"News articles already loaded ({db.query(NewsArticle).count()} rows), skipping")
        return 0

    total = 0
    # The source JSON repeats some stories verbatim (same ticker, same publish time, same
    # title), so collapse those rather than letting the unique constraint abort the load.
    seen = set()
    for news_dir in news_dirs:
        for json_file in sorted(news_dir.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Error reading {json_file.name}: {e}")
                continue

            if not isinstance(data, dict):
                continue

            batch = []
            for date_key, articles in data.items():
                try:
                    date_dt = datetime.strptime(date_key, "%Y%m%d")
                except ValueError:
                    continue

                for article in articles or []:
                    title = (article.get("title") or "").strip()
                    if not title:
                        continue

                    # "20260701T062006" -> datetime; fall back to the trading date.
                    raw_time = article.get("time_published") or ""
                    try:
                        published_at = datetime.strptime(raw_time, "%Y%m%dT%H%M%S")
                    except ValueError:
                        published_at = date_dt

                    topics = ",".join(
                        t.get("topic", "") for t in (article.get("topics") or []) if t.get("topic")
                    ) or None

                    for ts in article.get("ticker_sentiment") or []:
                        ticker = ts.get("ticker")
                        if ticker not in SUPPORTED_TICKERS:
                            continue
                        try:
                            relevance = float(ts.get("relevance_score", 0) or 0)
                            sentiment = float(ts.get("ticker_sentiment_score", 0) or 0)
                        except (TypeError, ValueError):
                            continue

                        key = (ticker, published_at, title)
                        if key in seen:
                            continue
                        seen.add(key)

                        batch.append(NewsArticle(
                            id=str(uuid.uuid4()),
                            ticker=ticker,
                            date=date_dt,
                            published_at=published_at,
                            title=title,
                            relevance_score=relevance,
                            sentiment_score=sentiment,
                            sentiment_label=ts.get("ticker_sentiment_label") or "Neutral",
                            topics=topics,
                        ))

            if batch:
                db.bulk_save_objects(batch)
                db.commit()
                total += len(batch)
                print(f"  {json_file.name}: {len(batch)} ticker-relevant headlines")

    print(f"Total news articles loaded: {total}")
    return total


def load_news_sentiment_data(db: Session, data_dir: str = "data") -> int:
    """
    Load news sentiment data from JSON files into news_sentiment_daily table.
    
    Expected format: simulation_news_data_.../*.json
    JSON structure should contain per-ticker daily sentiment scores
    Filters to only the 7 supported tickers per Section 2
    """
    news_dir = Path(data_dir)
    
    # Find news directories (they might have different names)
    news_dirs = [d for d in Path(data_dir).glob("simulation_news_data*") if d.is_dir()]
    
    if not news_dirs:
        print(f"Warning: No news data directories found in {data_dir}")
        return 0
    
    total_rows = 0
    
    for news_dir in news_dirs:
        for json_file in news_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Process the JSON data
                # Expected structure: dict with date keys (e.g., "20260701")
                # each containing an array of news articles with ticker_sentiment
                if not isinstance(data, dict):
                    continue
                
                # Aggregate sentiment by ticker and date
                ticker_date_sentiment = {}  # {(ticker, date): [sentiments]}
                
                for date_key, articles in data.items():
                    try:
                        # Parse date from key (e.g., "20260701" -> "2026-07-01")
                        date_dt = datetime.strptime(date_key, "%Y%m%d").replace(tzinfo=timezone.utc)
                        date_str = date_dt.strftime("%Y-%m-%d")
                        
                        if not isinstance(articles, list):
                            continue
                        
                        for article in articles:
                            if not isinstance(article, dict):
                                continue
                            
                            ticker_sentiments = article.get('ticker_sentiment', [])
                            if not isinstance(ticker_sentiments, list):
                                continue
                            
                            for ticker_info in ticker_sentiments:
                                if not isinstance(ticker_info, dict):
                                    continue
                                
                                ticker = ticker_info.get('ticker', '').upper()
                                if ticker not in SUPPORTED_TICKERS:
                                    continue
                                
                                # Calculate weighted sentiment based on relevance
                                relevance = float(ticker_info.get('relevance_score', 0))
                                sentiment = float(ticker_info.get('ticker_sentiment_score', 0))
                                
                                # Skip if relevance is too low
                                if relevance < 0.1:
                                    continue
                                
                                key = (ticker, date_str)
                                if key not in ticker_date_sentiment:
                                    ticker_date_sentiment[key] = []
                                
                                ticker_date_sentiment[key].append({
                                    'sentiment': sentiment,
                                    'relevance': relevance
                                })
                                
                    except Exception as e:
                        print(f"Error processing date {date_key}: {e}")
                        continue
                
                # Calculate average sentiment per ticker per date
                for (ticker, date_str), sentiments in ticker_date_sentiment.items():
                    try:
                        # Calculate weighted average sentiment
                        total_weight = sum(s['relevance'] for s in sentiments)
                        weighted_sum = sum(s['sentiment'] * s['relevance'] for s in sentiments)
                        avg_sentiment = weighted_sum / total_weight if total_weight > 0 else 0
                        headline_count = len(sentiments)
                        
                        # Parse date (explicitly set to UTC per principle 12)
                        date_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        
                        # Check if record already exists
                        existing = db.query(NewsSentimentDaily).filter(
                            NewsSentimentDaily.ticker == ticker,
                            NewsSentimentDaily.date == date_dt
                        ).first()
                        
                        if existing:
                            continue
                        
                        # Create database record
                        record = NewsSentimentDaily(
                            ticker=ticker,
                            date=date_dt,
                            avg_sentiment=avg_sentiment,
                            headline_count=headline_count
                        )
                        
                        db.add(record)
                        total_rows += 1
                        
                    except Exception as e:
                        print(f"Error creating sentiment record for {ticker} {date_str}: {e}")
                        continue
                
                print(f"Processed {len(ticker_date_sentiment)} ticker-date pairs from {json_file.name}")
                
            except Exception as e:
                print(f"Error loading {json_file}: {e}")
                continue
    
    db.commit()
    print(f"Total news sentiment rows loaded: {total_rows}")
    return total_rows


def load_all_data(db: Session, data_dir: str = "data") -> dict:
    """
    Load all data sources (historical daily, live minute, news sentiment).
    
    Returns a dictionary with row counts for each data source.
    """
    print("Starting data ingestion...")
    
    results = {
        "historical_daily": load_historical_daily_data(db, data_dir),
        "live_minute": load_live_minute_data(db, data_dir),
        "news_sentiment": load_news_sentiment_data(db, data_dir),
        "news_articles": load_news_articles(db, data_dir),
    }
    
    print("Data ingestion complete.")
    print(f"Results: {results}")
    
    return results


def verify_data_counts(db: Session) -> dict:
    """
    Verify the row counts in the database match expected values.
    
    Expected per Section 2:
    - Historical daily: 7 tickers × 130 rows = 910 rows
    - Live minute: 7 tickers × ~17,000 rows = ~119,000 rows
    - News sentiment: Variable, but should only contain the 7 supported tickers
    """
    results = {
        "price_history_daily": db.query(PriceHistoryDaily).count(),
        "price_history_minute": db.query(PriceHistoryMinute).count(),
        "news_sentiment_daily": db.query(NewsSentimentDaily).count()
    }
    
    # Check per-ticker counts for historical data
    historical_by_ticker = {}
    for ticker in SUPPORTED_TICKERS:
        count = db.query(PriceHistoryDaily).filter(
            PriceHistoryDaily.ticker == ticker
        ).count()
        historical_by_ticker[ticker] = count
    
    results["historical_by_ticker"] = historical_by_ticker
    
    print("Data verification results:")
    print(f"  Historical daily total: {results['price_history_daily']} (expected: ~910)")
    print(f"  Live minute total: {results['price_history_minute']} (expected: ~119,000)")
    print(f"  News sentiment total: {results['news_sentiment_daily']}")
    print(f"  Historical by ticker: {historical_by_ticker}")
    
    return results