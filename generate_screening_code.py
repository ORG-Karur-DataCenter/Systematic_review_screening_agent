"""
generate_screening_code.py — Screening Code Generator using Gemini

Supports two modes:
  API mode (fast):     python generate_screening_code.py criteria.txt --api-key YOUR_KEY
  Browser mode (free): python generate_screening_code.py criteria.txt --browser chrome

Interacts with Gemini to generate custom screening logic from user criteria.
"""

import os
import re
import ast
import time
import json
import logging
import argparse
from pathlib import Path
from criteria_parser import parse_criteria

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("screening_gen_run.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
GEMINI_URL = "https://gemini.google.com/app"
DEFAULT_OUTPUT = "screen_articles_custom.py"
MAX_RETRIES = 3


def create_gemini_prompt(criteria: dict, reference_code: str) -> str:
    """Create the prompt for Gemini to generate screening code."""
    
    prompt = f"""You are an expert Python developer specializing in systematic review automation.

I need you to generate a Python function called `screen_articles(json_path)` that screens academic articles based on custom criteria.

**REFERENCE CODE (for structure and logic patterns):**
```python
{reference_code}
```

**USER'S CUSTOM CRITERIA:**
```json
{json.dumps(criteria, indent=2)}
```

**REQUIREMENTS:**
1. Generate a complete, working `screen_articles(json_path)` function
2. Use the SAME sophisticated logic patterns from the reference code:
   - Hierarchical decision trees
   - Contextual exception handling (e.g., if keyword A is in title AND keyword B, treat differently)
   - Title vs abstract weighting
   - Complex boolean logic for competing diagnoses
3. Adapt the logic to use the user's custom criteria keywords
4. Maintain the same input/output format:
   - Input: JSON file with articles (each has 'key', 'title', 'abstract')
   - Output: List of dicts with 'Key', 'Title', 'Decision', 'Reason'
5. Include detailed reasoning for each decision
6. Add comments explaining the logic

**IMPORTANT:**
- Do NOT just do simple keyword matching
- Implement nuanced logic similar to the reference code
- Handle edge cases and exceptions
- Make the code production-ready
- Keep the function CONCISE — under 100 lines. Do not embed the criteria as a JSON string; hardcode them directly as Python lists/variables.

Generate ONLY the `screen_articles(json_path)` function body starting with `def screen_articles(json_path):`. Do NOT include import statements, the `if __name__` block, or any JSON/YAML configuration strings. Assume `json` is already imported."""
    
    return prompt


# ============================================================
# API MODE — Fast, single key, no browser needed
# ============================================================

def generate_via_api(prompt_text, api_key, model_name="gemini-2.5-flash"):
    """Generate screening code using the Gemini API directly."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name,
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 16384,  # Code generation needs room
        }
    )

    logger.info(f"Sending prompt to Gemini API ({model_name})...")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = model.generate_content(prompt_text)
            raw_text = response.text

            code = extract_python_code(raw_text)
            if code and validate_generated_code(code):
                logger.info(f"Code validated successfully on attempt {attempt}.")
                return code
            else:
                logger.warning(f"Attempt {attempt}: no valid code extracted.")
                if code:
                    logger.warning(f"  Code preview: {code[:200]}...")

        except Exception as e:
            logger.warning(f"Attempt {attempt} API error: {e}")
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                logger.info("Rate limited. Waiting 15s...")
                time.sleep(15)
            else:
                time.sleep(5)

    return None


# ============================================================
# BROWSER MODE — Free, uses Playwright + Gemini web UI
# ============================================================

def generate_via_browser(prompt_text, browser_channel="chrome"):
    """Generate screening code using browser automation (Playwright)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        profile_name = f"{browser_channel}_profile_screening"
        user_data_dir = str(Path.cwd() / profile_name)

        logger.info(f"Launching {browser_channel} with profile: {user_data_dir}")

        browser = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            channel=browser_channel,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--disable-gpu",
            ],
            ignore_default_args=["--enable-automation"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Use existing page or create one — don't open extra tabs
        if len(browser.pages) > 0:
            page = browser.pages[0]
        else:
            page = browser.new_page()

        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        generated_code = None
        for attempt in range(1, MAX_RETRIES + 1):
            logger.info(f"Attempt {attempt}/{MAX_RETRIES}: Sending prompt to Gemini...")
            candidate_code = _browser_send_and_extract(page, prompt_text)

            if candidate_code and validate_generated_code(candidate_code):
                generated_code = candidate_code
                logger.info(f"Code validated successfully on attempt {attempt}.")
                break
            else:
                logger.warning(f"Attempt {attempt} failed (no code or invalid syntax).")
                if attempt < MAX_RETRIES:
                    logger.info("Retrying in 10 seconds...")
                    time.sleep(10)

        # Close browser cleanly
        try:
            browser.close()
        except Exception:
            pass

        return generated_code


def _browser_send_and_extract(page, prompt_text, max_wait=90):
    """Send prompt to Gemini via browser and extract the response code."""
    logger.info("Navigating to Gemini...")
    page.goto(GEMINI_URL)
    time.sleep(8)

    # Check if logged in
    try:
        logger.info("Checking login status...")
        page.locator("div[contenteditable='true'], textarea").wait_for(state="visible", timeout=8000)
        logger.info("Login confirmed. Proceeding...")
    except Exception:
        logger.warning("Login verification failed. Please log in to Gemini.")
        logger.info("Waiting 45 seconds for manual login...")
        time.sleep(45)

    # Send prompt
    try:
        logger.info("Sending prompt...")
        text_area = page.locator("div[contenteditable='true'], textarea")
        text_area.first.fill(prompt_text)
        time.sleep(1)
        text_area.first.press("Enter")
        logger.info("Prompt sent. Waiting for response...")

        # Wait for response to start
        time.sleep(10)

        # Wait for generation to complete
        logger.info("Waiting for Gemini to finish generating...")
        wait_time = 0
        while wait_time < max_wait:
            stop_button = page.locator("button:has-text('Stop generating'), button[aria-label*='Stop']")
            if stop_button.count() == 0:
                time.sleep(5)
                break
            time.sleep(5)
            wait_time += 5
            logger.info(f"  Still generating... ({wait_time}s)")

        logger.info("Response received. Extracting code...")

        # Extract response text
        response_elements = page.locator("model-response, .model-response-text, message-content, [data-test-id*='response']")

        if response_elements.count() > 0:
            last_response = response_elements.all()[-1].inner_text()
        else:
            logger.info("Using fallback extraction method...")
            main_content = page.locator("main, .conversation-container, .chat-history")
            if main_content.count() > 0:
                last_response = main_content.first.inner_text()
            else:
                last_response = page.content()

        code = extract_python_code(last_response)

        if code:
            logger.info(f"Extracted {len(code)} characters of code")
            return code
        else:
            logger.warning("Could not find Python code in response")
            logger.info(f"Response preview: {last_response[:300]}")
            return None

    except Exception as e:
        logger.error(f"Error during Gemini interaction: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# SHARED UTILITIES
# ============================================================

def validate_generated_code(code: str) -> bool:
    """Check if Gemini's output is syntactically valid Python."""
    try:
        ast.parse(code)
        return True
    except SyntaxError as e:
        logger.warning(f"Generated code has a syntax error on line {e.lineno}: {e.msg}")
        return False


def extract_python_code(text: str) -> str:
    """
    Extract Python code from Gemini's response.
    Looks for code blocks marked with ```python or ```
    """
    # Try to find code block with python marker
    if '```python' in text:
        parts = text.split('```python')
        if len(parts) > 1:
            code_part = parts[1].split('```')[0]
            return code_part.strip()
    
    # Try to find any code block
    if '```' in text:
        parts = text.split('```')
        if len(parts) >= 3:
            code_part = parts[1]
            lines = code_part.split('\n')
            if lines[0].strip() in ['python', 'py']:
                code_part = '\n'.join(lines[1:])
            return code_part.strip()
    
    # If no code blocks, try to extract function definition
    if 'def screen_articles' in text:
        start_idx = text.find('def screen_articles')
        if start_idx != -1:
            return text[start_idx:].strip()
    
    return None


def create_complete_module(generated_function: str, criteria: dict, criteria_file: str) -> str:
    """Create a complete Python module with the generated function."""
    
    module_code = f'''"""
Custom Screening Module
Auto-generated from criteria file: {criteria_file}

Criteria Description:
{criteria.get('description', 'No description provided')}

Generated using Gemini AI.
"""

import json
import csv

{generated_function}

if __name__ == "__main__":
    results = screen_articles('parsed_articles.json')
    with open('screening_results.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Key", "Title", "Decision", "Reason"])
        writer.writeheader()
        writer.writerows(results)
    
    print("Screening complete. Results saved to screening_results.csv")
    for res in results:
        print(f"[{{res['Decision']}}] {{res['Title'][:50]}}... - {{res['Reason']}}")
'''
    
    return module_code


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main(criteria_file: str, output_file: str = None, browser_channel: str = "chrome",
         api_key: str = None, model_name: str = "gemini-2.5-flash"):
    """
    Main function to generate screening code.
    Uses API mode if --api-key is provided. Falls back to browser mode.
    """
    print(f"\n{'='*70}")
    print("AUTOMATED SCREENING CODE GENERATOR")
    print(f"{'='*70}\n")

    # Parse criteria
    logger.info(f"Parsing criteria from: {criteria_file}")
    try:
        criteria = parse_criteria(criteria_file)
        logger.info("Criteria parsed successfully!")
    except Exception as e:
        logger.error(f"Error parsing criteria: {e}")
        return

    # Read reference code
    reference_code_path = Path(__file__).parent / 'screen_articles.py'
    if not reference_code_path.exists():
        logger.error(f"Reference code not found: {reference_code_path}")
        return

    with open(reference_code_path, 'r', encoding='utf-8') as f:
        reference_code = f.read()

    # Create prompt
    logger.info("Creating prompt for Gemini...")
    prompt = create_gemini_prompt(criteria, reference_code)
    logger.info(f"Prompt created ({len(prompt)} characters)")

    # Set output file
    if output_file is None:
        output_file = DEFAULT_OUTPUT
    output_path = Path(output_file).absolute()

    # Choose mode
    if api_key:
        logger.info(f"Mode: API ({model_name})")
        generated_code = generate_via_api(prompt, api_key, model_name)
    else:
        logger.info(f"Mode: Browser ({browser_channel})")
        generated_code = generate_via_browser(prompt, browser_channel)

    if generated_code:
        # Create complete module
        logger.info("Creating complete module...")
        complete_module = create_complete_module(generated_code, criteria, criteria_file)

        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(complete_module)

        logger.info(f"\n{'='*70}")
        logger.info("SUCCESS!")
        logger.info(f"{'='*70}")
        logger.info(f"Custom screening module saved to: {output_path}")
        logger.info(f"Next steps:")
        logger.info(f"1. Review the generated code: {output_path}")
        logger.info(f"2. Parse your BibTeX file: python parse_bib.py")
        logger.info(f"3. Run screening: python {output_file}")
    else:
        logger.error(f"Failed to generate valid code after {MAX_RETRIES} attempts.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate custom screening code using Gemini AI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "criteria_file",
        help="Path to criteria file (.txt, .docx, or .json)"
    )
    parser.add_argument(
        "--output",
        help=f"Output file path (default: {DEFAULT_OUTPUT})",
        default=None
    )
    parser.add_argument(
        "--browser",
        help="Browser channel to use (chrome, msedge)",
        default="chrome"
    )
    parser.add_argument(
        "--api-key",
        help="Gemini API key (uses fast API mode instead of browser)",
        default=None
    )
    parser.add_argument(
        "--model",
        help="Gemini model name (default: gemini-2.5-flash)",
        default="gemini-2.5-flash"
    )

    args = parser.parse_args()
    main(
        criteria_file=args.criteria_file,
        output_file=args.output,
        browser_channel=args.browser,
        api_key=args.api_key,
        model_name=args.model
    )
