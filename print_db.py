import sqlite3

def print_db():
    conn = sqlite3.connect('intelligence.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get email info
    cursor.execute("SELECT * FROM emails ORDER BY parsed_date DESC")
    emails = cursor.fetchall()

    print(f"Total Emails: {len(emails)}\n")

    for email in emails:
        print("=" * 80)
        print(f"Subject: {email['subject']}")
        print(f"Date: {email['parsed_date']}")
        print("=" * 80)

        # Get all deals for this email
        cursor.execute("""
            SELECT d.id, c.name as category, d.title, d.body, d.intelligence_id,
                   d.source, d.value, d.stake_value, d.grade, d.alert_type
            FROM deals d
            JOIN categories c ON d.category_id = c.id
            WHERE d.email_id = ?
            ORDER BY c.name, d.id
        """, (email['id'],))

        deals = cursor.fetchall()

        if not deals:
            print("No deals found\n")
            continue

        current_category = None
        for deal in deals:
            if deal['category'] != current_category:
                print(f"\n{deal['category']}")
                print("-" * 80)
                current_category = deal['category']

            print(f"\n  {deal['title']}")

            if deal['intelligence_id']:
                print(f"    ID: {deal['intelligence_id']}")
            if deal['value']:
                print(f"    Value: {deal['value']}")
            if deal['stake_value']:
                print(f"    Stake: {deal['stake_value']}")
            if deal['grade']:
                print(f"    Grade: {deal['grade']}")
            if deal['alert_type']:
                print(f"    Type: {deal['alert_type']}")
            if deal['source']:
                print(f"    Source: {deal['source']}")

            # Get bullets
            cursor.execute("SELECT bullet_text FROM deal_bullets WHERE deal_id = ?", (deal['id'],))
            bullets = cursor.fetchall()
            for bullet in bullets:
                print(f"      - {bullet['bullet_text']}")

            # Get links
            cursor.execute("SELECT link_url FROM deal_links WHERE deal_id = ?", (deal['id'],))
            links = cursor.fetchall()
            if links:
                print("    Links:")
                for link in links:
                    print(f"      {link['link_url']}")

            # Get metadata
            cursor.execute("SELECT key, value FROM deal_metadata WHERE deal_id = ?", (deal['id'],))
            metadata = cursor.fetchall()
            if metadata:
                print("    Metadata:")
                for meta in metadata:
                    print(f"      {meta['key']}: {meta['value']}")

        print("\n")

    conn.close()

if __name__ == "__main__":
    print_db()
