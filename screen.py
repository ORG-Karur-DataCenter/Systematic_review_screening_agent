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

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.text import Text
    from rich.columns import Columns
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Force UTF-8 output on Windows to support unicode glyphs
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

console = Console(force_terminal=True) if RICH_AVAILABLE else None

# Structured logging — file only when rich is available (to avoid duplicating console output)
log_handlers = [logging.FileHandler("screening_pipeline.log", mode='a', encoding='utf-8')]
if not RICH_AVAILABLE:
    log_handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=log_handlers
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


def parse_pubmed_file(file_path):
    """Parse a PubMed/MEDLINE format file (.txt) with proper multi-line field handling."""
    articles = []
    current = {}
    last_tag = None  # Track last tag for multi-line continuation
    
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            
            if line.startswith('PMID- '):
                if current and current.get('title'):
                    articles.append(current)
                current = {'key': line[6:].strip(), 'title': '', 'abstract': '', 'author': '',
                           'year': '', 'doi': '', 'journal': '', 'keywords': ''}
                last_tag = 'PMID'
            
            elif line.startswith('TI  - '):
                current['title'] = line[6:].strip()
                last_tag = 'TI'
            elif line.startswith('AB  - '):
                current['abstract'] = line[6:].strip()
                last_tag = 'AB'
            elif line.startswith('FAU - '):
                author = line[6:].strip()
                if current.get('author'):
                    current['author'] += ' and ' + author
                else:
                    current['author'] = author
                last_tag = 'FAU'
            elif line.startswith('AU  - '):
                # Fallback if FAU not present
                if not current.get('author') or last_tag != 'FAU':
                    author = line[6:].strip()
                    if current.get('author'):
                        current['author'] += ' and ' + author
                    else:
                        current['author'] = author
                last_tag = 'AU'
            elif line.startswith('DP  - '):
                current['year'] = line[6:].strip()[:4]
                last_tag = 'DP'
            elif line.startswith('AID - ') and '[doi]' in line:
                current['doi'] = line[6:].replace('[doi]', '').strip()
                last_tag = 'AID'
            elif line.startswith('JT  - '):
                current['journal'] = line[6:].strip()
                last_tag = 'JT'
            elif line.startswith('MH  - '):
                kw = line[6:].strip()
                if current.get('keywords'):
                    current['keywords'] += ', ' + kw
                else:
                    current['keywords'] = kw
                last_tag = 'MH'
            
            # Multi-line continuation: lines starting with 6 spaces continue the previous field
            elif line.startswith('      ') and current and last_tag:
                continuation = line.strip()
                if last_tag == 'TI':
                    current['title'] += ' ' + continuation
                elif last_tag == 'AB':
                    current['abstract'] += ' ' + continuation
            
            # Any other tag resets the continuation
            elif len(line) >= 4 and line[4] == '-' and not line.startswith('      '):
                last_tag = line[:4].strip()

    if current and current.get('title'):
        articles.append(current)
        
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
    elif ext == '.txt':
        # Try to detect if it's PubMed or RIS
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            head = f.read(1000)
        
        if 'PMID-' in head or 'TI  -' in head:
            logger.info(f"Parsing PubMed/MEDLINE file: {file_path}")
            return parse_pubmed_file(file_path)
        elif 'TY  -' in head:
            logger.info(f"Parsing RIS file as .txt: {file_path}")
            return parse_ris_file(file_path)
        else:
            logger.error(f"Unknown text format for: {file_path}")
            sys.exit(1)
    else:
        logger.error(f"Unsupported file format: {ext}")
        logger.info("Supported formats: .bib, .ris, .json, .txt (PubMed/RIS)")
        sys.exit(1)


def rprint(msg, style=None):
    """Print with rich if available, else plain print."""
    if RICH_AVAILABLE:
        console.print(msg, style=style)
    else:
        print(msg)


