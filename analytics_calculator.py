#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analytics Calculator
Core engine for calculating M&A intelligence analytics from the database.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import re

# Try to import the PE classifier (optional)
try:
    from classifier import EnhancedPEFundClassifier
    CLASSIFIER_AVAILABLE = True
except ImportError as e:
    print(f"[INFO] PE Classifier not available: {e}")
    print("[INFO] Install dependencies: pip3 install fuzzywuzzy python-Levenshtein")
    CLASSIFIER_AVAILABLE = False

DB_FILE = 'intelligence.db'


class AnalyticsCalculator:
    """Calculate analytics metrics from the intelligence database."""

    def __init__(self, db_file: str = DB_FILE):
        """Initialize the calculator with database connection and PE classifier."""
        self.db_file = db_file
        # Initialize the trained PE fund classifier if available
        if CLASSIFIER_AVAILABLE:
            try:
                self.pe_classifier = EnhancedPEFundClassifier()
                print("[OK] PE Fund Classifier loaded successfully")
            except Exception as e:
                print(f"[WARNING] Could not load PE classifier: {e}")
                self.pe_classifier = None
        else:
            self.pe_classifier = None
            print("[INFO] Using basic pattern matching for PE firm extraction")

    def _get_connection(self):
        """Create a database connection."""
        return sqlite3.connect(self.db_file)

    def _parse_date_range(self, period: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse period string into start and end dates.

        Args:
            period: 'current_month', 'ytd', 'all', or 'YYYY-MM-DD,YYYY-MM-DD'

        Returns:
            Tuple of (start_date, end_date) in ISO format
        """
        today = datetime.now()

        if period == 'current_month':
            start_date = today.replace(day=1).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            return start_date, end_date

        elif period == 'ytd':
            start_date = today.replace(month=1, day=1).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            return start_date, end_date

        elif period == 'all':
            return None, None

        elif ',' in period:
            # Custom range: "YYYY-MM-DD,YYYY-MM-DD"
            start_date, end_date = period.split(',')
            return start_date.strip(), end_date.strip()

        else:
            return None, None

    def get_total_deals(self, period: str = 'all') -> int:
        """
        Get total number of deals for a given period.

        Args:
            period: 'current_month', 'ytd', 'all', or custom range

        Returns:
            Total deal count
        """
        start_date, end_date = self._parse_date_range(period)

        conn = self._get_connection()

        if start_date and end_date:
            query = """
                SELECT COUNT(*) as total
                FROM deals d
                JOIN emails e ON d.email_id = e.id
                WHERE e.parsed_date BETWEEN ? AND ?
            """
            result = pd.read_sql_query(query, conn, params=[start_date, end_date])
        else:
            query = "SELECT COUNT(*) as total FROM deals"
            result = pd.read_sql_query(query, conn)

        conn.close()
        return int(result['total'].iloc[0])

    def get_deals_by_sector(self, period: str = 'all') -> pd.DataFrame:
        """
        Get deal counts grouped by sector.

        Args:
            period: Time period filter

        Returns:
            DataFrame with columns: sector, deal_count
        """
        start_date, end_date = self._parse_date_range(period)

        conn = self._get_connection()

        if start_date and end_date:
            query = """
                SELECT
                    c.name as sector,
                    COUNT(*) as deal_count
                FROM deals d
                JOIN categories c ON d.category_id = c.id
                JOIN emails e ON d.email_id = e.id
                WHERE e.parsed_date BETWEEN ? AND ?
                GROUP BY c.name
                ORDER BY deal_count DESC
            """
            result = pd.read_sql_query(query, conn, params=[start_date, end_date])
        else:
            query = """
                SELECT
                    c.name as sector,
                    COUNT(*) as deal_count
                FROM deals d
                JOIN categories c ON d.category_id = c.id
                GROUP BY c.name
                ORDER BY deal_count DESC
            """
            result = pd.read_sql_query(query, conn)

        conn.close()
        return result

    def get_sector_monthly_trend(self, months: int = 12) -> pd.DataFrame:
        """
        Get monthly deal counts by sector for trend analysis.

        Args:
            months: Number of months to look back

        Returns:
            DataFrame with columns: month, sector, deal_count
        """
        conn = self._get_connection()

        # Calculate start date
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)

        query = """
            SELECT
                strftime('%Y-%m', e.parsed_date) as month,
                c.name as sector,
                COUNT(*) as deal_count
            FROM deals d
            JOIN categories c ON d.category_id = c.id
            JOIN emails e ON d.email_id = e.id
            WHERE e.parsed_date >= ?
            GROUP BY month, c.name
            ORDER BY month, deal_count DESC
        """

        result = pd.read_sql_query(query, conn, params=[start_date.strftime('%Y-%m-%d')])
        conn.close()

        return result

    def get_average_deals_per_sector(self, period: str = 'all') -> pd.DataFrame:
        """
        Get average metrics per sector.

        Args:
            period: Time period filter

        Returns:
            DataFrame with sector statistics
        """
        # Get total deals by sector
        deals_by_sector = self.get_deals_by_sector(period)

        # Calculate number of months in period
        start_date, end_date = self._parse_date_range(period)

        if start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            months = max(1, (end.year - start.year) * 12 + end.month - start.month + 1)
        else:
            # For 'all', calculate based on data range
            conn = self._get_connection()
            query = """
                SELECT
                    MIN(parsed_date) as min_date,
                    MAX(parsed_date) as max_date
                FROM emails
            """
            date_range = pd.read_sql_query(query, conn)
            conn.close()

            if not date_range.empty and date_range['min_date'].iloc[0]:
                start = datetime.strptime(date_range['min_date'].iloc[0][:10], '%Y-%m-%d')
                end = datetime.strptime(date_range['max_date'].iloc[0][:10], '%Y-%m-%d')
                months = max(1, (end.year - start.year) * 12 + end.month - start.month + 1)
            else:
                months = 1

        deals_by_sector['avg_deals_per_month'] = (deals_by_sector['deal_count'] / months).round(2)

        return deals_by_sector

    def extract_pe_firms(self, deal_body: str, metadata: Dict) -> List[str]:
        """
        Extract PE firm names from deal body and metadata using trained classifier.

        Args:
            deal_body: Deal body text
            metadata: Deal metadata dictionary

        Returns:
            List of validated PE firm names
        """
        candidate_firms = []

        # Blacklist of common false positives
        blacklist = {
            'executive management', 'link to', 'link to original', 'source',
            'group sold', 'company owned', 'firm acquired', 'was acquired',
            'in late', 'https', 'http', 'www', 'com', 'original source',
            'press release', 'company press', 'edited', 'he added', 'she added',
            'they added', 'this capital', 'that capital', 'its capital',
            'project capital', 'working capital', 'share capital', 'own capital',
            'foundation', 'partenaires', 'partners', 'cie', 'eutelsat',
            'investment director', 'managing director', 'executive director',
            'via', 'santander', 'bank', 'metro bank'
        }

        # Single-word names that are not PE firms (unless they're structure entities)
        invalid_single_words = {'foundation', 'partenaires', 'partners', 'cie', 'eutelsat',
                               'capital', 'equity', 'ventures', 'investments', 'holdings',
                               'management', 'herman', 'business', 'group', 'company'}

        # Blacklist of standalone words that indicate non-PE context
        invalid_prefixes = {'he', 'she', 'they', 'this', 'that', 'its', 'the', 'a', 'an',
                           'project', 'working', 'share', 'own', 'our', 'their', 'his', 'her'}

        # More precise patterns with length limits
        # Capture firm names ending with PE keywords, max 4 words
        keywords = [
            # "backed by [Firm Name]" - captures firm name only
            r'backed by (?:private equity (?:firm )?)?([A-Z][\w&]+(?:\s+[\w&]+){0,3}\s+(?:Capital|Partners|Equity|Ventures|Investments))',

            # "owned by [Firm Name]"
            r'owned by (?:private equity (?:firm )?)?([A-Z][\w&]+(?:\s+[\w&]+){0,3}\s+(?:Capital|Partners|Equity|Ventures|Investments))',

            # "portfolio company of [Firm Name]"
            r'portfolio company of ([A-Z][\w&]+(?:\s+[\w&]+){0,3}\s+(?:Capital|Partners|Equity|Ventures|Investments))',

            # Direct PE firm mentions - must have 2+ words ending in PE keyword
            r'([A-Z][\w&]+(?:\s+[\w&]+){1,3}\s+(?:Capital|Partners|Equity|Ventures|Investments))',

            # PE structure entities (Holdco, Bidco, etc.) - must have prefix word
            r'([A-Z][\w&]+\s+(?:Holdco|Topco|Bidco|Acquico|Newco))',

            # Holdings firms - must have prefix word
            r'([A-Z][\w&]+(?:\s+[\w&]+){1,2}\s+Holdings?)',
        ]

        # Search in body text
        if deal_body:
            for pattern in keywords:
                matches = re.findall(pattern, deal_body, re.IGNORECASE)
                for match in matches:
                    if match:
                        candidate_firms.append(match.strip())

        # Check metadata for investor info
        for key, value in metadata.items():
            if key in ['Investor', 'Investors', 'Acquirer', 'Buyer', 'Owner', 'Backed by'] and value:
                value_str = str(value)

                # Skip if it's a URL
                if 'http' in value_str.lower() or '://' in value_str:
                    continue

                # Split multiple investors if comma-separated
                if ',' in value_str:
                    candidate_firms.extend([v.strip() for v in value_str.split(',')])
                else:
                    candidate_firms.append(value_str.strip())

        # Clean and validate candidates
        validated_candidates = []

        for firm in candidate_firms:
            if not firm or len(firm.strip()) < 3:
                continue

            firm = firm.strip()
            firm_lower = firm.lower()

            # Check blacklist
            if any(black in firm_lower for black in blacklist):
                continue

            # Must not contain URLs
            if 'http' in firm_lower or '://' in firm or '.com' in firm_lower:
                continue

            # Must not be too long (likely a sentence fragment)
            if len(firm) > 60:
                continue

            # Must start with uppercase letter
            if not firm[0].isupper():
                continue

            # Clean up trailing/leading junk
            # Remove common trailing phrases
            firm = re.sub(r'\s+(in|at|on|by|to|from|with|for|and|or)\s+\w+.*$', '', firm, flags=re.IGNORECASE)
            firm = re.sub(r'\s+(was|is|has|have|had)\s+.*$', '', firm, flags=re.IGNORECASE)

            # Remove "X owner Y Capital" -> keep only "Y Capital"
            firm = re.sub(r'^.+\s+owner\s+([A-Z][\w\s&]+(?:Capital|Partners|Equity|Ventures))$', r'\1', firm, flags=re.IGNORECASE)

            # Remove leading person names before conjunctions: "Herman and the wider Capital" -> skip
            if ' and ' in firm_lower or ' or ' in firm_lower:
                # This is likely a list with conjunction, not a firm name
                continue

            firm = firm.strip()

            # Must contain at least one PE keyword OR be very short with Capital/Partners/etc
            pe_keywords = ['capital', 'partners', 'equity', 'ventures', 'investments',
                          'holdings', 'management', 'holdco', 'bidco', 'topco', 'private equity']
            has_pe_keyword = any(kw in firm_lower for kw in pe_keywords)

            if not has_pe_keyword:
                continue

            # Additional validation: "Executive Management" specifically excluded
            if firm_lower == 'executive management':
                continue

            # Check if first word is an invalid prefix (pronouns, articles, etc.)
            first_word = firm.split()[0].lower()
            if first_word in invalid_prefixes:
                continue

            # Filter out single-word names that are not PE firms
            words = firm.split()
            if len(words) == 1 and firm_lower in invalid_single_words:
                continue

            # Filter out names containing verbs or titles that indicate non-PE context
            verb_indicators = ['sells', 'sold', 'advise', 'advised', 'buys', 'bought',
                             'acquired', 'acquires', 'owns', 'owned', 'manages']
            title_indicators = ['chairman', 'ceo', 'cfo', 'director', 'president',
                               'manager', 'officer']

            words_lower = [w.lower() for w in words]
            if any(verb in words_lower for verb in verb_indicators):
                continue
            if any(title in words_lower for title in title_indicators):
                continue

            # Must have proper capitalization (each word should start uppercase for firm names)
            # Allow some lowercase words (of, and, the) but most should be capitalized
            uppercase_words = sum(1 for w in words if w[0].isupper())
            if uppercase_words < len(words) * 0.6:  # At least 60% words capitalized
                continue

            validated_candidates.append(firm)

        # Normalize case and deduplicate
        # Use a dict to keep longest version of similar names
        normalized_firms = {}

        for firm in validated_candidates:
            # Normalize to title case for comparison
            firm_norm = firm.title()

            # Check if we already have a similar firm (case-insensitive)
            existing_key = None
            for key in normalized_firms.keys():
                if key.lower() == firm_norm.lower():
                    existing_key = key
                    break

            if existing_key:
                # Keep the longer/more complete version
                if len(firm) > len(normalized_firms[existing_key]):
                    del normalized_firms[existing_key]
                    normalized_firms[firm_norm] = firm
            else:
                normalized_firms[firm_norm] = firm

        validated_candidates = list(normalized_firms.values())

        # If classifier is available, further validate
        if self.pe_classifier:
            classifier_validated = []
            for firm in validated_candidates:
                try:
                    result = self.pe_classifier.classify_fund(firm)
                    if result.classification in ['definite_pe', 'likely_pe']:
                        classifier_validated.append(firm)
                except Exception:
                    # If classification fails, keep the firm (it passed basic validation)
                    classifier_validated.append(firm)
            return classifier_validated
        else:
            # Return validated candidates even without classifier
            return validated_candidates

    def get_top_pe_firms(self, limit: int = 10, period: str = 'all') -> pd.DataFrame:
        """
        Get most active PE firms by deal count.

        Args:
            limit: Maximum number of firms to return
            period: Time period filter

        Returns:
            DataFrame with columns: firm_name, deal_count
        """
        start_date, end_date = self._parse_date_range(period)

        conn = self._get_connection()

        # Get all deals with metadata
        if start_date and end_date:
            query = """
                SELECT
                    d.id,
                    d.body,
                    dm.key,
                    dm.value
                FROM deals d
                JOIN emails e ON d.email_id = e.id
                LEFT JOIN deal_metadata dm ON d.id = dm.deal_id
                WHERE e.parsed_date BETWEEN ? AND ?
            """
            deals = pd.read_sql_query(query, conn, params=[start_date, end_date])
        else:
            query = """
                SELECT
                    d.id,
                    d.body,
                    dm.key,
                    dm.value
                FROM deals d
                LEFT JOIN deal_metadata dm ON d.id = dm.deal_id
            """
            deals = pd.read_sql_query(query, conn)

        conn.close()

        # Extract PE firms from each deal
        firm_counts = {}

        for deal_id in deals['id'].unique():
            deal_data = deals[deals['id'] == deal_id]
            body = deal_data['body'].iloc[0] if not deal_data.empty else ''

            # Build metadata dict
            metadata = {}
            for _, row in deal_data.iterrows():
                if pd.notna(row['key']) and pd.notna(row['value']):
                    metadata[row['key']] = row['value']

            # Extract firms
            firms = self.extract_pe_firms(body or '', metadata)

            for firm in firms:
                firm_counts[firm] = firm_counts.get(firm, 0) + 1

        # Convert to DataFrame
        if firm_counts:
            result = pd.DataFrame([
                {'firm_name': firm, 'deal_count': count}
                for firm, count in sorted(firm_counts.items(), key=lambda x: x[1], reverse=True)
            ])
            return result.head(limit)
        else:
            return pd.DataFrame(columns=['firm_name', 'deal_count'])

    def get_deals_by_grade(self, period: str = 'all') -> pd.DataFrame:
        """
        Get deal counts grouped by grade (Confirmed, Rumored, etc.).

        Args:
            period: Time period filter

        Returns:
            DataFrame with columns: grade, deal_count
        """
        start_date, end_date = self._parse_date_range(period)

        conn = self._get_connection()

        if start_date and end_date:
            query = """
                SELECT
                    COALESCE(d.grade, 'Unknown') as grade,
                    COUNT(*) as deal_count
                FROM deals d
                JOIN emails e ON d.email_id = e.id
                WHERE e.parsed_date BETWEEN ? AND ?
                GROUP BY grade
                ORDER BY deal_count DESC
            """
            result = pd.read_sql_query(query, conn, params=[start_date, end_date])
        else:
            query = """
                SELECT
                    COALESCE(d.grade, 'Unknown') as grade,
                    COUNT(*) as deal_count
                FROM deals d
                GROUP BY grade
                ORDER BY deal_count DESC
            """
            result = pd.read_sql_query(query, conn)

        conn.close()
        return result

    def get_geographic_breakdown(self, period: str = 'all') -> pd.DataFrame:
        """
        Get deal counts by geographic region (based on alert_type).

        Args:
            period: Time period filter

        Returns:
            DataFrame with columns: region, deal_count
        """
        start_date, end_date = self._parse_date_range(period)

        conn = self._get_connection()

        if start_date and end_date:
            query = """
                SELECT
                    COALESCE(d.alert_type, 'Unknown') as region,
                    COUNT(*) as deal_count
                FROM deals d
                JOIN emails e ON d.email_id = e.id
                WHERE e.parsed_date BETWEEN ? AND ?
                GROUP BY region
                ORDER BY deal_count DESC
            """
            result = pd.read_sql_query(query, conn, params=[start_date, end_date])
        else:
            query = """
                SELECT
                    COALESCE(d.alert_type, 'Unknown') as region,
                    COUNT(*) as deal_count
                FROM deals d
                GROUP BY region
                ORDER BY deal_count DESC
            """
            result = pd.read_sql_query(query, conn)

        conn.close()
        return result

    def get_summary_stats(self) -> Dict:
        """
        Get overall summary statistics.

        Returns:
            Dictionary with key metrics
        """
        return {
            'total_deals_all': self.get_total_deals('all'),
            'total_deals_mtd': self.get_total_deals('current_month'),
            'total_deals_ytd': self.get_total_deals('ytd'),
            'total_sectors': len(self.get_deals_by_sector('all')),
            'top_sector': self.get_deals_by_sector('all')['sector'].iloc[0] if not self.get_deals_by_sector('all').empty else 'N/A',
        }


def main():
    """Test the analytics calculator."""
    calc = AnalyticsCalculator()

    print("="*60)
    print("ANALYTICS CALCULATOR TEST")
    print("="*60)
    print()

    # Summary stats
    print("SUMMARY STATISTICS")
    print("-"*60)
    stats = calc.get_summary_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    print()

    # Deals by sector
    print("DEALS BY SECTOR (All Time)")
    print("-"*60)
    print(calc.get_deals_by_sector('all'))
    print()

    # Monthly trend
    print("SECTOR MONTHLY TREND (Last 12 months)")
    print("-"*60)
    print(calc.get_sector_monthly_trend(12).head(20))
    print()

    # Top PE firms
    print("TOP PE FIRMS")
    print("-"*60)
    print(calc.get_top_pe_firms(10))
    print()

    # Deals by grade
    print("DEALS BY GRADE")
    print("-"*60)
    print(calc.get_deals_by_grade('all'))
    print()


if __name__ == '__main__':
    main()
