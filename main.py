#!/usr/bin/env python3
"""
Intelligence Tool Pipeline Orchestrator
Runs the complete pipeline in sequence:
1. Parse email to JSON
2. Import JSON to database
3. Compose output email
"""

import sys
from pathlib import Path

def run_pipeline():
    """Execute the complete intelligence processing pipeline."""

    print("=" * 60)
    print("INTELLIGENCE TOOL PIPELINE")
    print("=" * 60)
    print()

    # Step 1: Parse email to JSON
    print("[STEP 1/3] Parsing email to JSON...")
    print("-" * 60)
    try:
        import Input_mail_to_json
        Input_mail_to_json.main()
        print("[✓] Step 1 completed successfully")
    except Exception as e:
        print(f"[✗] Step 1 failed: {e}")
        sys.exit(1)

    print()

    # Step 2: Import JSON to database
    print("[STEP 2/3] Importing JSON to database...")
    print("-" * 60)
    try:
        import json_to_db
        json_to_db.main()
        print("[✓] Step 2 completed successfully")
    except Exception as e:
        print(f"[✗] Step 2 failed: {e}")
        sys.exit(1)

    print()

    # Step 3: Compose output email
    print("[STEP 3/3] Composing output email...")
    print("-" * 60)
    try:
        import output_mail_composer
        composer = output_mail_composer.EmailComposer()
        email_content = composer.compose_email()

        output_file = 'composed_email.txt'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(email_content)
        print(f"Email saved to {output_file}")
        print("[✓] Step 3 completed successfully")
    except Exception as e:
        print(f"[✗] Step 3 failed: {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print()
    print("Output files generated:")
    print("  • grouped.json - Parsed intelligence data")
    print("  • intelligence.db - SQLite database")
    print("  • composed_email.txt - Formatted output email")


if __name__ == "__main__":
    run_pipeline()
