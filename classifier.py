import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz, process
import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict, Counter
import math

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class FundClassificationResult:
    fund_name: str
    score: float
    classification: str
    confidence: float
    reasons: List[str]
    fund_type: str = "unknown"

class EnhancedPEFundClassifier:
    
    def __init__(self):
        self.thresholds = {
            'definite_pe': 2.0,
            'likely_pe': 1.0,
            'uncertain': 0.0
        }
        
        # Load and calculate individual word scores from training data
        self.word_scores = self._load_and_calculate_word_scores()
        
        # Add predefined multilingual PE keywords
        self._add_predefined_keywords()
        
        self.fund_patterns = {
            'numeric_fund': {
                'pattern': r'^\d+.*(?:fund|capital|ventures?|equity|partners)',
                'score': 1.2,
                'description': 'Numeric prefix with fund terms'
            },
            'year_based_fund': {
                'pattern': r'\b(19|20)\d{2}\s*(?:fund|capital|ventures?)',
                'score': 1.0,
                'description': 'Year-based fund naming'
            },
            'roman_numeral_series': {
                'pattern': r'\b[ivxlcdm]+\s*$',
                'score': 0.8,
                'description': 'Roman numeral series'
            },
            'fund_series_pattern': {
                'pattern': r'(?:fund|capital|ventures?)\s+[ivx0-9]+\s*$',
                'score': 1.0,
                'description': 'Fund series pattern'
            },
            'co_investment_pattern': {
                'pattern': r'co[\s\-]?invest',
                'score': 0.9,
                'description': 'Co-investment structure'
            },
            'spv_pattern': {
                'pattern': r'\bspv\b',
                'score': 0.8,
                'description': 'Special Purpose Vehicle'
            },
            'short_branded_name': {
                'pattern': r'^[a-z0-9&+.]{2,8}(?:\s+[ivx0-9]+)?$',
                'score': 0.6,
                'description': 'Short branded fund name'
            },
            'fund_suffix': {
                'pattern': r'(?:fund|capital|ventures?|equity|partners|lp|llc|ltd)\s*$',
                'score': 0.8,
                'description': 'Fund structure suffix'
            },
            'bid_top_pattern': {
                'pattern': r'\b(?:bid|top)[a-z]*\b',
                'score': 5.0,
                'description': 'BID/TOP PE indicator pattern'
            },
            'pe_structure_pattern': {
                'pattern': r'\b(?:holdco|topco|bidco|acquico|newco|finco|propco)\b',
                'score': 8.0,
                'description': 'PE acquisition structure entities'
            }
        }
    
    def _load_and_calculate_word_scores(self) -> Dict[str, float]:
        """Load training data and calculate individual word scores using TF-IDF-like approach"""
        try:
            logger.info("Loading training data from testing_results.xlsx...")
            df = pd.read_excel("testing_results.xlsx")
            
            # Clean the data
            df = df.dropna(subset=['NAME', 'IS_PE'])
            df['NAME'] = df['NAME'].astype(str).str.strip()
            df = df[df['NAME'] != '']
            
            pe_funds = df[df['IS_PE'] == 'YES']['NAME'].tolist()
            non_pe_funds = df[df['IS_PE'] == 'NO']['NAME'].tolist()
            
            logger.info(f"Loaded {len(pe_funds)} PE funds and {len(non_pe_funds)} non-PE funds")
            
            # Extract and count words
            pe_word_counts = self._extract_word_counts(pe_funds)
            non_pe_word_counts = self._extract_word_counts(non_pe_funds)
            
            # Calculate word scores
            word_scores = self._calculate_word_scores(pe_word_counts, non_pe_word_counts, 
                                                    len(pe_funds), len(non_pe_funds))
            
            # Apply manual boosts for critical PE structure terms
            pe_structure_terms = {
                'holdco': 12.0,
                'topco': 12.0, 
                'bidco': 12.0,
                'acquico': 12.0,
                'newco': 12.0,
                'finco': 12.0,
                'propco': 12.0
            }
            
            for term, boost_score in pe_structure_terms.items():
                if term in word_scores:
                    # Keep the higher of calculated vs manual score
                    word_scores[term] = max(word_scores[term], boost_score)
                else:
                    # Add the term if not found in training data
                    word_scores[term] = boost_score
            
            logger.info(f"Calculated scores for {len(word_scores)} unique words")
            logger.info(f"Applied manual boosts for PE structure terms: {list(pe_structure_terms.keys())}")
            
            # Log top positive and negative words for verification
            sorted_words = sorted(word_scores.items(), key=lambda x: x[1], reverse=True)
            logger.info(f"Top 10 PE-indicating words: {sorted_words[:10]}")
            logger.info(f"Top 10 non-PE-indicating words: {sorted_words[-10:]}")
            
            return word_scores
            
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            logger.info("Using fallback word scores...")
            return self._get_fallback_word_scores()
    
    def _extract_word_counts(self, fund_names: List[str]) -> Counter:
        """Extract and count words from fund names"""
        word_counts = Counter()
        
        for name in fund_names:
            # Convert to lowercase and clean
            clean_name = re.sub(r'[^\w\s]', ' ', name.lower())
            words = clean_name.split()
            
            # Filter out very short words and numbers
            words = [w for w in words if len(w) >= 2 and not w.isdigit()]
            
            word_counts.update(words)
        
        return word_counts
    
    def _calculate_word_scores(self, pe_word_counts: Counter, non_pe_word_counts: Counter,
                             pe_total: int, non_pe_total: int) -> Dict[str, float]:
        """Calculate individual word scores using statistical approach"""
        word_scores = {}
        
        # Get all unique words
        all_words = set(pe_word_counts.keys()) | set(non_pe_word_counts.keys())
        
        for word in all_words:
            pe_count = pe_word_counts.get(word, 0)
            non_pe_count = non_pe_word_counts.get(word, 0)
            
            # Skip words that appear too rarely (less than 3 times total)
            if pe_count + non_pe_count < 3:
                continue
            
            # Calculate frequencies
            pe_freq = pe_count / pe_total if pe_total > 0 else 0
            non_pe_freq = non_pe_count / non_pe_total if non_pe_total > 0 else 0
            
            # Calculate log odds ratio with smoothing
            smooth = 1e-6
            pe_prob = (pe_count + smooth) / (pe_total + 2 * smooth)
            non_pe_prob = (non_pe_count + smooth) / (non_pe_total + 2 * smooth)
            
            # Log odds ratio
            log_odds = math.log(pe_prob / non_pe_prob)
            
            # Weight by total frequency (more frequent words get higher weight)
            total_freq = (pe_count + non_pe_count) / (pe_total + non_pe_total)
            frequency_weight = min(1.0, total_freq * 1000)  # Cap the weight
            
            # Final score
            word_scores[word] = log_odds * frequency_weight
        
        return word_scores
    
    def _get_fallback_word_scores(self) -> Dict[str, float]:
        """Fallback word scores if training data loading fails"""
        return {
            'fund': 2.0, 'capital': 1.8, 'equity': 1.6, 'ventures': 1.5, 'partners': 1.4,
            'investment': 1.3, 'management': 1.2, 'advisors': 1.1, 'venture': 1.5, 'opportunities': 1.0,
            'private': 1.8, 'buyout': 1.6, 'growth': 1.2, 'spv': 1.4, 'holdco': 12.0,
            'topco': 12.0, 'bidco': 12.0, 'acquico': 12.0, 'newco': 12.0, 'invest': 1.2,
            'holding': 1.1, 'seed': 1.4, 'series': 1.3, 'emerging': 1.1, 'impact': 1.0,
            'tech': 0.5, 'healthcare': 0.5, 'energy': 0.5, 'industrial': 0.5,
            'gmbh': -2.0, 'ag': -1.5, 'bank': -1.8, 'insurance': -1.6, 'pension': -1.4,
            'foundation': -1.3, 'stiftung': -1.5, 'gastro': -2.0, 'restaurant': -1.8,
            'baeckerei': -1.6, 'cafe': -1.5, 'rewe': -1.8, 'food': -1.2, 'markt': -1.4
        }
    
    def classify_fund(self, fund_name: str) -> FundClassificationResult:
        
        if pd.isna(fund_name):
            return FundClassificationResult(
                fund_name=str(fund_name),
                score=0.0,
                classification='not_pe',
                confidence=0.0,
                reasons=['Empty or invalid name']
            )
        
        fund_name_str = str(fund_name).strip()
        if not fund_name_str:
            return FundClassificationResult(
                fund_name=fund_name_str,
                score=0.0,
                classification='not_pe',
                confidence=0.0,
                reasons=['Empty or invalid name']
            )
        
        fund_name = fund_name_str
        fund_lower = fund_name.lower()
        
        total_score = 0.0
        reasons = []
        fund_type = "unknown"
        
        # Score individual words
        word_score, word_reasons = self._score_individual_words(fund_lower)
        total_score += word_score
        reasons.extend(word_reasons)
        
        # Apply pattern scoring
        pattern_score, pattern_reasons, detected_type = self._score_fund_patterns(fund_lower)
        total_score += pattern_score
        reasons.extend(pattern_reasons)
        if detected_type:
            fund_type = detected_type
        
        # Apply special rules
        special_score, special_reasons = self._apply_fund_special_rules(fund_name, fund_lower)
        total_score += special_score
        reasons.extend(special_reasons)
        
        if fund_type == "unknown":
            fund_type = self._determine_fund_type(fund_lower, reasons)
        
        # PE Database Context Bonus (smaller now since we're using training data)
        context_bonus = 0.3
        total_score += context_bonus
        reasons.append(f"PE Database Context Bonus (+{context_bonus:.1f})")
        
        # Determine classification based on score
        if total_score >= self.thresholds['definite_pe']:
            classification = 'definite_pe'
            confidence = min(0.99, 0.7 + (total_score / 10))
        elif total_score >= self.thresholds['likely_pe']:
            classification = 'likely_pe'
            confidence = min(0.88, 0.5 + (total_score / 8))
        elif total_score >= self.thresholds['uncertain']:
            classification = 'uncertain'
            confidence = min(0.65, 0.3 + (total_score / 6))
        else:
            classification = 'not_pe'
            confidence = max(0.1, 0.6 + total_score / 5)  # Negative scores reduce confidence
        
        return FundClassificationResult(
            fund_name=fund_name,
            score=total_score,
            classification=classification,
            confidence=confidence,
            reasons=reasons if reasons else ['No clear PE indicators found'],
            fund_type=fund_type
        )
    
    def _score_individual_words(self, fund_lower: str) -> Tuple[float, List[str]]:
        """Score based on individual words and phrases using trained and predefined scores"""
        total_score = 0.0
        reasons = []
        
        # First, check for multi-word phrases
        phrase_contributions = []
        matched_phrase_positions = []
        
        for phrase, score in self.phrase_scores.items():
            if phrase in fund_lower:
                total_score += score
                phrase_contributions.append((phrase, score))
                # Track positions to avoid double-counting words in phrases
                start_pos = fund_lower.find(phrase)
                end_pos = start_pos + len(phrase)
                matched_phrase_positions.extend(range(start_pos, end_pos))
        
        # Extract words from fund name, excluding those already matched in phrases
        clean_name = re.sub(r'[^\w\s]', ' ', fund_lower)
        words = clean_name.split()
        words = [w for w in words if len(w) >= 2 and not w.isdigit()]
        
        word_contributions = []
        for word in words:
            # Check if this word is part of an already matched phrase
            word_pos = fund_lower.find(word)
            if any(pos in matched_phrase_positions for pos in range(word_pos, word_pos + len(word))):
                continue  # Skip words that are part of matched phrases
                
            if word in self.word_scores:
                score = self.word_scores[word]
                total_score += score
                word_contributions.append((word, score))
        
        # Group reasons by positive and negative contributions
        all_contributions = phrase_contributions + word_contributions
        positive_terms = [(term, score) for term, score in all_contributions if score > 0]
        negative_terms = [(term, score) for term, score in all_contributions if score < 0]
        
        if positive_terms:
            positive_terms.sort(key=lambda x: x[1], reverse=True)
            top_positive = positive_terms[:3]  # Show top 3
            reason = "Positive terms: " + ", ".join([f"'{term}' (+{score:.2f})" for term, score in top_positive])
            reasons.append(reason)
        
        if negative_terms:
            negative_terms.sort(key=lambda x: x[1])
            top_negative = negative_terms[:3]  # Show top 3 most negative
            reason = "Negative terms: " + ", ".join([f"'{term}' ({score:.2f})" for term, score in top_negative])
            reasons.append(reason)
        
        return total_score, reasons
    
    def _score_fund_patterns(self, fund_lower: str) -> Tuple[float, List[str], str]:
        total_score = 0.0
        reasons = []
        fund_type = "unknown"
        
        for pattern_name, config in self.fund_patterns.items():
            pattern = config['pattern']
            score = config['score']
            description = config['description']
            
            if re.search(pattern, fund_lower, re.IGNORECASE):
                total_score += score
                reasons.append(f"Fund Pattern: {description} (+{score:.1f})")
                
                if 'co' in pattern_name or 'spv' in pattern_name:
                    fund_type = "special_purpose"
                elif 'series' in pattern_name or 'roman' in pattern_name:
                    fund_type = "series_fund"
                elif 'numeric' in pattern_name:
                    fund_type = "modern_fund"
                elif 'bid_top' in pattern_name:
                    fund_type = "pe_acquisition"
                
                break
        
        return total_score, reasons, fund_type
    
    def _apply_fund_special_rules(self, fund_name: str, fund_lower: str) -> Tuple[float, List[str]]:
        total_score = 0.0
        reasons = []
        
        # Fund series numbering
        if re.search(r'\b[ivx0-9]+\s*$', fund_lower):
            total_score += 0.5
            reasons.append('Fund Series Numbering (+0.5)')
        
        # Contains year
        if re.search(r'\b(19|20)\d{2}\b', fund_lower):
            total_score += 0.3
            reasons.append('Contains Year (+0.3)')
        
        # All caps short name
        if fund_name.isupper() and len(fund_name.split()) <= 3:
            total_score += 0.2
            reasons.append('All Caps Short Name (+0.2)')
        
        # Fund abbreviations
        fund_abbrevs = ['lp', 'llc', 'ltd', 'gp', 'mgmt']
        for abbrev in fund_abbrevs:
            if abbrev in fund_lower:
                total_score += 0.3
                reasons.append(f'Fund Abbreviation: {abbrev} (+0.3)')
                break
        
        # Multiple numeric indicators
        numeric_count = len(re.findall(r'\d+', fund_lower))
        if numeric_count >= 2:
            total_score += 0.4
            reasons.append('Multiple Numeric Indicators (+0.4)')
        
        return total_score, reasons
    
    def _determine_fund_type(self, fund_lower: str, reasons: List[str]) -> str:
        
        if any('spv' in reason.lower() or 'co-invest' in reason.lower() for reason in reasons):
            return "special_purpose"
        elif any('bid' in reason.lower() or 'top' in reason.lower() for reason in reasons):
            return "pe_acquisition"
        elif any('ventures' in fund_lower for term in ['ventures', 'venture']):
            return "venture_capital"
        elif 'growth' in fund_lower:
            return "growth_capital"
        elif 'buyout' in fund_lower:
            return "buyout"
        elif any(term in fund_lower for term in ['real estate', 'reit']):
            return "real_estate"
        elif any(term in fund_lower for term in ['infrastructure', 'energy']):
            return "infrastructure"
        else:
            return "general_pe"
    
    def _add_predefined_keywords(self):
        """Add predefined multilingual PE keywords to word scores"""
        
        # PE-specific terms - Score: 10.0
        pe_specific = {
            # English
            'private equity': 10.0, 'buyout': 10.0, 'leveraged buyout': 10.0, 'lbo': 10.0, 
            'growth equity': 10.0, 'pe fund': 10.0, 'private equity fund': 10.0, 
            'portfolio company': 10.0, 'portfolio companies': 10.0,
            # Spanish
            'capital privado': 10.0, 'fondo de capital privado': 10.0, 'compra apalancada': 10.0, 
            'capital riesgo': 10.0, 'empresa en cartera': 10.0, 'empresas en cartera': 10.0,
            # German
            'beteiligungskapital': 10.0, 'beteiligungsgesellschaft': 10.0, 'wachstumskapital': 10.0, 
            'portfoliounternehmen': 10.0, 'beteiligungsfonds': 10.0,
            # French
            'capital investissement': 10.0, 'capital développement': 10.0, 
            'fonds de capital investissement': 10.0, 'rachat avec effet de levier': 10.0, 
            'société de portefeuille': 10.0, 'sociétés en portefeuille': 10.0,
            # Dutch
            'participatiemaatschappij': 10.0, 'durfkapitaal': 10.0, 'groeikapitaal': 10.0, 
            'portfoliobedrijf': 10.0, 'portfoliobedrijven': 10.0, 'participatiefonds': 10.0
        }
        
        # Strong indicators - Score: 8.0
        strong_indicators = {
            # English
            'acquisition': 8.0, 'acquisitions': 8.0, 'buyout fund': 8.0, 'growth capital': 8.0, 
            'management buyout': 8.0, 'mbo': 8.0, 'investment firm': 8.0, 'alternative investment': 8.0, 
            'distressed debt': 8.0, 'mezzanine': 8.0,
            # Spanish
            'adquisición': 8.0, 'adquisiciones': 8.0, 'fondo de adquisición': 8.0, 
            'capital de crecimiento': 8.0, 'compra por gestión': 8.0, 'firma de inversión': 8.0, 
            'inversión alternativa': 8.0, 'deuda en dificultades': 8.0,
            # German
            'akquisition': 8.0, 'akquisitionen': 8.0, 'übernahme': 8.0, 'übernahmen': 8.0, 
            'wachstumsfinanzierung': 8.0, 'investmentfirma': 8.0, 'alternative anlagen': 8.0, 
            'mezzanine-kapital': 8.0,
            # French
            'fonds de rachat': 8.0, 'capital croissance': 8.0, 'rachat par la direction': 8.0, 
            'société d\'investissement': 8.0, 'investissement alternatif': 8.0, 'dette en difficulté': 8.0,
            # Dutch
            'acquisitie': 8.0, 'acquisities': 8.0, 'overname': 8.0, 'overnames': 8.0, 
            'groeifinanciering': 8.0, 'investeringsmaatschappij': 8.0, 'alternatieve belegging': 8.0, 
            'mezzaninefinanciering': 8.0
        }
        
        # Moderate indicators - Score: 6.0
        moderate_indicators = {
            # English
            'capital': 6.0, 'equity': 6.0, 'fund': 6.0, 'partners': 6.0, 'investments': 6.0, 
            'holdings': 6.0, 'ventures': 6.0, 'assets': 6.0,
            # Spanish
            'equidad': 6.0, 'patrimonio': 6.0, 'fondo': 6.0, 'socios': 6.0, 'inversiones': 6.0, 
            'participaciones': 6.0, 'activos': 6.0,
            # German
            'kapital': 6.0, 'eigenkapital': 6.0, 'fonds': 6.0, 'partner': 6.0, 'investitionen': 6.0, 
            'beteiligungen': 6.0, 'vermögenswerte': 6.0, 'anlagen': 6.0,
            # French
            'équité': 6.0, 'partenaires': 6.0, 'investissements': 6.0, 'participations': 6.0, 'actifs': 6.0,
            # Dutch
            'kapitaal': 6.0, 'eigen vermogen': 6.0, 'investeringen': 6.0, 'participaties': 6.0, 
            'activa': 6.0, 'vermogen': 6.0
        }
        
        # Context enhancers - Score: 4.0
        context_enhancers = {
            # English
            'management': 4.0, 'strategic': 4.0, 'financial': 4.0, 'advisory': 4.0, 'global': 4.0, 
            'international': 4.0,
            # Spanish
            'gestión': 4.0, 'estratégico': 4.0, 'financiero': 4.0, 'asesoría': 4.0, 'internacional': 4.0,
            # German
            'strategisch': 4.0, 'finanziell': 4.0, 'beratung': 4.0,
            # French
            'gestion': 4.0, 'stratégique': 4.0, 'financier': 4.0, 'conseil': 4.0,
            # Dutch
            'beheer': 4.0, 'financieel': 4.0, 'advies': 4.0, 'globaal': 4.0, 'internationaal': 4.0
        }
        
        # Negative indicators - Score: -8.0
        negative_indicators = {
            # English
            'public': -8.0, 'listed': -8.0, 'traded': -8.0, 'mutual fund': -8.0, 'etf': -8.0, 
            'exchange traded': -8.0, 'index fund': -8.0, 'bank': -8.0, 'insurance': -8.0, 'retail': -8.0,
            # Spanish
            'público': -8.0, 'cotizado': -8.0, 'negociado': -8.0, 'fondo mutuo': -8.0, 
            'fondo índice': -8.0, 'banco': -8.0, 'seguro': -8.0, 'minorista': -8.0,
            # German
            'öffentlich': -8.0, 'börsennotiert': -8.0, 'gehandelt': -8.0, 'investmentfonds': -8.0, 
            'indexfonds': -8.0, 'versicherung': -8.0, 'einzelhandel': -8.0,
            # French
            'coté': -8.0, 'négocié': -8.0, 'fonds commun': -8.0, 'fonds indiciel': -8.0, 
            'banque': -8.0, 'assurance': -8.0, 'détail': -8.0,
            # Dutch
            'publiek': -8.0, 'beursgenoteerd': -8.0, 'verhandeld': -8.0, 'beleggingsfonds': -8.0, 
            'verzekering': -8.0, 'detailhandel': -8.0
        }
        
        # Combine all predefined keywords
        all_predefined = {}
        all_predefined.update(pe_specific)
        all_predefined.update(strong_indicators)
        all_predefined.update(moderate_indicators)
        all_predefined.update(context_enhancers)
        all_predefined.update(negative_indicators)
        
        # Add predefined scores, keeping higher absolute values when conflicts occur
        for term, score in all_predefined.items():
            # For phrases, also add individual words if they don't already have higher scores
            if ' ' in term:
                # Handle multi-word phrases separately
                continue
            else:
                # Single words: use higher absolute value
                current_score = self.word_scores.get(term, 0)
                if abs(score) > abs(current_score):
                    self.word_scores[term] = score
        
        # Store phrases separately for phrase matching
        self.phrase_scores = {term: score for term, score in all_predefined.items() if ' ' in term}
        
        logger.info(f"Added {len(all_predefined)} predefined multilingual keywords")
        logger.info(f"Total phrases for matching: {len(self.phrase_scores)}")

