import re
import json
from pathlib import Path
from collections import defaultdict, OrderedDict
from datetime import datetime

INPUT_PATH = "input_email.txt"
OUTPUT_PATH = "grouped.json"

# ---- CONFIG ----
ALLOWED_SECTIONS = {
    "Automotive",
    "Chemicals and materials",
    "Computer software",
    "Construction",
    "Consumer: Foods",
    "Consumer: Other",
    "Consumer: Retail",
    "Energy",
    "Financial Services",
    "Industrial automation",
    "Industrial products and services",
    "Industrial: Electronics",
    "Internet / ecommerce",
    "Leisure",
    "Media",
    "Real Estate",
    "Services (other)",
    "Telecommunications: Carriers",
    "Transportation",
}

# Numbered title like "14. Something"
ITEM_RE = re.compile(r'^\s*(\d+)\.\s+(.*\S)\s*$')

# Minimal URL finder (what you showed: a URL inside parentheses)
URL_IN_PARENS_RE = re.compile(r'\((\s*https?://[^\s)]+(?:\)[^)]*)?)\)')  # capture first URL inside () even if nested )

# Key: Value metadata lines (e.g., "Source: Company Press Release(s), ...")
META_RE = re.compile(r'^\s*([A-Za-z][A-Za-z\s/()&-]*?):\s*(.*?)\s*$')


def is_section_heading(line: str) -> bool:
    """A heading is a non-empty line that is not a numbered item and matches an allowed section exactly."""
    s = line.strip()
    return s in ALLOWED_SECTIONS


def collect_titles_and_positions(lines):
    """
    For each allowed section, collect all titled items with every position (line index)
    they appear at (overview + later repeated detail header).
    """
    # First, find the boundary between overview and details sections
    # The details section starts when we see the first item number repeat (e.g., "1. " again)
    details_start = None
    first_items_seen = set()
    
    for i, line in enumerate(lines):
        m = ITEM_RE.match(line)
        if m:
            item_num = int(m.group(1))
            if item_num in first_items_seen:
                details_start = i
                break
            first_items_seen.add(item_num)
    
    # Find section ranges in the overview section only
    section_positions = []  # [(section_name, start_idx, end_idx_exclusive)]
    current = None
    start = None
    end_search = details_start if details_start else len(lines)
    
    for i, raw in enumerate(lines[:end_search]):
        if is_section_heading(raw):
            # close previous section range
            if current is not None:
                section_positions.append((current, start, i))
            current = raw.strip()
            start = i + 1
    if current is not None:
        section_positions.append((current, start, end_search))

    # Create mapping from item title to section
    title_to_section = {}
    
    # For each section, collect item occurrences (both overview and details)
    per_section = OrderedDict()
    for section, s_start, s_end in section_positions:
        seen = defaultdict(list)  # title -> [indices]
        order = []                # preserve first-occurrence order
        
        # Collect overview items from this section
        for idx in range(s_start, s_end):
            m = ITEM_RE.match(lines[idx])
            if m:
                title = lines[idx].strip()  # keep the full "N. Title"
                if title not in seen:
                    order.append(title)
                seen[title].append(idx)
                title_to_section[title] = section
        
        per_section[section] = {"order": order, "occurrences": seen, "range": (s_start, s_end)}
    
    # Now scan the details section and add those occurrences to the appropriate sections
    if details_start:
        for idx in range(details_start, len(lines)):
            m = ITEM_RE.match(lines[idx])
            if m:
                title = lines[idx].strip()
                # Find which section this title belongs to
                if title in title_to_section:
                    section = title_to_section[title]
                    per_section[section]["occurrences"][title].append(idx)
    
    return per_section


def slice_details(lines, section_range, occurrences, start_idx):
    """
    Given a section range and index of the *detail header* line for an item,
    return the slice (start, end) for the detail block (exclusive of header line).
    Stops at next numbered title or next section heading or EOF.
    """
    # For details section, search until EOF or next numbered item
    boundaries = []
    for idx in range(start_idx + 1, len(lines)):
        line = lines[idx]
        if is_section_heading(line):     # next section (unlikely in details, but safe)
            boundaries.append(idx)
            break
        if ITEM_RE.match(line):          # next item's header
            boundaries.append(idx)
            break
    end = boundaries[0] if boundaries else len(lines)
    return start_idx + 1, end


