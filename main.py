#!/usr/bin/env python3
"""
Intelligence Tool Pipeline Orchestrator
Runs AUTO_INPUT.py continuously in the background and triggers the pipeline
when input_email.txt is updated:
1. Parse email to JSON
2. Import JSON to database
3. Compose output email
"""

import sys
import os
import time
import subprocess
from pathlib import Path

INPUT_FILE = "input_email.txt"
CHECK_INTERVAL = 2  # seconds between file checks

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
        return False

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
        return False

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
        return False

    print()
    print("=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print()
    print("Output files generated:")
    print("  • grouped.json - Parsed intelligence data")
    print("  • intelligence.db - SQLite database")
    print("  • composed_email.txt - Formatted output email")
    print()

    return True


def watch_and_process():
    """
    Start AUTO_INPUT.py in background and watch for changes to input_email.txt.
    When the file is modified, trigger the pipeline.
    """

    print("=" * 60)
    print("INTELLIGENCE TOOL - CONTINUOUS MODE")
    print("=" * 60)
    print()

    # Start AUTO_INPUT.py as background process
    print("Starting AUTO_INPUT.py in background...")
    try:
        auto_input_process = subprocess.Popen(
            [sys.executable, "AUTO_INPUT.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"[✓] AUTO_INPUT.py started (PID: {auto_input_process.pid})")
    except Exception as e:
        print(f"[✗] Failed to start AUTO_INPUT.py: {e}")
        sys.exit(1)

    print(f"[✓] Watching {INPUT_FILE} for changes...")
    print(f"    (checking every {CHECK_INTERVAL} seconds)")
    print()

    # Track last modification time
    last_mtime = None
    if os.path.exists(INPUT_FILE):
        last_mtime = os.path.getmtime(INPUT_FILE)

    try:
        while True:
            # Check if AUTO_INPUT.py is still running
            if auto_input_process.poll() is not None:
                print("[!] AUTO_INPUT.py process terminated unexpectedly")
                print("    Restarting AUTO_INPUT.py...")
                auto_input_process = subprocess.Popen(
                    [sys.executable, "AUTO_INPUT.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                print(f"[✓] AUTO_INPUT.py restarted (PID: {auto_input_process.pid})")

            # Check if input file has been modified
            if os.path.exists(INPUT_FILE):
                current_mtime = os.path.getmtime(INPUT_FILE)

                if last_mtime is None or current_mtime > last_mtime:
                    print(f"[•] Detected change in {INPUT_FILE}")
                    print(f"    Triggering pipeline...\n")

                    success = run_pipeline()

                    if success:
                        print("[✓] Waiting for next email...\n")
                    else:
                        print("[!] Pipeline failed, but continuing to watch for changes...\n")

                    last_mtime = current_mtime

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n[•] Shutting down...")
        auto_input_process.terminate()
        auto_input_process.wait(timeout=5)
        print("[✓] Cleanup complete. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    watch_and_process()
