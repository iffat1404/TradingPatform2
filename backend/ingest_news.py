#!/usr/bin/env python3
"""
Ingest news data from JSON files into the news_items database table.

Usage:
    python ingest_news.py

The script reads news data from simulation_news_data_July_1-Aug_30 folder
and upserts them into the news_items table with proper sentiment mapping.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.core.db import engine, Base
from app.models.orm import NewsItem


def parse_timestamp(time_str: str) -> datetime:
    """Parse timestamp string in format '20260701T062006' to datetime."""
    try:
        dt = datetime.strptime(time_str, "%Y%m%dT%H%M%S")
        # Set timezone to UTC
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        print(f"Warning: Could not parse timestamp {time_str}")
        return datetime.now(timezone.utc)


def map_sentiment_score(score: float) -> str:
    """Map sentiment score to label."""
    if score < -0.1:
        return "Bearish"
    elif score > 0.1:
        return "Bullish"
    else:
        return "Neutral"


def ingest_news_file(db_session, file_path: Path):
    """Ingest a single news JSON file into the database."""
    print(f"Reading file: {file_path}")

    with open(file_path, "r") as f:
        data = json.load(f)

    total_items = 0
    inserted_items = 0
    skipped_items = 0

    # Data structure: { "20260701": [ { news items } ], ... }
    for date_str, news_list in data.items():
        for news_item in news_list:
            total_items += 1

            try:
                title = news_item.get("title", "No Title")
                time_published = parse_timestamp(news_item.get("time_published", ""))
                topics = news_item.get("topics", [])
                ticker_sentiments = news_item.get("ticker_sentiment", [])

                # Get primary topic
                primary_topic = topics[0]["topic"] if topics else None

                # Process each ticker sentiment
                for ticker_sentiment in ticker_sentiments:
                    ticker = ticker_sentiment.get("ticker")
                    sentiment_score = float(ticker_sentiment.get("ticker_sentiment_score", 0))
                    sentiment_label = ticker_sentiment.get("ticker_sentiment_label", "Neutral")
                    relevance_score = float(ticker_sentiment.get("relevance_score", 0))

                    # Check if this news item already exists
                    existing = (
                        db_session.query(NewsItem)
                        .filter(
                            NewsItem.title == title,
                            NewsItem.ticker == ticker,
                            NewsItem.published_at == time_published,
                        )
                        .first()
                    )

                    if existing:
                        skipped_items += 1
                        continue

                    # Create new news item
                    news_obj = NewsItem(
                        title=title,
                        content=None,  # Not provided in the JSON
                        source="Alpha Vantage Simulation",
                        published_at=time_published,
                        ticker=ticker,
                        sentiment_score=sentiment_score,
                        sentiment_label=sentiment_label,
                        relevance_score=relevance_score,
                        primary_topic=primary_topic,
                    )

                    db_session.add(news_obj)
                    inserted_items += 1

                    if inserted_items % 100 == 0:
                        print(f"  Processed {inserted_items} items...")

            except Exception as e:
                print(f"Error processing item: {e}")
                continue

    print(
        f"File processing complete: {inserted_items} inserted, {skipped_items} skipped (out of {total_items} total)"
    )
    return inserted_items, skipped_items


def main():
    """Main ingestion function."""
    print("=" * 60)
    print("News Data Ingestion Script")
    print("=" * 60)

    # Create tables if they don't exist
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    # Create session
    Session = sessionmaker(bind=engine)
    db_session = Session()

    try:
        # Find news data files
        data_dir = Path(__file__).parent.parent / "simulation_news_data_July_1-Aug_30"

        if not data_dir.exists():
            print(f"Error: News data directory not found: {data_dir}")
            sys.exit(1)

        # Get all JSON files
        json_files = sorted(data_dir.glob("*.json"))
        print(f"Found {len(json_files)} JSON files to ingest\n")

        total_inserted = 0
        total_skipped = 0

        for json_file in json_files:
            inserted, skipped = ingest_news_file(db_session, json_file)
            total_inserted += inserted
            total_skipped += skipped

        # Commit all changes
        print("\nCommitting changes to database...")
        db_session.commit()

        print("\n" + "=" * 60)
        print("Ingestion Complete!")
        print(f"Total inserted: {total_inserted}")
        print(f"Total skipped (duplicates): {total_skipped}")
        print("=" * 60)

    except Exception as e:
        print(f"Fatal error: {e}")
        db_session.rollback()
        sys.exit(1)
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