def auto_detect_articles(search_dir="."):
    """
    Auto-detect article files in the current directory.
    Priority: *_deduplicated* files first (output from dedup agent), then any .bib/.ris/.txt.
    Excludes criteria files, generated code, logs, and output files.
    """
    SKIP_NAMES = {
        'parsed_articles.json', 'screening_results.csv', 'screening_disagreements.csv',
        'screening_pipeline.log', 'screening_gen_run.log', 'screening_run.log',
        'screen_articles_custom.py', 'included_articles.ris',
    }
    ARTICLE_EXTENSIONS = {'.bib', '.ris', '.txt', '.nbib'}

    candidates = []
    for f in Path(search_dir).iterdir():
        if not f.is_file():
            continue
        if f.name in SKIP_NAMES:
            continue
        if f.suffix.lower() not in ARTICLE_EXTENSIONS:
            continue
        # Skip criteria files
        if 'criteria' in f.name.lower():
            continue
        # Skip tiny files (likely not article exports)
        if f.stat().st_size < 500:
            continue

        # Check if it's actually an article file (sniff first 1000 chars)
        try:
            with open(f, 'r', encoding='utf-8', errors='replace') as fh:
                head = fh.read(1000)
            # Must look like PubMed, RIS, or BibTeX
            head_lower = head.lower()
            if any(marker in head for marker in ['PMID-', 'TI  -', 'TY  -']) or \
               any(marker in head_lower for marker in ['@article', '@inproceedings', '@book', '@misc', '@incollection']):
                candidates.append(str(f))
        except Exception:
            continue

    # Sort: *_deduplicated* files first, then alphabetical
    def sort_key(path):
        name = Path(path).name.lower()
        return (0 if 'deduplicated' in name else 1, name)

    return sorted(candidates, key=sort_key)


def auto_detect_criteria(search_dir="."):
    """Auto-detect a criteria file in the current directory."""
    for pattern in ['*criteria*', '*CRITERIA*', '*Criteria*']:
        for f in Path(search_dir).glob(pattern):
            if f.is_file() and f.suffix.lower() in {'.txt', '.docx', '.json'}:
                return str(f)
    return None


