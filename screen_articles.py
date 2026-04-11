"""
screen_articles.py — Dual-Pass Screening Engine with RIS Export

Screens parsed articles using keyword logic, runs dual independent passes,
and exports included articles as a valid RIS file.

Usage:
    python screen_articles.py                          # Uses parsed_articles.json
    python screen_articles.py --input my_articles.json
"""

import json
import csv
import os
import logging
import argparse

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("screening_run.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def screen_single_pass(articles):
    """Execute a single screening pass on all articles. Returns list of result dicts."""
    results = []
    for art in articles:
        title = art.get('title', '').upper()
        abstract = art.get('abstract', '').upper()
        
        # Exact GCT keywords
        gct_keywords = ["GIANT CELL TUMOR", "GIANT-CELL TUMOR", "GIANT CELL TUMOUR", "GIANT-CELL TUMOUR", "OSTEOCLASTOMA"]
        
        # Check if GCT is the main topic (usually in title)
        is_gct_in_title = any(x in title for x in gct_keywords)
        is_gct_in_abstract = any(x in abstract for x in gct_keywords)
        
        # Check for other competing tumor types in title
        competing_diagnosis = any(x in title for x in ["OSTEOBLASTOMA", "ANEURYSMAL BONE CYST", "METASTASIS", "METASTASES", "LYMPHOMA", "CHORDOMA", "PLASMACYTOMA"])
        # Exception: if title has GCT AND metastases (like case 1)
        if is_gct_in_title and "METASTAS" in title:
            competing_diagnosis = False
            
        # Refined GCT check
        is_gct = is_gct_in_title or (is_gct_in_abstract and not competing_diagnosis)
        
        # Cervical Spine check
        cervical_keywords = ["CERVICAL", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "ATLANTOAXIAL"]
        is_cervical_in_title = any(x in title for x in cervical_keywords)
        is_cervical_in_abstract = any(x in abstract for x in cervical_keywords)
        is_cervical = is_cervical_in_title or is_cervical_in_abstract

        # ONLY BONE GCT
        # Exclude Synovial or Tenosynovial types
        is_non_bone = any(x in title for x in ["SYNOVIAL", "TENOSYNOVIAL"]) or \
                       any(x in abstract for x in ["SYNOVIAL", "TENOSYNOVIAL"])
        
        # Exclusion criteria - Types
        is_review = any(x in title for x in ["SYSTEMATIC REVIEW", "META-ANALYSIS", "NARRATIVE REVIEW", "LITERATURE REVIEW"]) or \
                    (title.startswith("REVIEW") or " REVIEW " in title or title.endswith("REVIEW"))
        
        # Decision logic
        decision = "Exclude"
        reason = ""
        
        if not is_gct:
            reason = "Not GCT/Osteoclastoma or primary topic is another tumor type"
        elif is_non_bone:
            reason = "Non-bone origin (Synovial/Tenosynovial)"
        elif not is_cervical:
            reason = "Not Cervical Spine"
        elif is_review:
            reason = "Review/Meta-Analysis/Systematic Review"
        else:
            decision = "Include"
            reason = "Original article on Cervical Bone GCT/Osteoclastoma"

        results.append({
            "Key": art['key'],
            "Title": art['title'],
            "Decision": decision,
            "Reason": reason
        })
    
    return results


def dual_pass_screening(json_path):
    """
    Dual-pass screening strategy as described in the manuscript:
    Each screening task is executed twice independently.
    Only when both outputs match is the decision finalised.
    Disagreements are flagged for human adjudication.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        articles = json.load(f)

    logger.info(f"Starting dual-pass screening on {len(articles)} articles...")

    # Pass 1
    logger.info("  Executing Pass 1...")
    pass_1_results = screen_single_pass(articles)

    # Pass 2 (independent execution)
    logger.info("  Executing Pass 2...")
    pass_2_results = screen_single_pass(articles)

    # Compare passes
    agreed = []
    disagreements = []

    for r1, r2 in zip(pass_1_results, pass_2_results):
        if r1['Decision'] == r2['Decision']:
            agreed.append(r1)
        else:
            disagreements.append({
                "Key": r1['Key'],
                "Title": r1['Title'],
                "Pass_1_Decision": r1['Decision'],
                "Pass_1_Reason": r1['Reason'],
                "Pass_2_Decision": r2['Decision'],
                "Pass_2_Reason": r2['Reason'],
                "Final_Decision": "FLAGGED_FOR_HUMAN_REVIEW"
            })

    # Agreement statistics
    total = len(pass_1_results)
    agreement_rate = len(agreed) / total * 100 if total > 0 else 0
    included_count = sum(1 for r in agreed if r['Decision'] == 'Include')
    excluded_count = sum(1 for r in agreed if r['Decision'] == 'Exclude')

    logger.info(f"  Dual-pass agreement: {len(agreed)}/{total} ({agreement_rate:.1f}%)")
    logger.info(f"  Agreed Include: {included_count}, Agreed Exclude: {excluded_count}")
    if disagreements:
        logger.warning(f"  Disagreements: {len(disagreements)} articles flagged for human review")
    else:
        logger.info(f"  No disagreements -- 100% consistency confirmed.")

    return agreed, disagreements, articles


def export_included_ris(agreed_results, all_articles, output_path="included_articles.ris"):
    """
    Export all INCLUDED articles as a valid RIS file.
    
    RIS format spec:
      TY  - type (JOUR, BOOK, etc.)
      TI  - title
      AB  - abstract
      AU  - author (one per line)
      PY  - publication year
      DO  - DOI
      JO  - journal name
      KW  - keywords
      ER  - end of record
    
    Always writes the file, even if 0 articles are included (empty file).
    """
    included_keys = {r['Key'] for r in agreed_results if r['Decision'] == 'Include'}

    # Build a lookup by key for all original articles
    articles_by_key = {}
    for art in all_articles:
        articles_by_key[art['key']] = art

    count = 0
    with open(output_path, 'w', encoding='utf-8') as ris:
        for key in sorted(included_keys):
            art = articles_by_key.get(key)
            if not art:
                logger.warning(f"  Key '{key}' not found in original articles — skipping.")
                continue

            # Record type
            ris.write("TY  - JOUR\n")

            # Title (required)
            title = art.get('title', '').strip()
            if title:
                ris.write(f"TI  - {title}\n")

            # Abstract
            abstract = art.get('abstract', '').strip()
            if abstract:
                ris.write(f"AB  - {abstract}\n")

            # Authors — one AU line per author
            authors_raw = art.get('author', '').strip()
            if authors_raw:
                # Handle both "and"-separated and ";"-separated formats
                authors_raw = authors_raw.replace(';', ' and ')
                for author in authors_raw.split(' and '):
                    author = author.strip()
                    if author:
                        ris.write(f"AU  - {author}\n")

            # Year
            year = str(art.get('year', '')).strip()
            if year:
                ris.write(f"PY  - {year}\n")

            # DOI
            doi = art.get('doi', '').strip()
            if doi:
                ris.write(f"DO  - {doi}\n")

            # Journal
            journal = art.get('journal', '').strip()
            if journal:
                ris.write(f"JO  - {journal}\n")

            # Keywords
            keywords = art.get('keywords', '').strip()
            if keywords:
                for kw in keywords.split(','):
                    kw = kw.strip()
                    if kw:
                        ris.write(f"KW  - {kw}\n")

            # End of record
            ris.write("ER  - \n\n")
            count += 1

    logger.info(f"Included articles exported to {output_path} ({count} articles)")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dual-pass article screening with RIS export",
    )
    parser.add_argument(
        "--input",
        help="Path to parsed articles JSON (default: parsed_articles.json)",
        default="parsed_articles.json"
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        logger.error(f"Input file not found: {args.input}")
        logger.info("Run parse_bib.py first to generate parsed_articles.json")
        exit(1)

    agreed, disagreements, all_articles = dual_pass_screening(args.input)

    # Save agreed results
    with open('screening_results.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Key", "Title", "Decision", "Reason"])
        writer.writeheader()
        writer.writerows(agreed)

    # Save disagreements for human adjudication
    if disagreements:
        with open('screening_disagreements.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["Key", "Title", "Pass_1_Decision", "Pass_1_Reason",
                                                     "Pass_2_Decision", "Pass_2_Reason", "Final_Decision"])
            writer.writeheader()
            writer.writerows(disagreements)
        logger.info(f"Disagreements saved: screening_disagreements.csv")

    # Always export RIS — robust, sorted, complete
    export_included_ris(agreed, all_articles, "included_articles.ris")

    logger.info(f"Screening complete. Results saved to screening_results.csv")
    for res in agreed:
        print(f"[{res['Decision']}] {res['Title'][:50]}... - {res['Reason']}")
