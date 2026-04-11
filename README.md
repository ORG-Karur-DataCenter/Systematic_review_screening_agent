# Systematic Review Screening Agent

An AI-powered dual-pass title-and-abstract screening tool for systematic reviews. Generates custom screening logic from your research criteria using Google Gemini — runs fast via API key or free via browser automation.

Part of the **Agentic AI-Powered Systematic Review Pipeline** described in:
> *"Agentic AI for Systematic Reviews: A Four-Agent Pipeline for Deduplication, Screening, Extraction, and Validation"*

**Related Repositories:**
- [Deduplication Agent](https://github.com/ORG-Karur-DataCenter/Systematic_review_DeDuplication_agent)
- [Extraction Agent](https://github.com/ORG-Karur-DataCenter/Systematic_review_extraction_agent)
- [Validation & Healing Agent](https://github.com/ORG-Karur-DataCenter/Sys_review_extraction_validation_agent)

---

## Features

- **AI-powered code generation** — converts your criteria into a custom screening function via Gemini
- **Dual mode**: API (fast, single key) or Browser (free, no API key)
- **Dual-pass screening** — two independent passes per article; disagreements flagged for human review
- **Multiple input formats** — `.txt`, `.docx`, `.json` criteria files; `.bib` article files
- **Detailed reasoning** — every include/exclude decision includes an explanation
- **PRISMA-ready output** — CSV results + RIS export of included articles
- **Robust RIS export** — `included_articles.ris` generated every run with valid format (TY, TI, AB, AU, PY, DO, JO, ER tags)

---

## Installation

```bash
git clone https://github.com/ORG-Karur-DataCenter/Systematic_review_screening_agent.git
cd Systematic_review_screening_agent
pip install -r requirements.txt
playwright install chromium   # Only needed for browser mode
```

---

## Usage

### Step 1: Define Your Criteria

Create a criteria file (`my_criteria.txt`):

```
[DESCRIPTION]
Screening for studies on Giant Cell Tumor in the Cervical Spine

[INCLUSION_KEYWORDS]
Primary Topic: Giant Cell Tumor, Osteoclastoma
Anatomical Location: Cervical, C1, C2, C3, C4, C5, C6, C7

[EXCLUSION_KEYWORDS]
Study Types: Systematic Review, Meta-Analysis
Competing Diagnoses: Osteoblastoma, Chordoma, Lymphoma
Non-Bone Types: Synovial, Tenosynovial
```

### Step 2: Generate Custom Screening Logic

**API mode (fast, recommended — single key only):**
```bash
python generate_screening_code.py my_criteria.txt --api-key YOUR_GEMINI_KEY
```

**Browser mode (free, no API key):**
```bash
python generate_screening_code.py my_criteria.txt --browser chrome
```

This generates `screen_articles_custom.py` — a complete, validated Python module tailored to your criteria.

### Step 3: Prepare Articles

Place your BibTeX export in the project folder as `articles.bib`:
```bash
python parse_bib.py
```
This creates `parsed_articles.json`.

### Step 4: Run Screening

```bash
python screen_articles.py
```

Or run the custom-generated version:
```bash
python screen_articles_custom.py
```

### Step 5: Review Results

Three output files are produced:

| File | Description |
|---|---|
| `screening_results.csv` | All articles with Include/Exclude decisions and reasons |
| `screening_disagreements.csv` | Articles where Pass 1 and Pass 2 disagreed (for human review) |
| `included_articles.ris` | Valid RIS file of all included articles (importable into EndNote, Zotero, etc.) |

---

## Dual-Pass Screening Logic

```
Article → Pass 1 → Include/Exclude + Reason
        → Pass 2 → Include/Exclude + Reason
        → Agreement Check:
              Both Include → INCLUDE
              Both Exclude → EXCLUDE
              Disagree     → FLAG FOR HUMAN REVIEW
```

---

## Project Structure

```
screening_agent/
├── generate_screening_code.py   # AI code generator (API + browser modes)
├── screen_articles.py           # Core screening engine + RIS export
├── criteria_parser.py           # Criteria file parser (.txt/.json/.docx)
├── parse_bib.py                 # BibTeX parser → JSON
├── config.py                    # Configuration (model, temperature)
├── requirements.txt             # Python dependencies
├── LICENSE                      # MIT License
└── examples/
    ├── example_criteria.txt
    └── example_criteria.json
```

---

## RIS Export Format

The `included_articles.ris` file follows standard RIS specification:

```
TY  - JOUR
TI  - Giant-cell tumours of the spine: A clinical study
AB  - We report 24 patients with...
AU  - Sanjay, B.K.S.
AU  - Sim, F.H.
PY  - 1993
DO  - 10.1302/0301-620X.75B1.8421032
JO  - Journal of Bone and Joint Surgery
ER  -
```

Compatible with EndNote, Zotero, Mendeley, and other reference managers.

---

## API Configuration

| Parameter | Value |
|---|---|
| Model | `gemini-2.5-flash` |
| Temperature | `0.2` |
| max_output_tokens | `16384` (code generation) |

---

## Important Notes

- **API mode requires only one key** — no API_KIT needed
- **Browser mode**: log in to Gemini once; profile is saved for future runs
- **Always review** AI-generated screening code before using it for research
- **Deterministic**: `temperature=0.2` ensures reproducible outputs

---

## License

MIT License — see [LICENSE](LICENSE) for details.
