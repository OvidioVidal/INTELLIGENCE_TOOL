#!/usr/bin/env python3
import smtplib
import argparse
import sys
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import List, Optional, Dict
import re


class EmailSender:
    # Relevant sectors to keep in the email
    RELEVANT_SECTORS = {
        "automotive",
        "computer software",
        "consumer: foods",
        "consumer: other",
        "consumer: retail",
        "defense",
        "financial services",
        "industrial automation",
        "industrial products and services",
        "industrial: electronics",
        "services (other)"
    }

    def __init__(self, email_file: str = "composed_email.txt", config_file: str = "email_config.json"):
        """Initialize with the composed email file and config."""
        self.email_file = Path(email_file)
        self.config_file = Path(config_file)
        self.email_content = self._load_email()
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load email configuration from JSON file."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return default config if file doesn't exist
            return {
                "recipients": [],
                "smtp": {
                    "server": "smtp.gmail.com",
                    "port": 587,
                    "username": "",
                    "password": "",
                    "from_address": "",
                    "use_tls": True
                }
            }
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {self.config_file}: {e}")
            return {
                "recipients": [],
                "smtp": {
                    "server": "smtp.gmail.com",
                    "port": 587,
                    "username": "",
                    "password": "",
                    "from_address": "",
                    "use_tls": True
                }
            }

    def save_config(self, config: Dict) -> bool:
        """Save email configuration to JSON file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def _load_email(self) -> str:
        """Load the composed email content."""
        try:
            with open(self.email_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: {self.email_file} not found.")
            sys.exit(1)

    def filter_by_relevant_sectors(self, content: str) -> str:
        """Filter email content to only include relevant sectors."""
        lines = content.split('\n')
        filtered_lines = []
        current_sector = None
        skip_section = False
        in_detailed_section = False

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if we're entering the detailed section
            if "DETAILED PRESS RELEASES" in line:
                in_detailed_section = True
                filtered_lines.append(line)
                i += 1
                continue

            # In detailed section, identify sector headers (lines with emoji and uppercase)
            if in_detailed_section and line.strip() and not line.startswith(' ') and not line.startswith('•'):
                # Check if this is a sector header (contains emoji and uppercase text)
                sector_match = re.match(r'^[^\w\s]+\s+([A-Z\s:()]+)$', line)
                if sector_match:
                    sector_name = sector_match.group(1).strip().lower()

                    # Check if this sector is relevant
                    skip_section = not any(rel_sector in sector_name or sector_name in rel_sector
                                         for rel_sector in self.RELEVANT_SECTORS)

                    if not skip_section:
                        filtered_lines.append(line)

                    i += 1
                    continue

            # If not skipping, add the line
            if not skip_section:
                filtered_lines.append(line)

            i += 1

        # Rebuild the email and recalculate statistics
        filtered_content = '\n'.join(filtered_lines)

        # Remove sectors from summary and statistics sections
        filtered_content = self._filter_summary_and_stats(filtered_content)

        return filtered_content

    def _filter_summary_and_stats(self, content: str) -> str:
        """Filter summary and statistics sections to only show relevant sectors."""
        lines = content.split('\n')
        filtered_lines = []
        in_stats_breakdown = False
        in_summary_section = False

        for line in lines:
            # Check for statistics breakdown section
            if "Breakdown by Sector:" in line:
                in_stats_breakdown = True
                filtered_lines.append(line)
                continue

            # Check for summary section
            if "NEWS SUMMARY" in line:
                in_summary_section = True
                filtered_lines.append(line)
                continue

            # Exit stats breakdown when we hit empty line after breakdown
            if in_stats_breakdown and line.strip() == "":
                in_stats_breakdown = False
                filtered_lines.append(line)
                continue

            # Exit summary section when we hit detailed section
            if in_summary_section and "DETAILED PRESS RELEASES" in line:
                in_summary_section = False
                filtered_lines.append(line)
                continue

            # Filter lines in stats breakdown
            if in_stats_breakdown:
                # Check if line contains a sector
                sector_match = re.search(r'[^\w\s]+\s+([^:]+):', line)
                if sector_match:
                    sector_name = sector_match.group(1).strip().lower()
                    # Only include if relevant
                    if any(rel_sector in sector_name or sector_name in rel_sector
                          for rel_sector in self.RELEVANT_SECTORS):
                        filtered_lines.append(line)
                else:
                    filtered_lines.append(line)
                continue

            # Filter lines in summary section
            if in_summary_section:
                # Check if line contains a sector
                sector_match = re.search(r'[^\w\s]+\s+([^(]+)\s+\(', line)
                if sector_match:
                    sector_name = sector_match.group(1).strip().lower()
                    # Only include if relevant
                    if any(rel_sector in sector_name or sector_name in rel_sector
                          for rel_sector in self.RELEVANT_SECTORS):
                        filtered_lines.append(line)
                else:
                    filtered_lines.append(line)
                continue

            # Otherwise, keep the line
            filtered_lines.append(line)

        return '\n'.join(filtered_lines)

    def extract_subject(self, content: str) -> str:
        """Extract subject line from email content."""
        lines = content.split('\n')
        for line in lines:
            if line.startswith('Subject:'):
                return line.replace('Subject:', '').strip()
        return "News Alert"

    def send_email(self,
                   to_addresses: Optional[List[str]] = None,
                   from_address: Optional[str] = None,
                   smtp_server: Optional[str] = None,
                   smtp_port: Optional[int] = None,
                   username: Optional[str] = None,
                   password: Optional[str] = None,
                   filter_sectors: bool = True,
                   use_tls: Optional[bool] = None):
        """Send the email via SMTP. Uses config file if parameters not provided."""

        # Use config values if parameters not provided
        if to_addresses is None:
            to_addresses = self.config.get('recipients', [])

        if not to_addresses:
            print("✗ Error: No recipients specified")
            return False

        smtp_config = self.config.get('smtp', {})

        if from_address is None:
            from_address = smtp_config.get('from_address', '')

        if smtp_server is None:
            smtp_server = smtp_config.get('server', 'smtp.gmail.com')

        if smtp_port is None:
            smtp_port = smtp_config.get('port', 587)

        if username is None:
            username = smtp_config.get('username', '')

        if password is None:
            password = smtp_config.get('password', '')

        if use_tls is None:
            use_tls = smtp_config.get('use_tls', True)

        # Filter content if requested
        content = self.filter_by_relevant_sectors(self.email_content) if filter_sectors else self.email_content

        # Extract subject
        subject = self.extract_subject(content)

        # Create message
        msg = MIMEMultipart()
        msg['From'] = from_address
        msg['To'] = ', '.join(to_addresses)
        msg['Subject'] = subject

        # Attach body
        msg.attach(MIMEText(content, 'plain', 'utf-8'))

        try:
            # Connect to SMTP server
            if use_tls:
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)

            # Login if credentials provided
            if username and password:
                server.login(username, password)

            # Send email
            server.send_message(msg)
            server.quit()

            print(f"✓ Email sent successfully to {', '.join(to_addresses)}")
            return True

        except Exception as e:
            print(f"✗ Error sending email: {e}")
            return False

    def send_from_config(self, filter_sectors: bool = True):
        """Send email using all settings from config file."""
        return self.send_email(filter_sectors=filter_sectors)


def main():
    parser = argparse.ArgumentParser(
        description="Send filtered composed email via SMTP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use config file (email_config.json)
  python send_email.py --use-config

  # Override config with command line arguments
  python send_email.py --to recipient@example.com --from sender@example.com --server smtp.gmail.com --username user --password pass
  python send_email.py --to recipient@example.com --from sender@example.com --server smtp.gmail.com --no-filter
  python send_email.py --to recipient1@example.com recipient2@example.com --from sender@example.com --server smtp.gmail.com
        """
    )

    parser.add_argument('--email-file', default='composed_email.txt',
                       help='Path to the composed email file (default: composed_email.txt)')
    parser.add_argument('--config-file', default='email_config.json',
                       help='Path to email config file (default: email_config.json)')
    parser.add_argument('--use-config', action='store_true',
                       help='Use all settings from config file')
    parser.add_argument('--to', nargs='+',
                       help='Recipient email address(es) (overrides config)')
    parser.add_argument('--from', dest='from_address',
                       help='Sender email address (overrides config)')
    parser.add_argument('--server',
                       help='SMTP server address (e.g., smtp.gmail.com) (overrides config)')
    parser.add_argument('--port', type=int,
                       help='SMTP server port (overrides config)')
    parser.add_argument('--username',
                       help='SMTP username (overrides config)')
    parser.add_argument('--password',
                       help='SMTP password (overrides config)')
    parser.add_argument('--no-filter', action='store_true',
                       help='Do not filter by relevant sectors')
    parser.add_argument('--no-tls', action='store_true',
                       help='Use SSL instead of TLS')

    args = parser.parse_args()

    # Create sender instance
    sender = EmailSender(args.email_file, args.config_file)

    # Determine use_tls
    use_tls = None if not args.no_tls else False

    # Send email
    if args.use_config:
        # Use all config values
        success = sender.send_from_config(filter_sectors=not args.no_filter)
    else:
        # Allow command line arguments to override config
        success = sender.send_email(
            to_addresses=args.to,
            from_address=args.from_address,
            smtp_server=args.server,
            smtp_port=args.port,
            username=args.username,
            password=args.password,
            filter_sectors=not args.no_filter,
            use_tls=use_tls
        )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
