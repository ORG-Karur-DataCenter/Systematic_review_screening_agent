# Systematic Review Screening Agent

An AI-powered dual-pass title-and-abstract screening tool for systematic reviews. Generates custom screening logic from your research criteria using Google Gemini — runs free via browser automation (no API key required) or fast via API key.

Part of the **Agentic AI-Powered Systematic Review Pipeline** described in:
> *"Agentic AI for Systematic Reviews: A Four-Agent Pipeline for Deduplication, Screening, Extraction, and Validation"*

**Related Repositories:**
- [Deduplication Agent](https://github.com/ORG-Karur-DataCenter/Systematic_review_DeDuplication_agent)
- [Extraction Agent](https://github.com/ORG-Karur-DataCenter/Systematic_review_extraction_agent)
- [Validation & Healing Agent](https://github.com/ORG-Karur-DataCenter/Sys_review_extraction_validation_agent)

---

## Features

- **AI-powered criteria parsing** — converts free-text or structured criteria into screening logic via Gemini
- **Dual-pass screening** — two independent passes per article; disagreements are flagged for human review
- **Multiple input formats** — `.txt`, `.docx`, `.json` criteria files; `.bib`, `.ris` article files
- **Detailed reasoning** — every include/exclude decision includes an explanation
- **PRISMA-ready output** — CSV files compatible with PRISMA flow documentation
- **Free by default** — uses Playwright browser automation (log in to Gemini once, no API costs)
- **API mode** — use `--api-key` for faster batch processing

---

## Installation

```bash
git clone https://github.com/ORG-Karur-DataCenter/Systematic_review_screening_agent.git
cd Systematic_review_screening_agent
pip install -r requirements.txt
playwright install chromium
```

---

## Usage

### Step 1: Define Your Criteria

Create a criteria file (`my_criteria.txt`):

```
[DESCRIPTION]
Screening for RCTs comparing cervical disc arthroplasty vs ACDF

[INCLUSION_KEYWORDS]
Intervention: Cervical disc arthroplasty, CDA, Total disc replacement
Comparator: ACDF, Anterior cervical discectomy and fusion
Study Type: Randomized controlled trial, RCT

[EXCLUSION_KEYWORDS]
Study Types: Systematic Review, Meta-Analysis, Case Report
Conditions: Lumbar, Thoracic, Infection, Tumor
```

### Step 2: Generate Custom Screening Logic

```bash
python generate_screening_code.py my_criteria.txt
```

- Browser opens to gemini.google.com (log in once)
- Gemini generates a custom `screen_articles_custom.py`
- Screening logic is tailored to your exact criteria

### Step 3: Prepare Articles

Place your BibTeX or RIS export in the project folder as `articles.bib` (or `articles.ris`).

### Step 4: Parse and Screen

```bash
python parse_bib.py                    # Parse BibTeX to JSON
python screen_articles_custom.py       # Run dual-pass screening
```

### Step 5: Review Results

Open `screening_results.csv`:
| Field | Description |
|---|---|
| `title` | Article title |
| `decision` | Include / Exclude |
| `pass1_decision` | First screener decision |
| `pass2_decision` | Second screener decision |
| `agreement` | True/False |
| `reason` | Explanation |

---

## Project Structure

```
screening_agent/
├── screen_articles.py           # Core screening engine (with hardcoded reference criteria)
├── generate_screening_code.py   # AI-powered custom logic generator
├── criteria_parser.py           # Criteria file parser (.txt/.json/.docx)
├── parse_bib.py                 # BibTeX/RIS parser
├── config.py                    # Configuration (model, thresholds)
├── QUICKSTART.md                # 5-minute quickstart guide
├── requirements.txt             # Python dependencies
├── LICENSE                      # MIT License
└── examples/
    ├── example_criteria.txt
    └── example_criteria.json
```

---

## Dual-Pass Screening Logic

```
Article → Pass 1 (Gemini) → Include/Exclude + Reason
        → Pass 2 (Gemini) → Include/Exclude + Reason
        → Agreement Check:
              Both Include → INCLUDE
              Both Exclude → EXCLUDE
              Disagree     → FLAG FOR HUMAN REVIEW
```

---

## Configuration

Edit `config.py` to set:
- `MODEL_NAME` — Gemini model (`gemini-2.0-flash`, `gemini-2.5-flash`, etc.)
- `TEMPERATURE` — Reproducibility setting (default: `0.2`)
- `AGREEMENT_THRESHOLD` — Fuzzy match threshold for decisions

---

## Important Notes

- **First-time browser login**: Browser profile is saved; subsequent runs are fully automatic
- **Always review**: AI screening assists but does not replace expert judgment
- **Rate limits**: Free tier allows ~5 requests/min; use `--api-key` with multiple keys for bulk runs
- **Reproducibility**: `temperature=0.2` ensures deterministic outputs at `max_output_tokens=2048`

---

## License

MIT License — see [LICENSE](LICENSE) for details.