def parse_details_block(block_lines):
    """
    Split a detail block into bullets, body, links, and metadata.
    - bullets: lines beginning with '*' or '•' (kept as text without the marker)
    - links: any URL found inside parentheses on any line
    - metadata: simple "Key: Value" lines (e.g., Source:, Size:, Value:, Grade:, etc.)
    - body: the remaining text joined with newlines (preserving paragraphs)
    """
    bullets = []
    meta = OrderedDict()
    links = []

    # First pass: extract links and categorize lines
    remaining = []
    for raw in block_lines:
        line = raw.rstrip()

        # links (we keep raw urls)
        for m in URL_IN_PARENS_RE.finditer(line):
            url = m.group(1).strip()
            # If there is a trailing ')' mistakenly included, strip balanced
            url = url.split(')')[0]  # conservative cleanup
            links.append(url)

        # bullets
        if line.lstrip().startswith(("* ", "• ")):
            bullets.append(line.lstrip()[2:].strip())
            continue

        # metadata (Key: Value)
        mm = META_RE.match(line)
        if mm:
            key = mm.group(1).strip()
            val = mm.group(2).strip()
            # Merge multi-line values if repeated keys
            if key in meta and val:
                meta[key] = f"{meta[key]} {val}"
            else:
                meta[key] = val
            continue

        remaining.append(line)

    # Clean extra blank lines at block start/end
    # Also drop pure-empty lines that are adjacent (normalize to single blank)
    cleaned = []
    prev_blank = False
    for ln in remaining:
        if ln.strip() == "":
            if not prev_blank and cleaned:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(ln)
            prev_blank = False

    body = "\n".join(cleaned).strip()

    return {
        "bullets": bullets,
        "body": body,
        "links": links,
        "metadata": meta
    }


def extract_email_metadata(lines):
    """Extract email metadata from the first few lines."""
    email_meta = {
        "subject": None,
        "timestamp": None,
        "parsed_date": None
    }
    
    # Look for subject line in first few lines
    for i, line in enumerate(lines[:5]):
        if line.strip().startswith("Subject:"):
            subject_line = line.strip()
            email_meta["subject"] = subject_line
            
            # Extract timestamp from subject line
            # Pattern: "Subject: ... (DD/MM/YYYY HH:MM:SS)"
            timestamp_match = re.search(r'\((\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\)', subject_line)
            if timestamp_match:
                timestamp_str = timestamp_match.group(1)
                email_meta["timestamp"] = timestamp_str
                try:
                    # Parse to datetime object
                    email_meta["parsed_date"] = datetime.strptime(timestamp_str, "%d/%m/%Y %H:%M:%S")
                except ValueError:
                    pass
            break
    
    return email_meta


def build_json(lines):
    # Extract email metadata first
    email_meta = extract_email_metadata(lines)
    
    sections = collect_titles_and_positions(lines)
    out = OrderedDict()
    
    # Add email metadata to output
    if email_meta["subject"]:
        out["_email_metadata"] = {
            "subject": email_meta["subject"],
            "timestamp": email_meta["timestamp"],
            "parsed_date": email_meta["parsed_date"].isoformat() if email_meta["parsed_date"] else None
        }

    for section, data in sections.items():
        order = data["order"]
        occ = data["occurrences"]
        s_range = data["range"]

        items = []
        for title in order:
            # details: look for a second occurrence (the repeated header)
            positions = occ[title]
            details_obj = None
            if len(positions) >= 2:
                detail_header_idx = positions[1]
                d_start, d_end = slice_details(lines, s_range, occ, detail_header_idx)
                details_obj = parse_details_block(lines[d_start:d_end])

            items.append({
                "title": title,     # e.g., "1. Daimler Truck, Volvo launch software JV Coretura"
                "details": details_obj  # None if not found; else {bullets, body, links, metadata}
            })

        if items:
            out[section] = items

    return out


def main():
    text = Path(INPUT_PATH).read_text(encoding="utf-8")
    lines = text.splitlines()
    data = build_json(lines)

    Path(OUTPUT_PATH).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} with {sum(len(v) for v in data.values())} items across {len(data)} sections.")


if __name__ == "__main__":
    main()
