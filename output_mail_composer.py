#!/usr/bin/env python3
import json
import argparse
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class EmailComposer:
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

    def __init__(self, data_file: str = "grouped.json"):
        """Initialize with the parsed data file."""
        self.data_file = Path(data_file)
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """Load the parsed JSON data."""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: {self.data_file} not found.")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {self.data_file}: {e}")
            sys.exit(1)

    def filter_sectors(self, include_sectors: Optional[List[str]] = None,
                      exclude_sectors: Optional[List[str]] = None,
                      use_relevant_only: bool = True) -> Dict[str, Any]:
        """Filter data by including or excluding specific sectors."""
        filtered_data = {}

        # Get metadata if it exists
        if "_email_metadata" in self.data:
            filtered_data["_email_metadata"] = self.data["_email_metadata"]

        # Process each sector
        for sector, items in self.data.items():
            if sector == "_email_metadata":
                continue

            include_sector = True

            # First, apply relevant sectors filter if enabled
            if use_relevant_only:
                include_sector = any(rel_sector in sector.lower() or sector.lower() in rel_sector
                                   for rel_sector in self.RELEVANT_SECTORS)

            # Check include filter (if specified, only include these sectors)
            if include_sectors and include_sector:
                include_sector = any(inc.lower() == sector.lower() for inc in include_sectors)

            # Check exclude filter (if specified, exclude these sectors)
            if exclude_sectors and include_sector:
                include_sector = not any(exc.lower() in sector.lower() for exc in exclude_sectors)

            if include_sector:
                filtered_data[sector] = items

        return filtered_data

    def get_sector_emoji(self, sector: str) -> str:
        """Get appropriate emoji for each sector."""
        emoji_map = {
            "automotive": "🚗",
            "computer software": "💻",
            "consumer: foods": "🍕",
            "consumer: other": "🛍️",
            "consumer: retail": "🏪",
            "defense": "🛡️",
            "financial services": "💰",
            "industrial automation": "🤖",
            "industrial products and services": "🏭",
            "industrial: electronics": "⚡",
            "services (other)": "🔧",
            "energy": "⚡",
            "telecommunications: carriers": "📡",
            "real estate": "🏢",
            "media": "📺",
            "transportation": "🚚",
            "construction": "🏗️",
            "chemicals and materials": "⚗️",
            "internet / ecommerce": "🌐",
            "leisure": "🎯"
        }
        return emoji_map.get(sector.lower(), "📋")

    def extract_deal_value(self, metadata: Dict[str, Any]) -> float:
        """Extract deal value from metadata, return 0 if not found or not parseable."""
        value_str = metadata.get('Value', '') or metadata.get('Size', '')
        if not value_str or value_str == '-':
            return 0

        # Clean the string and extract numbers
        # Look for patterns like "100m", "1.5bn", "500", etc.
        value_str = value_str.lower().replace(',', '').replace(' ', '')

        # Extract number and multiplier
        match = re.search(r'(\d+(?:\.\d+)?)\s*(m|bn|million|billion)?', value_str)
        if match:
            number = float(match.group(1))
            multiplier = match.group(2)

            if multiplier in ['bn', 'billion']:
                return number * 1000  # Convert to millions
            elif multiplier in ['m', 'million']:
                return number
            else:
                # Assume it's already in millions if no multiplier
                return number
        return 0

    def calculate_deal_statistics(self, filtered_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate deal statistics for the filtered data."""
        stats = {
            'deals_by_sector': {},
            'total_deals': 0,
            'total_volume': 0,
            'deals_with_value': 0
        }

        for sector, items in filtered_data.items():
            if sector == "_email_metadata":
                continue

            sector_deals = len(items)
            sector_volume = 0
            sector_deals_with_value = 0

            for item in items:
                metadata = item.get('details', {}).get('metadata', {})
                deal_value = self.extract_deal_value(metadata)
                if deal_value > 0:
                    sector_volume += deal_value
                    sector_deals_with_value += 1

            stats['deals_by_sector'][sector] = {
                'count': sector_deals,
                'volume': sector_volume,
                'deals_with_value': sector_deals_with_value
            }

            stats['total_deals'] += sector_deals
            stats['total_volume'] += sector_volume
            stats['deals_with_value'] += sector_deals_with_value

        return stats

    def create_deal_statistics_section(self, stats: Dict[str, Any]) -> str:
        """Create the deal statistics section for the top of the email."""
        lines = []
        lines.append("DEALS BY SECTOR")
        lines.append("=" * 50)
        lines.append("")

        # Overall statistics
        avg_volume = stats['total_volume'] / stats['deals_with_value'] if stats['deals_with_value'] > 0 else 0
        lines.append(f"Total Deals: {stats['total_deals']}")
        lines.append(f"Total Deal Volume: {stats['total_volume']:.1f}M")
        lines.append(f"Average Deal Volume: {avg_volume:.1f}M (based on {stats['deals_with_value']} deals with disclosed values)")
        lines.append("")

        # By sector
        lines.append("Breakdown by Sector:")
        for sector, sector_stats in stats['deals_by_sector'].items():
            emoji = self.get_sector_emoji(sector)
            avg_sector = sector_stats['volume'] / sector_stats['deals_with_value'] if sector_stats['deals_with_value'] > 0 else 0
            lines.append(f"{emoji} {sector}: {sector_stats['count']} deals, {sector_stats['volume']:.1f}M volume, {avg_sector:.1f}M avg")

        lines.append("")
        return "\n".join(lines)

    def create_email_summary(self, filtered_data: Dict[str, Any]) -> str:
        """Create email summary with all titles grouped by sector."""
        summary_lines = []
        summary_lines.append("NEWS SUMMARY")
        summary_lines.append("=" * 50)
        summary_lines.append("")

        total_items = 0
        for sector, items in filtered_data.items():
            if sector == "_email_metadata":
                continue

            if items:
                emoji = self.get_sector_emoji(sector)
                summary_lines.append(f"{emoji} {sector} ({len(items)} items)")
                for item in items:
                    # Keep the original title with its number
                    summary_lines.append(f"  {item['title']}")
                summary_lines.append("")
                total_items += len(items)

        summary_lines.insert(2, f"Total: {total_items} news items across {len([k for k in filtered_data.keys() if k != '_email_metadata'])} sectors")
        summary_lines.insert(3, "")

        return "\n".join(summary_lines)

    def create_detailed_section(self, filtered_data: Dict[str, Any]) -> str:
        """Create detailed section with full press releases, metadata and links."""
        detailed_lines = []
        detailed_lines.append("DETAILED PRESS RELEASES")
        detailed_lines.append("=" * 50)
        detailed_lines.append("")

        for sector, items in filtered_data.items():
            if sector == "_email_metadata":
                continue

            if items:
                emoji = self.get_sector_emoji(sector)
                detailed_lines.append(f"{emoji} {sector.upper()}")
                detailed_lines.append("")

                for item in items:
                    # Title
                    detailed_lines.append(f"{item['title']}")
                    detailed_lines.append("")

                    details = item.get('details', {})

                    # Bullets/highlights
                    if details.get('bullets'):
                        detailed_lines.append("Key Points:")
                        for bullet in details['bullets']:
                            detailed_lines.append(f"• {bullet}")
                        detailed_lines.append("")

                    # Main body
                    if details.get('body'):
                        detailed_lines.append("Details:")
                        detailed_lines.append(details['body'])
                        detailed_lines.append("")

                    # Metadata
                    if details.get('metadata'):
                        meta = details['metadata']
                        detailed_lines.append("Metadata:")

                        # Key financial info
                        key_fields = ['Size', 'Value', 'Stake Value', 'Grade', 'Source']
                        for field in key_fields:
                            if field in meta and meta[field] and meta[field] != "":
                                detailed_lines.append(f"• {field}: {meta[field]}")

                        # Intelligence ID if available
                        if meta.get('Intelligence ID'):
                            detailed_lines.append(f"• ID: {meta['Intelligence ID']}")

                        detailed_lines.append("")

                    # Links
                    meta = details.get('metadata', {})
                    links_found = []

                    # Direct links
                    if details.get('links'):
                        links_found.extend(details['links'])

                    # Extract links from metadata (including split URLs)
                    for key, value in meta.items():
                        if isinstance(value, str):
                            # Handle the specific case where URL is split
                            if key.endswith('( https') and value.startswith('//'):
                                full_url = 'https:' + value
                                clean_key = key.replace(' ( https', '')
                                links_found.append(f"{clean_key}: {full_url}")
                            elif 'http' in value:
                                links_found.append(f"{key}: {value}")
                            elif 'http' in key:
                                links_found.append(f"{key}: {value}")

                    if links_found:
                        detailed_lines.append("Links:")
                        for link in links_found:
                            detailed_lines.append(f"• {link}")
                        detailed_lines.append("")

                    detailed_lines.append("---")
                    detailed_lines.append("")

                detailed_lines.append("=" * 50)
                detailed_lines.append("")

        return "\n".join(detailed_lines)

    def compose_email(self, include_sectors: Optional[List[str]] = None,
                     exclude_sectors: Optional[List[str]] = None) -> str:
        """Compose the complete email."""
        # Filter data
        filtered_data = self.filter_sectors(include_sectors, exclude_sectors)

        if not any(k != "_email_metadata" for k in filtered_data.keys()):
            return "No news items found with the specified filters."

        email_lines = []

        # Email header
        metadata = filtered_data.get("_email_metadata", {})
        if metadata:
            email_lines.append(f"Subject: {metadata.get('subject', 'News Alert')}")
            email_lines.append(f"Date: {metadata.get('timestamp', datetime.now().strftime('%d/%m/%Y %H:%M:%S'))}")
            email_lines.append("")

        # Deal statistics section
        stats = self.calculate_deal_statistics(filtered_data)
        email_lines.append(self.create_deal_statistics_section(stats))

        # Summary section
        email_lines.append(self.create_email_summary(filtered_data))
        email_lines.append("")

        # Detailed section
        email_lines.append(self.create_detailed_section(filtered_data))

        return "\n".join(email_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Compose structured emails from news data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python output_mail_composer.py                                    # Create email with all sectors (saves to composed_email.txt)
  python output_mail_composer.py --include "Energy" "Financial"     # Only include specific sectors
  python output_mail_composer.py --exclude "Gaming" "Sports"        # Exclude specific sectors
  python output_mail_composer.py --include "Tech" --output tech_news.txt  # Save to custom file
        """
    )

    parser.add_argument('--data-file', default='grouped.json',
                        help='Path to the parsed data file (default: grouped.json)')
    parser.add_argument('--include', nargs='+', metavar='SECTOR',
                        help='Include only these sectors (case-insensitive, supports partial matching)')
    parser.add_argument('--exclude', nargs='+', metavar='SECTOR',
                        help='Exclude these sectors (case-insensitive, supports partial matching)')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Output file (default: composed_email.txt)')

    args = parser.parse_args()

    # Create composer instance
    composer = EmailComposer(args.data_file)

    # Compose email
    email_content = composer.compose_email(
        include_sectors=args.include,
        exclude_sectors=args.exclude
    )

    # Output email to file
    output_file = args.output if args.output else 'composed_email.txt'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(email_content)
    print(f"Email saved to {output_file}")


if __name__ == "__main__":
    main()