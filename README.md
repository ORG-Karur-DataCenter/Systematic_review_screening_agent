<p align="center">
  <h1 align="center">Systematic Review Screening Agent</h1>
  <p align="center">
    AI-powered title & abstract screening for systematic reviews.<br>
    One command. Criteria in, included articles out.
  </p>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#output">Output</a> •
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

## Quickstart

### 1. Install

```bash
git clone https://github.com/ORG-Karur-DataCenter/Systematic_review_screening_agent.git
cd Systematic_review_screening_agent
pip install -r requirements.txt
playwright install chromium
```

### 2. Prepare Your Inputs

You need two files:

| File | Description | Formats |
|------|-------------|---------|
| **Criteria file** | Your inclusion/exclusion rules | `.txt`, `.docx`, `.json` |
| **Articles file** | Exported bibliography from database search | `.bib`, `.ris`, `.json` |

### 3. Run

```bash
python screen.py --criteria my_criteria.txt --articles my_articles.bib
```

That's it. A browser window opens, Gemini generates your custom screening logic, articles are screened, and results are exported — all in one command.

#### Want it faster? Add an API key:

```bash
python screen.py --criteria my_criteria.txt --articles my_articles.ris --api-key YOUR_KEY
```

No browser needed. Runs in ~40 seconds.

---

## How It Works

```
                    ┌─────────────────────────┐
                    │   screen.py             │
                    │   (one command)          │
                    └────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌───────────┐  ┌──────────┐
        │ Phase 1  │  │  Phase 2  │  │ Phase 3  │
        │ Parse    │  │ Generate  │  │ Screen   │
        │ articles │  │ screening │  │ dual-pass│
        │ .bib/.ris│  │ logic via │  │ + export │
        │ → JSON   │  │ Gemini AI │  │ CSV + RIS│
        └──────────┘  └───────────┘  └──────────┘
```

### Phase 1 — Parse Articles
Reads `.bib`, `.ris`, or `.json` files and extracts title, abstract, authors, year, DOI, and journal for each article.

### Phase 2 — Generate Screening Logic
Sends your criteria + a reference screening function to Gemini. Gemini generates a custom Python screening function with:
- Hierarchical decision trees
- Title vs abstract weighting
- Contextual exception handling
- Complex boolean logic for competing diagnoses

The generated code is validated for syntax before use.

### Phase 3 — Dual-Pass Screening
Runs the screening function **twice independently** on every article:
- **Both passes agree → decision finalized** (Include or Exclude)
- **Passes disagree → flagged for human review**

Because the screening logic is deterministic (keyword-based generated code), both passes produce identical results — guaranteeing **100% reproducibility**.

### Phase 4 — Export
Produces three output files automatically:
- `screening_results.csv` — all decisions with reasons
- `included_articles.ris` — valid RIS file of included articles (for import into EndNote/Zotero)
- `screening_disagreements.csv` — any flagged articles (if applicable)

---

## Criteria File Format

### Text Format (`.txt`) — Recommended

```
[DESCRIPTION]
Screening for RCTs comparing cervical disc arthroplasty vs ACDF

[INCLUSION_KEYWORDS]
Primary Topic: Giant Cell Tumor, Osteoclastoma
Anatomical Location: Cervical, C1, C2, C3, C4, C5, C6, C7

[EXCLUSION_KEYWORDS]
Study Types: Systematic Review, Meta-Analysis, Case Report
Competing Diagnoses: Osteoblastoma, Chordoma, Lymphoma
Non-Bone Types: Synovial, Tenosynovial

[MATCHING_RULES]
Case Sensitive: No
Primary Topic in Title Required: Yes
Title Weight Higher Than Abstract: Yes
```

### JSON Format (`.json`)

```json
{
  "description": "Screening for GCT in cervical spine",
  "inclusion": {
    "primary_topic": ["Giant Cell Tumor", "Osteoclastoma"],
    "location": ["Cervical", "C1", "C2"]
  },
  "exclusion": {
    "study_types": ["Systematic Review", "Meta-Analysis"],
    "competing": ["Osteoblastoma", "Chordoma"]
  }
}
```

See `examples/` folder for complete examples.

---

## Output

### `screening_results.csv`

| Key | Title | Decision | Reason |
|-----|-------|----------|--------|
| sanjay1993 | Giant-cell tumours of the spine... | Include | Original article on Cervical Bone GCT |
| smith2020 | Systematic Review of Osteoblastoma... | Exclude | Not GCT/Osteoclastoma |

### `included_articles.ris`

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

## Advanced

### Command-Line Options

```
python screen.py --help

Options:
  --criteria FILE     Path to criteria file (.txt, .docx, .json)    [required]
  --articles FILE     Path to articles file (.bib, .ris, .json)     [required]
  --browser CHANNEL   Browser for code generation (chrome, msedge)  [default: chrome]
  --api-key KEY       Gemini API key (optional, faster than browser)
  --model NAME        Gemini model (default: gemini-2.5-flash)
  --output-dir DIR    Output directory (default: current directory)
  --skip-codegen      Skip AI code generation, use default logic
```

### Using Individual Scripts

If you prefer step-by-step control:

```bash
# Step 1: Generate screening code
python generate_screening_code.py criteria.txt --api-key KEY

# Step 2: Parse articles
python parse_bib.py

# Step 3: Run screening
python screen_articles.py
```

### Modes

| Mode | Command | Speed | Cost |
|------|---------|-------|------|
| **Browser** (default) | `python screen.py --criteria c.txt --articles a.bib` | ~2 min | Free |
| **API** (optional) | `python screen.py --criteria c.txt --articles a.bib --api-key KEY` | ~40 sec | Free tier |

---

## Project Structure

```
screening_agent/
├── screen.py                    # One-command pipeline orchestrator
├── generate_screening_code.py   # AI code generator (API + browser)
├── screen_articles.py           # Core screening engine + RIS export
├── criteria_parser.py           # Criteria file parser
├── parse_bib.py                 # BibTeX parser
├── config.py                    # Configuration
├── requirements.txt             # Dependencies
├── LICENSE                      # MIT License
└── examples/
    ├── example_criteria.txt
    └── example_criteria.json
```

---

## API Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `temperature` | `0.2` | Deterministic, reproducible output |
| `max_output_tokens` | `16384` | Room for generated screening code |
| Model | `gemini-2.5-flash` | Fast, capable |

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
  <sub>Built for systematic reviewers. One command to screen them all.</sub>
</p>
