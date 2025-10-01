#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intelligence Database Importer
Imports M&A intelligence data from grouped.json into SQLite database.
Only new data is saved - duplicates are automatically skipped.
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Any

# Database file path
DB_FILE = 'intelligence.db'

def create_database():
    """Create database tables with proper constraints to prevent duplicates."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Email metadata table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            parsed_date TEXT NOT NULL,
            UNIQUE(subject, timestamp)
        )
    ''')

    # Categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    # Deals/Intelligence entries table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            intelligence_id TEXT UNIQUE,
            source TEXT,
            value TEXT,
            stake_value TEXT,
            grade TEXT,
            alert_type TEXT,
            FOREIGN KEY (email_id) REFERENCES emails(id),
            FOREIGN KEY (category_id) REFERENCES categories(id),
            UNIQUE(intelligence_id)
        )
    ''')

    # Bullets table (many-to-many relationship)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deal_bullets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id INTEGER NOT NULL,
            bullet_text TEXT NOT NULL,
            FOREIGN KEY (deal_id) REFERENCES deals(id),
            UNIQUE(deal_id, bullet_text)
        )
    ''')

    # Links table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deal_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id INTEGER NOT NULL,
            link_url TEXT NOT NULL,
            FOREIGN KEY (deal_id) REFERENCES deals(id),
            UNIQUE(deal_id, link_url)
        )
    ''')

    # Additional metadata table (flexible key-value pairs)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deal_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            FOREIGN KEY (deal_id) REFERENCES deals(id),
            UNIQUE(deal_id, key)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"[OK] Database schema ready: {DB_FILE}")


def insert_email(cursor, email_metadata: Dict) -> int:
    """Insert email metadata and return email_id. Skip if duplicate."""
    try:
        cursor.execute('''
            INSERT INTO emails (subject, timestamp, parsed_date)
            VALUES (?, ?, ?)
        ''', (
            email_metadata.get('subject', ''),
            email_metadata.get('timestamp', ''),
            email_metadata.get('parsed_date', '')
        ))
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Email already exists, fetch its ID
        cursor.execute('''
            SELECT id FROM emails WHERE subject = ? AND timestamp = ?
        ''', (email_metadata.get('subject', ''), email_metadata.get('timestamp', '')))
        result = cursor.fetchone()
        return result[0] if result else None


def insert_category(cursor, category_name: str) -> int:
    """Insert category and return category_id. Skip if duplicate."""
    try:
        cursor.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Category already exists, fetch its ID
        cursor.execute('SELECT id FROM categories WHERE name = ?', (category_name,))
        result = cursor.fetchone()
        return result[0] if result else None


def insert_deal(cursor, email_id: int, category_id: int, deal: Dict) -> int:
    """Insert deal and return deal_id. Skip if duplicate intelligence_id."""
    details = deal.get('details', {})
    metadata = details.get('metadata', {})

    intelligence_id = metadata.get('Intelligence ID', '')

    # Skip if intelligence_id already exists
    if intelligence_id:
        cursor.execute('SELECT id FROM deals WHERE intelligence_id = ?', (intelligence_id,))
        existing = cursor.fetchone()
        if existing:
            print(f"  [SKIP] Duplicate: {intelligence_id}")
            return None

    try:
        cursor.execute('''
            INSERT INTO deals (
                email_id, category_id, title, body, intelligence_id,
                source, value, stake_value, grade, alert_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            email_id,
            category_id,
            deal.get('title', ''),
            details.get('body', ''),
            intelligence_id,
            metadata.get('Source', ''),
            metadata.get('Value', ''),
            metadata.get('Stake Value', ''),
            metadata.get('Grade', ''),
            metadata.get('Alert', '')
        ))
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        print(f"  [SKIP] Duplicate intelligence_id: {intelligence_id}")
        return None


def insert_bullets(cursor, deal_id: int, bullets: List[str]):
    """Insert bullet points for a deal. Skip duplicates."""
    for bullet in bullets:
        try:
            cursor.execute('''
                INSERT INTO deal_bullets (deal_id, bullet_text)
                VALUES (?, ?)
            ''', (deal_id, bullet))
        except sqlite3.IntegrityError:
            pass  # Skip duplicate bullets


def insert_links(cursor, deal_id: int, links: List[str]):
    """Insert links for a deal. Skip duplicates."""
    for link in links:
        if link:  # Only insert non-empty links
            try:
                cursor.execute('''
                    INSERT INTO deal_links (deal_id, link_url)
                    VALUES (?, ?)
                ''', (deal_id, link))
            except sqlite3.IntegrityError:
                pass  # Skip duplicate links


def insert_metadata(cursor, deal_id: int, metadata: Dict):
    """Insert additional metadata key-value pairs. Skip duplicates."""
    # Skip standard fields already stored in deals table
    skip_keys = {'Intelligence ID', 'Source', 'Value', 'Stake Value', 'Grade', 'Alert', 'Size'}

    for key, value in metadata.items():
        if key not in skip_keys and value:
            try:
                cursor.execute('''
                    INSERT INTO deal_metadata (deal_id, key, value)
                    VALUES (?, ?, ?)
                ''', (deal_id, key, str(value)))
            except sqlite3.IntegrityError:
                pass  # Skip duplicate metadata


def import_json_to_db(json_file: str = 'grouped.json'):
    """Import grouped.json data into the database. Only new data is saved."""
    print(f"Reading {json_file}...")

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Insert email metadata
    email_metadata = data.get('_email_metadata', {})
    email_id = insert_email(cursor, email_metadata)

    if not email_id:
        print("Error: Could not insert or find email metadata")
        conn.close()
        return

    print(f"[OK] Email processed (ID: {email_id})")

    # Process each category
    total_deals = 0
    skipped_deals = 0

    for category_name, deals in data.items():
        if category_name == '_email_metadata':
            continue

        print(f"\nProcessing category: {category_name}")
        category_id = insert_category(cursor, category_name)

        if not category_id:
            print(f"  Warning: Could not process category {category_name}")
            continue

        # Process each deal in the category
        for deal in deals:
            deal_id = insert_deal(cursor, email_id, category_id, deal)

            if deal_id:
                # Insert related data
                details = deal.get('details', {})
                bullets = details.get('bullets', [])
                links = details.get('links', [])
                metadata = details.get('metadata', {})

                insert_bullets(cursor, deal_id, bullets)
                insert_links(cursor, deal_id, links)
                insert_metadata(cursor, deal_id, metadata)

                total_deals += 1
                print(f"  [NEW] {deal.get('title', 'Untitled')[:60]}")
            else:
                skipped_deals += 1

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Import complete!")
    print(f"New deals imported: {total_deals}")
    print(f"Duplicate deals skipped: {skipped_deals}")
    print(f"Database: {DB_FILE}")
    print(f"{'='*60}")


def main():
    """Main execution function."""
    print("Starting database import process...\n")

    # Create database schema
    create_database()

    # Import data from JSON
    import_json_to_db()


if __name__ == '__main__':
    main()
