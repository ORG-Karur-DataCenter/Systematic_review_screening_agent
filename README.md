<p align="center">
  <h1 align="center">Systematic Review Screening Agent</h1>
  <p align="center">
    AI-powered title &amp; abstract screening for systematic reviews.<br>
    Dual independent AI reviewers. Disagreements exported for human adjudication.<br>
    Zero-config. One command.
  </p>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#output">Output</a> •
  <a href="#criteria-file-format">Criteria Format</a> •
  <a href="#advanced">Advanced</a> •
  <a href="#contributing">Contributing</a>
</p>

---

> Part of the **Agentic AI-Powered Systematic Review Pipeline**
>
> [Deduplication Agent](https://github.com/ORG-Karur-DataCenter/Systematic_review_DeDuplication_agent) →
> **Screening Agent** →
> [Extraction Agent](https://github.com/ORG-Karur-DataCenter/Systematic_review_extraction_agent) →
> [Validation Agent](https://github.com/ORG-Karur-DataCenter/Sys_review_extraction_validation_agent)

---

## 🌐 Web Interface — No Installation Required

A fully browser-based version of this screening agent is available on GitHub Pages:

**👉 [Launch Web Screening App](https://org-karur-datacenter.github.io/sr-screen-app/)**

### How It Works (Web Version)

1. **Upload** your `.bib`, `.ris`, `.txt`, or `.nbib` article files
2. **Enter** your inclusion/exclusion criteria
3. **Paste** your free [Gemini API key](https://aistudio.google.com/app/apikey)
4. **Click Run** — the app makes **one single API call** to generate a custom screening logic engine from your criteria, then **screens all articles instantly in your browser** with zero further API usage

### Key Features

| Feature | Detail |
|---------|--------|
| **Single API call** | AI generates a Javascript screening engine once; all articles evaluated locally |
| **No rate limits** | After the initial logic generation, screening is 100% offline and instant |
| **No installation** | Runs entirely in your browser — no Python, no dependencies |
| **Privacy** | API key stored only in your browser's localStorage, never sent to any server |
| **Export** | Download results as CSV, audit logs, and RIS files for import into EndNote/Zotero |

> **Source code:** [sr-screen-app repository](https://github.com/ORG-Karur-DataCenter/sr-screen-app)

---

## Quickstart

### 1. Install

```bash
git clone https://github.com/ORG-Karur-DataCenter/Systematic_review_screening_agent.git
cd Systematic_review_screening_agent
pip install -r requirements.txt
playwright install chromium
```

### 2. Prepare Your Inputs

Place your files in the working directory:

| File | Description | Formats |
|------|-------------|---------|
| **Criteria file** | Your inclusion/exclusion criteria | `.txt`, `.docx`, `.json` |
| **Article files** | Exported bibliographies from database searches | `.bib`, `.ris`, `.txt` (PubMed/MEDLINE), `.nbib` |

### 3. Run

```bash
# Zero-config — auto-detects criteria and article files
python screen.py

# Or specify files explicitly
python screen.py --criteria my_criteria.txt --articles pubmed.txt scopus.bib wos.bib
```

A browser opens, Gemini generates **two independent screening algorithms**, articles are screened by both, and results are exported — all in one command.

#### Want it faster? Add your Gemini API key:

```bash
python screen.py --api-key YOUR_KEY
```

No browser needed.

---

## How It Works

```
                    ┌──────────────────────────────┐
                    │     screen.py (orchestrator)  │
                    └──────────┬───────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
    ┌──────────┐     ┌─────────────────┐     ┌──────────────┐
    │ Phase 1  │     │    Phase 2      │     │   Phase 3    │
    │ Parse    │     │ Generate dual   │     │  Dual indep. │
    │ articles │     │ independent     │     │  screening + │
    │ .bib/.ris│     │ screening logic │     │  compare     │
    │ .txt/.nbib     │ via Gemini AI   │     │  decisions   │
    │ → JSON   │     │ (Reviewer 1 + 2)│     │              │
    └──────────┘     └─────────────────┘     └──────┬───────┘
                                                    │
                            ┌───────────────────────┼──────────┐
                            ▼                       ▼          ▼
                     ┌────────────┐        ┌────────────┐  ┌────────────┐
                     │  Phase 4   │        │  Phase 5   │  │  Phase 5   │
                     │  Export    │        │  Export     │  │  (no       │
                     │  agreed    │        │  disagree-  │  │  disagree- │
                     │  results   │        │  ments as   │  │  ments)    │
                     │  CSV + RIS │        │  RIS for    │  │            │
                     │            │        │  manual     │  │            │
                     └────────────┘        │  review     │  └────────────┘
                                           └────────────┘
```

### Phase 1 — Parse Articles (Auto-Detection)

- **Auto-detects** all article files in the working directory (prioritizes `*_deduplicated*` files from the Deduplication Agent)
- Reads `.bib` (BibTeX), `.ris` (RIS), `.txt`/`.nbib` (PubMed/MEDLINE) formats
- Supports case-insensitive BibTeX entries (`@ARTICLE`, `@Article`, `@article`) for compatibility with PubMed, Scopus, and Web of Science exports
- Extracts title, abstract, authors, year, DOI, and journal from each record

### Phase 2 — Generate Dual Independent Screening Logic

Two **independent** calls to Gemini generate **two separate screening algorithms** ("Reviewer 1" and "Reviewer 2"):

- Each generation produces a self-contained Python function with:
  - Hierarchical decision trees
  - Title vs abstract weighting
  - Contextual exception handling
  - Complex boolean logic for competing diagnoses
- Both algorithms are validated for syntax before use
- Saved as `screen_articles_pass1.py` and `screen_articles_pass2.py` for full auditability

> **Why two generations?** Just like two human reviewers interpret inclusion/exclusion criteria independently, each AI generation interprets the criteria slightly differently — producing genuinely independent screening decisions.

### Phase 3 — Dual Independent Screening

Both screening algorithms are executed on the **same** article dataset:

- **Both agree → decision finalised** (Include or Exclude)
- **Disagree → flagged for human review**

This produces a **meaningful inter-rater agreement rate** (not an artificial 100%), directly analogous to the dual-reviewer workflow in traditional systematic reviews.

### Phase 4 — Export Agreed Results

- `screening_results.csv` — all agreed decisions with reasoning
- `included_articles.ris` — agreed included articles (for import into EndNote/Zotero/Rayyan)
- `screening_disagreements.csv` — disagreement details with both reviewers' reasoning

### Phase 5 — Export Disagreements for Manual Review

- `disagreements_for_review.ris` — all disagreed articles exported as a standard RIS file
- Import directly into **EndNote**, **Zotero**, **Rayyan**, or **Covidence** for manual screening
- Each record is tagged with `KW  - AI_DISAGREEMENT` for easy identification

---

## Criteria File Format

### Free-Text Format (`.txt`) — Recommended

Write your criteria as natural language. No special headers required:

```
The inclusion criteria for the systematic review are as follows:
- Randomised controlled trials (RCTs) comparing cervical disc arthroplasty (CDA) versus ACDF
- Studies reporting clinical outcomes (NDI, VAS, SF-36)
- Adult patients with single or multi-level cervical disc disease

Exclusion criteria:
- Non-comparative studies, case reports, reviews, meta-analyses
- Cadaveric, biomechanical, or in vitro studies
- Paediatric populations
```

### Structured Format (`.txt`)

```
[DESCRIPTION]
Screening for RCTs comparing cervical disc arthroplasty vs ACDF

[INCLUSION_KEYWORDS]
Primary Topic: Cervical Disc Arthroplasty, CDA, Artificial Disc
Comparison: ACDF, Anterior Cervical Discectomy

[EXCLUSION_KEYWORDS]
Study Types: Systematic Review, Meta-Analysis, Case Report
Non-Clinical: Cadaveric, Biomechanical, In Vitro
```

### JSON Format (`.json`)

```json
{
  "description": "Screening for RCTs: CDA vs ACDF",
  "inclusion": {
    "interventions": ["cervical disc arthroplasty", "CDA", "total disc replacement"],
    "comparison": ["ACDF", "anterior cervical discectomy and fusion"]
  },
  "exclusion": {
    "study_types": ["Systematic Review", "Meta-Analysis", "Case Report"],
    "non_clinical": ["Cadaveric", "Biomechanical"]
  }
}
```

---

## Output

### `screening_results.csv`

| Key | Title | Decision | Reason |
|-----|-------|----------|--------|
| Davis2023 | Five-year outcomes of CDA versus ACDF... | Include | RCT comparing CDA vs ACDF with clinical outcomes |
| Lee2021 | Biomechanical analysis of cervical spine... | Exclude | Non-clinical biomechanical study |

### `included_articles.ris`

```
TY  - JOUR
TI  - Five-year outcomes of CDA versus ACDF: a randomised trial
AB  - We report a prospective randomised controlled trial...
AU  - Davis, R.J.
PY  - 2023
DO  - 10.1016/j.spinee.2023.01.005
JO  - The Spine Journal
ER  -
```

Compatible with EndNote, Zotero, Mendeley, Rayyan, and Covidence.

### `disagreements_for_review.ris`

Same RIS format — contains only articles where the two AI reviewers disagreed. Import into your reference manager for manual screening.

### `screening_disagreements.csv`

| Key | Title | Pass_1_Decision | Pass_1_Reason | Pass_2_Decision | Pass_2_Reason |
|-----|-------|----------------|---------------|----------------|---------------|
| Kim2019 | Cervical arthroplasty outcomes... | Include | CDA outcome study | Exclude | No direct ACDF comparison |

---

## Advanced

### Command-Line Options

```
python screen.py --help

Options:
  --criteria FILE       Path to criteria file (.txt, .docx, .json)    [auto-detected]
  --articles FILE(s)    Path(s) to article files (.bib, .ris, .txt)   [auto-detected]
  --browser CHANNEL     Browser for code generation (chrome, msedge)  [default: chrome]
  --api-key KEY         Gemini API key (optional, faster than browser)
  --model NAME          Gemini model (default: gemini-2.5-flash)
  --output-dir DIR      Output directory (default: current directory)
  --skip-codegen        Skip AI code generation, reuse existing screening logic
```

### Auto-Detection

When run without arguments, the agent automatically:

1. **Criteria**: Finds any file matching `*criteria*` (`.txt`, `.docx`, `.json`)
2. **Articles**: Scans for `.bib`, `.ris`, `.txt`, `.nbib` files and validates their content headers
3. **Priority**: Prefers files with `_deduplicated` in the name (output from the Deduplication Agent)
4. **Safety**: Skips output files (`screening_results.csv`, `included_articles.ris`, etc.)

### Modes

| Mode | Command | Speed | Cost |
|------|---------|-------|------|
| **Browser** (default) | `python screen.py` | ~3 min | Free |
| **API** (optional) | `python screen.py --api-key KEY` | ~60 sec | Free tier |

### Reproducibility Workflow

For systematic review publication, follow this workflow:

```bash
# Step 1: Generate screening logic + screen (first run)
python screen.py

# Step 2: Review generated algorithms
#   → screen_articles_pass1.py (Reviewer 1 logic)
#   → screen_articles_pass2.py (Reviewer 2 logic)

# Step 3: For subsequent runs with the SAME locked logic:
python screen.py --skip-codegen

# Step 4: Resolve disagreements manually
#   → Import disagreements_for_review.ris into EndNote/Rayyan
```

> **Note:** Each code generation produces a unique screening algorithm. Using `--skip-codegen` ensures identical results across runs by reusing the previously generated algorithms.

### Using Individual Scripts

For step-by-step control:

```bash
# Step 1: Generate screening code
python generate_screening_code.py criteria.txt --api-key KEY

# Step 2: Parse articles
python parse_bib.py

# Step 3: Run screening
python screen_articles.py
```

---

## Project Structure

```
screening_agent/
├── screen.py                      # One-command pipeline orchestrator
├── generate_screening_code.py     # AI code generator (API + browser)
├── screen_articles.py             # Core screening engine + RIS export
├── criteria_parser.py             # Criteria file parser (structured + free-text)
├── parse_bib.py                   # BibTeX parser (PubMed, Scopus, WoS)
├── config.py                      # Configuration
├── requirements.txt               # Dependencies
├── LICENSE                        # MIT License
└── examples/
    ├── example_criteria.txt
    └── example_criteria.json
```

### Generated at Runtime

```
├── screen_articles_pass1.py       # AI Reviewer 1 screening logic (auditable)
├── screen_articles_pass2.py       # AI Reviewer 2 screening logic (auditable)
├── parsed_articles.json           # Parsed articles in JSON format
├── screening_results.csv          # Agreed decisions
├── screening_disagreements.csv    # Disagreement details
├── included_articles.ris          # Agreed included articles (RIS)
├── disagreements_for_review.ris   # Disagreements for manual screening (RIS)
└── screening_pipeline.log         # Full execution log
```

---

## API Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `temperature` | `0.2` | Low variance, focused output |
| `max_output_tokens` | `16384` | Room for generated screening code |
| Model | `gemini-2.5-flash` | Fast, capable |

---

## Methodology

This agent implements the dual-pass screening strategy described in the manuscript:

> *"The screening agent applied inclusion and exclusion criteria to titles and abstracts. A dual-pass strategy was employed to ensure consistency in the AI decisions for screening, where each screening task was executed twice independently. Only when both outputs matched was the decision finalised."*

The implementation generates **two independent screening algorithms** via separate LLM calls, analogous to two human reviewers independently interpreting the same inclusion/exclusion criteria. This produces a meaningful agreement rate and identifies articles requiring human adjudication.

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Built for systematic reviewers. Dual AI reviewers. Human oversight for disagreements.</sub>
</p>