def process_preqin_funds_enhanced():
    try:
        output_dir = Path("data/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        df = pd.read_excel("preqin_pe_funds.xlsx")
        logger.info(f"Processing {len(df)} funds with enhanced individual word classifier...")
        
        classifier = EnhancedPEFundClassifier()
        
        results = []
        for idx, fund_name in enumerate(df['NAME'].dropna()):
            if idx % 500 == 0:
                logger.info(f"Processed {idx}/{len(df)} funds ({idx/len(df)*100:.1f}%)")
            
            result = classifier.classify_fund(fund_name)
            results.append({
                'fund_name': result.fund_name,
                'classification': result.classification,
                'score': result.score,
                'confidence': result.confidence,
                'fund_type': result.fund_type,
                'reasons': '; '.join(result.reasons)
            })
        
        results_df = pd.DataFrame(results)
        
        output_file = output_dir / "enhanced_preqin_pe_funds_results_individual_words.xlsx"
        results_df.to_excel(output_file, index=False)
        
        logger.info(f"Enhanced individual word classification completed!")
        logger.info(f"Results saved to: {output_file}")
        
        print("\n" + "="*80)
        print("ENHANCED INDIVIDUAL WORD CLASSIFICATION SUMMARY")
        print("="*80)
        
        classification_counts = results_df['classification'].value_counts()
        total_pe = sum(count for cls, count in classification_counts.items() 
                      if cls in ['definite_pe', 'likely_pe'])
        pe_rate = (total_pe / len(results_df)) * 100
        
        for classification, count in classification_counts.items():
            percentage = (count / len(results_df)) * 100
            print(f"{classification}: {count} ({percentage:.1f}%)")
        
        print(f"\nTotal PE Success Rate: {pe_rate:.1f}%")
        print(f"Average Score: {results_df['score'].mean():.2f}")
        print(f"Average Confidence: {results_df['confidence'].mean():.2f}")
        
        return results_df
        
    except Exception as e:
        logger.error(f"Error in enhanced classification: {e}")
        raise

if __name__ == "__main__":
    from pathlib import Path
    process_preqin_funds_enhanced()