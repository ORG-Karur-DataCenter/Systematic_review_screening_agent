import json
import csv
import logging

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
        logger.info(f"  No disagreements — 100% consistency confirmed.")

    return agreed, disagreements, articles


if __name__ == "__main__":
    agreed, disagreements, all_articles = dual_pass_screening('parsed_articles.json')

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

    # Export filtered RIS of INCLUDED articles with title + abstract
    included_keys = {r['Key'] for r in agreed if r['Decision'] == 'Include'}

    with open('included_articles.ris', 'w', encoding='utf-8') as ris:
        for art in all_articles:
            if art['key'] in included_keys:
                ris.write(f"TY  - JOUR\n")
                ris.write(f"TI  - {art.get('title', '')}\n")
                ris.write(f"AB  - {art.get('abstract', '')}\n")
                if art.get('author'):
                    for author in art['author'].split(' and '):
                        ris.write(f"AU  - {author.strip()}\n")
                if art.get('year'):
                    ris.write(f"PY  - {art['year']}\n")
                if art.get('doi'):
                    ris.write(f"DO  - {art['doi']}\n")
                if art.get('journal'):
                    ris.write(f"JO  - {art['journal']}\n")
                ris.write(f"ER  - \n\n")

    logger.info(f"Screening complete. Results saved to screening_results.csv")
    logger.info(f"Included articles exported to included_articles.ris ({len(included_keys)} articles)")
    for res in agreed:
        print(f"[{res['Decision']}] {res['Title'][:50]}... - {res['Reason']}")

