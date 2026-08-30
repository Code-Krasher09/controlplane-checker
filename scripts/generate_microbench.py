import json
from pathlib import Path

cases = [
    # SUPPORTED
    {"case_id": "sup-1", "premise": "The policy requires employees to attend mandatory training once per year.", "hypothesis": "Employees must go to training annually.", "expected": "SUPPORTED", "type": "paraphrase"},
    {"case_id": "sup-2", "premise": "Only items purchased within the last 30 days are eligible for a full refund.", "hypothesis": "You can get your money back if you bought the item 2 weeks ago.", "expected": "SUPPORTED", "type": "numerical implication"},
    {"case_id": "sup-3", "premise": "A password must be at least 12 characters long and contain a number.", "hypothesis": "A 14-character password with a digit is allowed if other rules are met.", "expected": "SUPPORTED", "type": "partial support"},
    {"case_id": "sup-4", "premise": "The system will be down on Monday. It will resume operations on Tuesday.", "hypothesis": "The system is offline on Monday.", "expected": "SUPPORTED", "type": "multi-sentence evidence"},
    {"case_id": "sup-5", "premise": "Remote work is permitted for all roles except hardware technicians.", "hypothesis": "Software engineers can work remotely.", "expected": "SUPPORTED", "type": "logical deduction"},
    {"case_id": "sup-6", "premise": "The company matched 5% of 401k contributions in 2023 and increased it to 6% in 2024.", "hypothesis": "In 2024, the company matches 6% of contributions.", "expected": "SUPPORTED", "type": "temporal resolution"},
    {"case_id": "sup-7", "premise": "We do not accept checks or money orders.", "hypothesis": "Checks are not an accepted payment method.", "expected": "SUPPORTED", "type": "negation extraction"},
    {"case_id": "sup-8", "premise": "Users caught sharing accounts will be permanently banned immediately.", "hypothesis": "Account sharing results in a permanent ban.", "expected": "SUPPORTED", "type": "direct support"},
    {"case_id": "sup-9", "premise": "All internal emails are encrypted. External emails are not.", "hypothesis": "Internal emails have encryption.", "expected": "SUPPORTED", "type": "direct support"},
    {"case_id": "sup-10", "premise": "You must submit the form by 5 PM EST on Friday.", "hypothesis": "The deadline for the form is Friday at 5 PM EST.", "expected": "SUPPORTED", "type": "paraphrase"},

    # CONTRADICTED
    {"case_id": "con-1", "premise": "The return window is 30 days from the date of purchase.", "hypothesis": "You can return the item up to 60 days after purchase.", "expected": "CONTRADICTED", "type": "numerical contradiction"},
    {"case_id": "con-2", "premise": "Use of the corporate credit card for personal expenses is strictly prohibited.", "hypothesis": "You can use the corporate card for personal expenses if you pay it back.", "expected": "CONTRADICTED", "type": "direct contradiction"},
    {"case_id": "con-3", "premise": "The office is open Monday through Friday from 9 AM to 5 PM.", "hypothesis": "The office is open on weekends.", "expected": "CONTRADICTED", "type": "logical contradiction"},
    {"case_id": "con-4", "premise": "You must have manager approval before booking international flights.", "hypothesis": "Manager approval is not required for international flights.", "expected": "CONTRADICTED", "type": "negation"},
    {"case_id": "con-5", "premise": "The 2023 policy stated 10 vacation days. The 2024 policy updated this to 15 days.", "hypothesis": "According to the current 2024 policy, employees get 10 vacation days.", "expected": "CONTRADICTED", "type": "temporal contradiction"},
    {"case_id": "con-6", "premise": "All contractors must complete the security orientation.", "hypothesis": "Contractors are exempt from security orientation.", "expected": "CONTRADICTED", "type": "negation"},
    {"case_id": "con-7", "premise": "The maximum file upload size is 50MB.", "hypothesis": "You can upload files up to 100MB in size.", "expected": "CONTRADICTED", "type": "numerical contradiction"},
    {"case_id": "con-8", "premise": "Lunch breaks are 60 minutes long and unpaid.", "hypothesis": "Lunch breaks are paid.", "expected": "CONTRADICTED", "type": "direct contradiction"},
    {"case_id": "con-9", "premise": "First time offenders receive a warning. Second time offenders are terminated.", "hypothesis": "First time offenders are immediately terminated.", "expected": "CONTRADICTED", "type": "multi-sentence contradiction"},
    {"case_id": "con-10", "premise": "The software is only compatible with Windows 10 and 11.", "hypothesis": "The software is compatible with macOS.", "expected": "CONTRADICTED", "type": "logical exclusion"},

    # INSUFFICIENT_EVIDENCE (NEUTRAL)
    {"case_id": "neu-1", "premise": "The company provides a health insurance plan.", "hypothesis": "The health insurance plan includes dental coverage.", "expected": "INSUFFICIENT_EVIDENCE", "type": "related-but-not-supporting"},
    {"case_id": "neu-2", "premise": "Employees must wear formal attire on Mondays.", "hypothesis": "Employees can wear casual clothes on Fridays.", "expected": "INSUFFICIENT_EVIDENCE", "type": "related-but-not-supporting"},
    {"case_id": "neu-3", "premise": "The maximum file upload size is 50MB.", "hypothesis": "The system accepts PDF and DOCX files.", "expected": "INSUFFICIENT_EVIDENCE", "type": "unrelated"},
    {"case_id": "neu-4", "premise": "Rule A says refunds are allowed. Rule B says no refunds under any circumstances.", "hypothesis": "Refunds are allowed for damaged items.", "expected": "INSUFFICIENT_EVIDENCE", "type": "conflicting evidence / ambiguous"},
    {"case_id": "neu-5", "premise": "The office is open Monday through Friday.", "hypothesis": "The office is closed on federal holidays.", "expected": "INSUFFICIENT_EVIDENCE", "type": "logical gap"},
    {"case_id": "neu-6", "premise": "Most items are eligible for a 30-day return.", "hypothesis": "Customized items are eligible for a 30-day return.", "expected": "INSUFFICIENT_EVIDENCE", "type": "ambiguous wording"},
    {"case_id": "neu-7", "premise": "The CEO announced a new strategic direction in 2024.", "hypothesis": "The company will focus on artificial intelligence.", "expected": "INSUFFICIENT_EVIDENCE", "type": "related-but-not-supporting"},
    {"case_id": "neu-8", "premise": "All managers must submit their reviews by Friday.", "hypothesis": "Employees must submit their self-reviews by Wednesday.", "expected": "INSUFFICIENT_EVIDENCE", "type": "related-but-not-supporting"},
    {"case_id": "neu-9", "premise": "The base salary is $70,000.", "hypothesis": "Employees receive an annual bonus of 10%.", "expected": "INSUFFICIENT_EVIDENCE", "type": "unrelated"},
    {"case_id": "neu-10", "premise": "Use of force is only authorized in self defense.", "hypothesis": "Use of force is authorized when a suspect flees.", "expected": "INSUFFICIENT_EVIDENCE", "type": "ambiguous / logical gap"}
]

out_dir = Path("data/evaluation/nli_microbench")
out_dir.mkdir(parents=True, exist_ok=True)

with open(out_dir / "microbench.jsonl", "w") as f:
    for c in cases:
        f.write(json.dumps(c) + "\n")
