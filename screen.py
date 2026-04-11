"""
screen.py — One-Command Systematic Review Screening Pipeline

Orchestrates the full screening workflow in a single command:
  1. Parse criteria file
  2. Generate custom screening logic via Gemini (browser or API)
  3. Parse article bibliography (.bib / .ris)
  4. Run dual-pass deterministic screening
  5. Export results (CSV + RIS)

Usage:
    python screen.py --criteria criteria.txt --articles articles.bib
    python screen.py --criteria criteria.txt --articles articles.bib --api-key KEY
    python screen.py --criteria criteria.txt --articles articles.bib --browser msedge
"""

import os
import sys
import json
import csv
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("screening_pipeline.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import internal modules
from criteria_parser import parse_criteria
from parse_bib import parse_bib
from generate_screening_code import create_gemini_prompt, generate_via_api, generate_via_browser
from generate_screening_code import validate_generated_code, create_complete_module, extract_python_code
from screen_articles import dual_pass_screening, export_included_ris


def parse_ris_file(file_path):
    """Parse a .ris file into a list of article dicts (same format as parse_bib)."""
    articles = []
    current = {}

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n').rstrip('\r')

            if line.startswith('TY  - '):
                current = {'key': '', 'title': '', 'abstract': '', 'author': '',
                           'year': '', 'doi': '', 'journal': '', 'keywords': ''}

            elif line.startswith('TI  - '):
                current['title'] = line[6:].strip()
            elif line.startswith('T1  - '):
                current['title'] = line[6:].strip()

            elif line.startswith('AB  - '):
                current['abstract'] = line[6:].strip()
            elif line.startswith('N2  - '):
                current['abstract'] = line[6:].strip()

            elif line.startswith('AU  - '):
                author = line[6:].strip()
                if current.get('author'):
                    current['author'] += ' and ' + author
                else:
                    current['author'] = author
            elif line.startswith('A1  - '):
                author = line[6:].strip()
                if current.get('author'):
                    current['author'] += ' and ' + author
                else:
                    current['author'] = author

            elif line.startswith('PY  - '):
                current['year'] = line[6:].strip()[:4]
            elif line.startswith('Y1  - '):
                current['year'] = line[6:].strip()[:4]

            elif line.startswith('DO  - '):
                current['doi'] = line[6:].strip()

            elif line.startswith('JO  - ') or line.startswith('JF  - ') or line.startswith('T2  - '):
                current['journal'] = line[6:].strip()

            elif line.startswith('KW  - '):
                kw = line[6:].strip()
                if current.get('keywords'):
                    current['keywords'] += ', ' + kw
                else:
                    current['keywords'] = kw

            elif line.startswith('ER  - '):
                # End of record — generate a key if missing
                if not current.get('key'):
                    # Create key from first author surname + year
                    first_author = current.get('author', 'unknown').split(',')[0].split(' ')[0].lower()
                    year = current.get('year', '0000')
                    current['key'] = f"{first_author}{year}_{len(articles)}"

                if current.get('title'):  # Only add if we have at least a title
                    articles.append(current)
                current = {}

    return articles


def parse_articles(file_path):
    """Auto-detect file format and parse articles."""
    ext = Path(file_path).suffix.lower()

    if ext == '.bib':
        logger.info(f"Parsing BibTeX file: {file_path}")
        return parse_bib(file_path)
    elif ext == '.ris':
        logger.info(f"Parsing RIS file: {file_path}")
        return parse_ris_file(file_path)
    elif ext == '.json':
        logger.info(f"Loading pre-parsed JSON: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        logger.error(f"Unsupported file format: {ext}")
        logger.info("Supported formats: .bib, .ris, .json")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="One-command systematic review screening pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python screen.py --criteria criteria.txt --articles articles.bib
  python screen.py --criteria criteria.txt --articles export.ris --api-key YOUR_KEY
  python screen.py --criteria criteria.txt --articles articles.bib --browser msedge
        """
    )
    parser.add_argument(
        "--criteria", required=True,
        help="Path to criteria file (.txt, .docx, or .json)"
    )
    parser.add_argument(
        "--articles", required=True,
        help="Path to articles file (.bib, .ris, or .json)"
    )
    parser.add_argument(
        "--browser",
        help="Browser channel for code generation (default: chrome)",
        default="chrome"
    )
    parser.add_argument(
        "--api-key",
        help="Gemini API key (optional — uses faster API mode instead of browser)",
        default=None
    )
    parser.add_argument(
        "--model",
        help="Gemini model name (default: gemini-2.5-flash)",
        default="gemini-2.5-flash"
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for output files (default: current directory)",
        default="."
    )
    parser.add_argument(
        "--skip-codegen",
        action="store_true",
        help="Skip code generation — use existing screen_articles.py directly"
    )
    args = parser.parse_args()

    start_time = datetime.now()

    print()
    print("=" * 70)
    print("  SYSTEMATIC REVIEW SCREENING PIPELINE")
    print("=" * 70)
    print()

    # Validate inputs
    if not os.path.exists(args.criteria):
        logger.error(f"Criteria file not found: {args.criteria}")
        sys.exit(1)
    if not os.path.exists(args.articles):
        logger.error(f"Articles file not found: {args.articles}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────
    # PHASE 1: Parse Articles
    # ──────────────────────────────────────────────
    logger.info("PHASE 1: Parsing articles...")
    articles = parse_articles(args.articles)
    logger.info(f"  Loaded {len(articles)} articles")

    if len(articles) == 0:
        logger.error("No articles found. Check your input file.")
        sys.exit(1)

    # Save parsed articles as JSON (for screening step)
    parsed_json_path = str(output_dir / "parsed_articles.json")
    with open(parsed_json_path, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    logger.info(f"  Saved to: {parsed_json_path}")

    # ──────────────────────────────────────────────
    # PHASE 2: Generate Custom Screening Logic
    # ──────────────────────────────────────────────
    custom_module_path = str(output_dir / "screen_articles_custom.py")

    if args.skip_codegen:
        logger.info("PHASE 2: Skipped (--skip-codegen)")
    else:
        logger.info("PHASE 2: Generating custom screening logic via Gemini...")

        criteria = parse_criteria(args.criteria)
        logger.info(f"  Criteria parsed: {criteria.get('description', 'N/A')[:60]}...")

        # Read reference code
        reference_code_path = Path(__file__).parent / 'screen_articles.py'
        with open(reference_code_path, 'r', encoding='utf-8') as f:
            reference_code = f.read()

        prompt = create_gemini_prompt(criteria, reference_code)
        logger.info(f"  Prompt: {len(prompt)} characters")

        if args.api_key:
            logger.info(f"  Mode: API ({args.model})")
            generated_code = generate_via_api(prompt, args.api_key, args.model)
        else:
            logger.info(f"  Mode: Browser ({args.browser})")
            generated_code = generate_via_browser(prompt, args.browser)

        if generated_code:
            complete_module = create_complete_module(generated_code, criteria, args.criteria)
            with open(custom_module_path, 'w', encoding='utf-8') as f:
                f.write(complete_module)
            logger.info(f"  Custom module saved: {custom_module_path}")
        else:
            logger.warning("  Code generation failed. Using default screening logic.")

    # ──────────────────────────────────────────────
    # PHASE 3: Dual-Pass Screening
    # ──────────────────────────────────────────────
    logger.info("PHASE 3: Running dual-pass screening...")
    agreed, disagreements, all_articles = dual_pass_screening(parsed_json_path)

    # ──────────────────────────────────────────────
    # PHASE 4: Export Results
    # ──────────────────────────────────────────────
    logger.info("PHASE 4: Exporting results...")

    # CSV — all results
    csv_path = str(output_dir / "screening_results.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Key", "Title", "Decision", "Reason"])
        writer.writeheader()
        writer.writerows(agreed)
    logger.info(f"  Results: {csv_path}")

    # CSV — disagreements
    if disagreements:
        disagree_path = str(output_dir / "screening_disagreements.csv")
        with open(disagree_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Key", "Title", "Pass_1_Decision", "Pass_1_Reason",
                "Pass_2_Decision", "Pass_2_Reason", "Final_Decision"
            ])
            writer.writeheader()
            writer.writerows(disagreements)
        logger.info(f"  Disagreements: {disagree_path}")

    # RIS — included articles
    ris_path = str(output_dir / "included_articles.ris")
    included_count = export_included_ris(agreed, all_articles, ris_path)

    # ──────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()
    total = len(agreed) + len(disagreements)
    included = sum(1 for r in agreed if r['Decision'] == 'Include')
    excluded = sum(1 for r in agreed if r['Decision'] == 'Exclude')

    print()
    print("=" * 70)
    print("  SCREENING COMPLETE")
    print("=" * 70)
    print(f"  Total articles:     {total}")
    print(f"  Included:           {included}")
    print(f"  Excluded:           {excluded}")
    print(f"  Disagreements:      {len(disagreements)}")
    print(f"  Time elapsed:       {elapsed:.1f}s")
    print()
    print(f"  Output files:")
    print(f"    screening_results.csv      ({total} rows)")
    print(f"    included_articles.ris      ({included_count} articles)")
    if disagreements:
        print(f"    screening_disagreements.csv ({len(disagreements)} flagged)")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
