# Configuration File for Systematic Review Screening Agent

# =============================================================================
# GEMINI API CONFIGURATION
# =============================================================================
# Get your API key from: https://aistudio.google.com/app/apikey
# Set as environment variable: GEMINI_API_KEY=your-key-here

# Gemini model to use for code generation
GEMINI_MODEL = "gemini-2.5-flash"

# Temperature for code generation (manuscript specifies 0.2)
GENERATION_TEMPERATURE = 0.2

# Maximum tokens for code generation (needs more room than extraction)
MAX_OUTPUT_TOKENS = 8192

# =============================================================================
# USAGE INSTRUCTIONS
# =============================================================================
# API Mode (fast, recommended):
#   python generate_screening_code.py your_criteria.txt --api-key YOUR_KEY
#
# Browser Mode (free, no API key):
#   python generate_screening_code.py your_criteria.txt --browser chrome
#
# Then:
#   python parse_bib.py
#   python screen_articles_custom.py   (or screen_articles.py for default logic)

# =============================================================================
# CRITERIA FILE LOCATION
# =============================================================================
DEFAULT_CRITERIA_FILE = "examples/example_criteria.txt"

# =============================================================================
# OUTPUT SETTINGS
# =============================================================================
OUTPUT_FILE = "screening_results.csv"
RIS_OUTPUT = "included_articles.ris"
VERBOSE = True