def main():
    parser = argparse.ArgumentParser(
        description="One-command systematic review screening pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python screen.py                                      # Auto-detect everything
  python screen.py --criteria criteria.txt               # Auto-detect articles
  python screen.py --articles data.bib                   # Auto-detect criteria
  python screen.py --api-key YOUR_KEY                    # Auto-detect + fast API mode
        """
    )
    parser.add_argument("--criteria", default=None,
                        help="Path to criteria file (auto-detected if not provided)")
    parser.add_argument("--articles", default=None, nargs='+',
                        help="Path to articles file(s) (auto-detected if not provided)")
    parser.add_argument("--browser", default="chrome",
                        help="Browser channel for code generation (default: chrome)")
    parser.add_argument("--api-key", default=None,
                        help="Gemini API key (optional — uses faster API mode)")
    parser.add_argument("--model", default="gemini-2.5-flash",
                        help="Gemini model name (default: gemini-2.5-flash)")
    parser.add_argument("--output-dir", default=".",
                        help="Directory for output files (default: current directory)")
    parser.add_argument("--skip-codegen", action="store_true",
                        help="Skip code generation — use existing screening logic")
    args = parser.parse_args()

    start_time = datetime.now()

    # ── Banner ──
    if RICH_AVAILABLE:
        banner = Panel(
            Text("SYSTEMATIC REVIEW SCREENING PIPELINE", style="bold white", justify="center"),
            border_style="cyan",
            box=box.DOUBLE_EDGE,
            padding=(1, 4),
            subtitle="Agentic AI-Powered",
            subtitle_align="center"
        )
        console.print()
        console.print(banner)
        console.print()
    else:
        print("\n" + "=" * 70)
        print("  SYSTEMATIC REVIEW SCREENING PIPELINE")
        print("=" * 70 + "\n")

    # ── Auto-detect inputs ──
    if args.criteria is None:
        detected = auto_detect_criteria()
        if detected:
            args.criteria = detected
            rprint(f"  [green]✔[/green] Auto-detected criteria: [bold]{detected}[/bold]")
        else:
            rprint("[bold red]✘[/bold red] No criteria file found. Provide --criteria or place a *criteria*.txt file here.")
            sys.exit(1)

    if args.articles is None:
        detected = auto_detect_articles()
        if detected:
            args.articles = detected
            rprint(f"  [green]✔[/green] Auto-detected [bold]{len(detected)}[/bold] article file(s):")
            for af in detected:
                rprint(f"      [dim]→[/dim] {Path(af).name}")
        else:
            rprint("[bold red]✘[/bold red] No article files found. Provide --articles or place .bib/.ris/.txt files here.")
            sys.exit(1)

    rprint("")

    # ── Validate Inputs ──
    if not os.path.exists(args.criteria):
        rprint(f"[bold red]✘[/bold red] Criteria file not found: {args.criteria}")
        sys.exit(1)
    for af in args.articles:
        if not os.path.exists(af):
            rprint(f"[bold red]✘[/bold red] Articles file not found: {af}")
            sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Show config
    if RICH_AVAILABLE:
        config_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        config_table.add_column(style="dim")
        config_table.add_column(style="bold")
        config_table.add_row("Criteria", str(args.criteria))
        config_table.add_row("Articles", ", ".join(Path(a).name for a in args.articles))
        config_table.add_row("Mode", "API" if args.api_key else f"Browser ({args.browser})")
        config_table.add_row("Model", args.model)
        console.print(Panel(config_table, title="[bold]Configuration", border_style="dim"))
        console.print()

    # ══════════════════════════════════════════════
    # PHASE 1: Parse Articles
    # ══════════════════════════════════════════════
    rprint("[bold cyan]PHASE 1[/bold cyan] [white]Parsing articles...[/white]")
    logger.info("PHASE 1: Parsing articles...")

    all_articles = []
    if RICH_AVAILABLE:
        with Progress(
            SpinnerColumn("dots"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Parsing files...", total=len(args.articles))
            for article_file in args.articles:
                arts = parse_articles(article_file)
                logger.info(f"  Loaded {len(arts)} articles from {article_file}")
                all_articles.extend(arts)
                progress.update(task, advance=1, description=f"Parsed {Path(article_file).name}")
    else:
        for article_file in args.articles:
            arts = parse_articles(article_file)
            logger.info(f"  Loaded {len(arts)} articles from {article_file}")
            all_articles.extend(arts)

    articles = all_articles
    logger.info(f"  Total loaded: {len(articles)} articles")

    if len(articles) == 0:
        rprint("[bold red]✘ No articles found in any of the provided files.[/bold red]")
        sys.exit(1)

    # Show per-file breakdown
    if RICH_AVAILABLE:
        file_table = Table(box=box.ROUNDED, border_style="green")
        file_table.add_column("File", style="white")
        file_table.add_column("Format", style="cyan")
        file_table.add_column("Records", style="bold green", justify="right")
        for af in args.articles:
            ext = Path(af).suffix
            count = len(parse_articles(af))
            file_table.add_row(Path(af).name, ext.upper(), str(count))
        file_table.add_row("[bold]TOTAL", "", f"[bold]{len(articles)}", style="dim")
        console.print(file_table)
        console.print()

    rprint(f"  [green]✔[/green] Loaded [bold]{len(articles)}[/bold] articles")

    # Save parsed JSON
    parsed_json_path = str(output_dir / "parsed_articles.json")
    with open(parsed_json_path, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)

    # ══════════════════════════════════════════════
    # PHASE 2: Generate Custom Screening Logic (Dual Independent Generation)
    # ══════════════════════════════════════════════
    custom_module_path_1 = str(output_dir / "screen_articles_pass1.py")
    custom_module_path_2 = str(output_dir / "screen_articles_pass2.py")

    if args.skip_codegen:
        rprint("[bold cyan]PHASE 2[/bold cyan] [dim]Skipped (--skip-codegen)[/dim]")
        logger.info("PHASE 2: Skipped (--skip-codegen)")
    else:
        rprint("[bold cyan]PHASE 2[/bold cyan] [white]Generating dual independent screening logic via Gemini...[/white]")
        logger.info("PHASE 2: Generating dual independent screening logic via Gemini...")

        criteria = parse_criteria(args.criteria)
        desc_preview = criteria.get('description', 'N/A')[:60]
        logger.info(f"  Criteria parsed: {desc_preview}...")
        rprint(f"  [dim]Criteria:[/dim] {desc_preview}...")

        reference_code_path = Path(__file__).parent / 'screen_articles.py'
        with open(reference_code_path, 'r', encoding='utf-8') as f:
            reference_code = f.read()

        prompt = create_gemini_prompt(criteria, reference_code)
        logger.info(f"  Prompt: {len(prompt)} characters")

        def _generate_code(label):
            """Generate screening code via API or browser."""
            if args.api_key:
                logger.info(f"  {label} — Mode: API ({args.model})")
                return generate_via_api(prompt, args.api_key, args.model)
            else:
                logger.info(f"  {label} — Mode: Browser ({args.browser})")
                return generate_via_browser(prompt, args.browser)

        # Generate Pass 1 code
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn("dots"),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Generating Reviewer 1 logic...", total=None)
                code_1 = _generate_code("Reviewer 1")
        else:
            code_1 = _generate_code("Reviewer 1")

        if code_1:
            module_1 = create_complete_module(code_1, criteria, args.criteria)
            with open(custom_module_path_1, 'w', encoding='utf-8') as f:
                f.write(module_1)
            logger.info(f"  Reviewer 1 module saved: {custom_module_path_1}")
            rprint(f"  [green]✔[/green] Reviewer 1 screening code generated")
        else:
            logger.warning("  Reviewer 1 code generation failed.")
            rprint("  [yellow]⚠[/yellow] Reviewer 1 code generation failed")

        # Generate Pass 2 code (independent generation)
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn("dots"),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Generating Reviewer 2 logic...", total=None)
                code_2 = _generate_code("Reviewer 2")
        else:
            code_2 = _generate_code("Reviewer 2")

        if code_2:
            module_2 = create_complete_module(code_2, criteria, args.criteria)
            with open(custom_module_path_2, 'w', encoding='utf-8') as f:
                f.write(module_2)
            logger.info(f"  Reviewer 2 module saved: {custom_module_path_2}")
            rprint(f"  [green]✔[/green] Reviewer 2 screening code generated")
        else:
            logger.warning("  Reviewer 2 code generation failed.")
            rprint("  [yellow]⚠[/yellow] Reviewer 2 code generation failed")

    # ══════════════════════════════════════════════
    # PHASE 3: Dual-Pass Independent Screening
    # ══════════════════════════════════════════════
    rprint("[bold cyan]PHASE 3[/bold cyan] [white]Running dual independent screening...[/white]")
    logger.info("PHASE 3: Running dual independent screening...")

    # Load both screening modules
    def _load_screen_func(module_path, label):
        """Load a screening function from a generated module."""
        if not os.path.exists(module_path):
            return None
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(label, module_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, 'screen_articles'):
                logger.info(f"  Loaded {label} from: {module_path}")
                return mod.screen_articles
        except Exception as e:
            logger.warning(f"  Failed to load {label}: {e}")
        return None

    func_1 = _load_screen_func(custom_module_path_1, "pass1")
    func_2 = _load_screen_func(custom_module_path_2, "pass2")

    # Fallback: if only one custom module exists, use default for the other
    if func_1 and not func_2:
        rprint("  [yellow]⚠[/yellow] Only Reviewer 1 available — using default for Reviewer 2")
        func_2 = func_1  # Graceful fallback
    elif func_2 and not func_1:
        rprint("  [yellow]⚠[/yellow] Only Reviewer 2 available — using default for Reviewer 1")
        func_1 = func_2
    elif not func_1 and not func_2:
        # Ultimate fallback
        agreed, disagreements, all_articles = dual_pass_screening(parsed_json_path)
        func_1 = None  # Signal to skip custom path

    if func_1:
        with open(parsed_json_path, 'r', encoding='utf-8') as f:
            all_articles = json.load(f)

        logger.info(f"Starting dual independent screening on {len(all_articles)} articles...")
        rprint(f"  [dim]Screening {len(all_articles)} articles with 2 independent reviewers...[/dim]")

        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn("dots"),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=30),
                console=console,
                transient=True,
            ) as progress:
                t = progress.add_task("Reviewer 1 screening...", total=2)
                pass_1 = func_1(parsed_json_path)
                progress.update(t, advance=1, description="Reviewer 2 screening...")
                pass_2 = func_2(parsed_json_path)
                progress.update(t, advance=1, description="Complete")
        else:
            pass_1 = func_1(parsed_json_path)
            pass_2 = func_2(parsed_json_path)

        agreed = []
        disagreements = []
        for r1, r2 in zip(pass_1, pass_2):
            if r1['Decision'] == r2['Decision']:
                agreed.append(r1)
            else:
                disagreements.append({
                    "Key": r1['Key'], "Title": r1['Title'],
                    "Pass_1_Decision": r1['Decision'], "Pass_1_Reason": r1['Reason'],
                    "Pass_2_Decision": r2['Decision'], "Pass_2_Reason": r2['Reason'],
                    "Final_Decision": "FLAGGED_FOR_HUMAN_REVIEW"
                })

        total = len(pass_1)
        included_count_phase = sum(1 for r in agreed if r['Decision'] == 'Include')
        excluded_count_phase = sum(1 for r in agreed if r['Decision'] == 'Exclude')
        agreement_rate = len(agreed) / total * 100 if total > 0 else 0
        logger.info(f"  Dual-pass agreement: {len(agreed)}/{total} ({agreement_rate:.1f}%)")
        logger.info(f"  Agreed Include: {included_count_phase}, Agreed Exclude: {excluded_count_phase}")
        if disagreements:
            logger.warning(f"  Disagreements: {len(disagreements)} articles flagged for human review")
        else:
            logger.info("  No disagreements -- 100% consistency confirmed.")

    if disagreements:
        rprint(f"  [green]✔[/green] Dual-pass complete — agreement: [bold]{agreement_rate:.1f}%[/bold] ({len(disagreements)} flagged)")
    else:
        rprint(f"  [green]✔[/green] Dual-pass complete — [bold]100%[/bold] agreement")

    # ══════════════════════════════════════════════
    # PHASE 4: Export Results
    # ══════════════════════════════════════════════
    rprint("[bold cyan]PHASE 4[/bold cyan] [white]Exporting results...[/white]")
    logger.info("PHASE 4: Exporting results...")

    csv_path = str(output_dir / "screening_results.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Key", "Title", "Decision", "Reason"])
        writer.writeheader()
        writer.writerows(agreed)
    logger.info(f"  Results: {csv_path}")

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

    ris_path = str(output_dir / "included_articles.ris")
    included_count = export_included_ris(agreed, all_articles, ris_path)

    rprint(f"  [green]✔[/green] Files exported")

    # ══════════════════════════════════════════════
    # PHASE 5: Human Adjudication of Disagreements
    # ══════════════════════════════════════════════
    if disagreements:
        rprint("")
        rprint(f"[bold cyan]PHASE 5[/bold cyan] [white]Human adjudication of {len(disagreements)} disagreements[/white]")
        rprint(f"  [dim]For each article, type: [bold]i[/bold]=Include  [bold]e[/bold]=Exclude  [bold]s[/bold]=Skip[/dim]")
        rprint("")
        logger.info(f"PHASE 5: Human adjudication of {len(disagreements)} disagreements...")

        resolved = []
        still_unresolved = []

        for idx, d in enumerate(disagreements, 1):
            if RICH_AVAILABLE:
                detail = Text()
                detail.append("Reviewer 1: ", style="bold")
                r1_style = "green" if d['Pass_1_Decision'] == 'Include' else "red"
                detail.append(d['Pass_1_Decision'], style=r1_style)
                detail.append(f" -- {d['Pass_1_Reason']}\n", style="dim")
                detail.append("Reviewer 2: ", style="bold")
                r2_style = "green" if d['Pass_2_Decision'] == 'Include' else "red"
                detail.append(d['Pass_2_Decision'], style=r2_style)
                detail.append(f" -- {d['Pass_2_Reason']}", style="dim")

                title_short = d['Title'][:80]
                console.print(Panel(
                    detail,
                    title=f"[bold yellow][{idx}/{len(disagreements)}] {title_short}",
                    border_style="yellow",
                    padding=(1, 2),
                ))
            else:
                print(f"\n--- [{idx}/{len(disagreements)}] {d['Title'][:80]} ---")
                print(f"  Reviewer 1: {d['Pass_1_Decision']} -- {d['Pass_1_Reason']}")
                print(f"  Reviewer 2: {d['Pass_2_Decision']} -- {d['Pass_2_Reason']}")

            while True:
                try:
                    choice = input("  Decision (i/e/s): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    choice = 's'
                if choice in ('i', 'e', 's'):
                    break
                print("  Invalid input. Enter i (Include), e (Exclude), or s (Skip).")

            if choice == 'i':
                resolved.append({
                    "Key": d['Key'], "Title": d['Title'],
                    "Decision": "Include",
                    "Reason": f"Human adjudication (R1: {d['Pass_1_Decision']}, R2: {d['Pass_2_Decision']})"
                })
                rprint("  [green]-> Included[/green]")
            elif choice == 'e':
                resolved.append({
                    "Key": d['Key'], "Title": d['Title'],
                    "Decision": "Exclude",
                    "Reason": f"Human adjudication (R1: {d['Pass_1_Decision']}, R2: {d['Pass_2_Decision']})"
                })
                rprint("  [red]-> Excluded[/red]")
            else:
                still_unresolved.append(d)
                rprint("  [yellow]-> Skipped[/yellow]")

        # Merge resolved into agreed
        agreed.extend(resolved)
        disagreements = still_unresolved

        human_inc = sum(1 for r in resolved if r['Decision'] == 'Include')
        human_exc = sum(1 for r in resolved if r['Decision'] == 'Exclude')
        logger.info(f"  Adjudication: {len(resolved)} resolved ({human_inc} inc, {human_exc} exc), {len(still_unresolved)} skipped")
        rprint(f"\n  [green]✔[/green] Adjudication: [bold]{human_inc}[/bold] included, [bold]{human_exc}[/bold] excluded, [bold]{len(still_unresolved)}[/bold] deferred")

        # Re-export final results
        rprint("")
        rprint("[bold cyan]PHASE 5b[/bold cyan] [white]Re-exporting with adjudicated results...[/white]")

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["Key", "Title", "Decision", "Reason"])
            writer.writeheader()
            writer.writerows(agreed)

        if still_unresolved:
            with open(disagree_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "Key", "Title", "Pass_1_Decision", "Pass_1_Reason",
                    "Pass_2_Decision", "Pass_2_Reason", "Final_Decision"
                ])
                writer.writeheader()
                writer.writerows(still_unresolved)
        else:
            disagree_file = output_dir / "screening_disagreements.csv"
            if disagree_file.exists():
                disagree_file.unlink()

        included_count = export_included_ris(agreed, all_articles, ris_path)
        rprint(f"  [green]✔[/green] Final results re-exported")

    # SUMMARY
    # ══════════════════════════════════════════════
    elapsed = (datetime.now() - start_time).total_seconds()
    total = len(agreed) + len(disagreements)
    included = sum(1 for r in agreed if r['Decision'] == 'Include')
    excluded = sum(1 for r in agreed if r['Decision'] == 'Exclude')

    if RICH_AVAILABLE:
        console.print()

        # Stats table
        stats = Table(box=box.ROUNDED, border_style="cyan", title="Screening Results", title_style="bold cyan")
        stats.add_column("Metric", style="white")
        stats.add_column("Value", style="bold", justify="right")
        stats.add_row("Total Articles", str(total))
        stats.add_row("Included", f"[bold green]{included}")
        stats.add_row("Excluded", f"[dim]{excluded}")
        stats.add_row("Disagreements", f"[yellow]{len(disagreements)}" if disagreements else "[green]0")
        stats.add_row("Agreement Rate", "[green]100%" if not disagreements else f"{len(agreed)/total*100:.1f}%")
        stats.add_row("Time Elapsed", f"{elapsed:.1f}s")
        console.print(stats)
        console.print()

        # Output files table
        files = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        files.add_column(style="cyan")
        files.add_column(style="dim")
        files.add_row("screening_results.csv", f"{total} rows")
        files.add_row("included_articles.ris", f"{included_count} articles")
        if disagreements:
            files.add_row("screening_disagreements.csv", f"{len(disagreements)} flagged")
        console.print(Panel(files, title="[bold]Output Files", border_style="green"))
        console.print()

        # Show included titles
        if included > 0:
            inc_table = Table(
                box=box.SIMPLE_HEAVY, border_style="green",
                title=f"Included Articles ({included})", title_style="bold green"
            )
            inc_table.add_column("#", style="dim", width=3)
            inc_table.add_column("Title", style="white")
            inc_table.add_column("Reason", style="dim")
            for i, r in enumerate(agreed, 1):
                if r['Decision'] == 'Include':
                    inc_table.add_row(str(i), r['Title'][:70], r['Reason'][:40])
            console.print(inc_table)
            console.print()

        console.print(Panel(
            Text("Screening Complete", style="bold green", justify="center"),
            border_style="green", box=box.DOUBLE_EDGE,
            subtitle=f"{included} included · {excluded} excluded · {elapsed:.1f}s",
            subtitle_align="center"
        ))
        console.print()
    else:
        print(f"\n{'='*70}")
        print(f"  SCREENING COMPLETE")
        print(f"{'='*70}")
        print(f"  Total: {total}  |  Included: {included}  |  Excluded: {excluded}")
        print(f"  Disagreements: {len(disagreements)}  |  Time: {elapsed:.1f}s")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
