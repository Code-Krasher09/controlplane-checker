import json
from pathlib import Path

corpus_dir = Path("data/corpus")
corpus_dir.mkdir(parents=True, exist_ok=True)

documents = [
    {
        "document_id": "doc-returns-2024",
        "source_id": "doc-returns-2024",
        "title": "Legacy Retail Return Policy 2024",
        "document_version": "v1.0",
        "timestamp": "2024-01-01T00:00:00Z",
        "authority": "MEDIUM",
        "application_profile": "CUSTOMER_SUPPORT",
        "policy_scope": "RETAIL",
        "content": "Legacy retail return policy permits product returns within 14 days of purchase subject to a 15% restocking fee. Open box electronics are strictly non-refundable.",
        "extra_metadata": {"is_deprecated": True, "effective_year": 2024}
    },
    {
        "document_id": "doc-returns-2026",
        "source_id": "doc-returns-2026",
        "title": "Standard Retail Return Policy 2026",
        "document_version": "v2.1",
        "timestamp": "2026-01-01T00:00:00Z",
        "authority": "HIGH",
        "application_profile": "CUSTOMER_SUPPORT",
        "policy_scope": "RETAIL",
        "content": "Standard retail return policy permits full refunds within 30 days of product delivery in original packaging. Customers are entitled to full money back without restocking fees. Personalized or customized items are strictly excluded from returns.",
        "extra_metadata": {"is_current": True, "effective_year": 2026}
    },
    {
        "document_id": "doc-waivers-2024",
        "source_id": "doc-waivers-2024",
        "title": "Legacy Customer Waiver Thresholds 2024",
        "document_version": "v1.0",
        "timestamp": "2024-01-01T00:00:00Z",
        "authority": "LOW",
        "application_profile": "DECISION_SUPPORT",
        "policy_scope": "FINANCIAL",
        "content": "Legacy customer service waiver limit permits representative discretion up to $50 per customer incident without managerial review.",
        "extra_metadata": {"is_deprecated": True}
    },
    {
        "document_id": "doc-waivers-2026",
        "source_id": "doc-waivers-2026",
        "title": "Executive Fee Waiver and Courtesy Credit Policy 2026",
        "document_version": "v1.4",
        "timestamp": "2026-01-01T00:00:00Z",
        "authority": "HIGH",
        "application_profile": "DECISION_SUPPORT",
        "policy_scope": "FINANCIAL",
        "content": "Customer courtesy fee waivers are strictly capped at $200 per account and require formal supervisor signoff. Unlimited or $1000 waivers are strictly prohibited under financial compliance rules. Waivers exceeding $200 require director approval.",
        "extra_metadata": {"is_current": True}
    },
    {
        "document_id": "doc-eeo-policy",
        "source_id": "doc-eeo-policy",
        "title": "Equal Employment Opportunity and Anti-Bias Policy",
        "document_version": "v3.0",
        "timestamp": "2026-01-01T00:00:00Z",
        "authority": "HIGH",
        "application_profile": "INTERNAL_KNOWLEDGE",
        "policy_scope": "HR",
        "content": "Company hiring and technical performance evaluations must be based solely on objective skills without bias regarding age, gender, or background. All candidates must be assessed using standardized scorecards.",
        "extra_metadata": {"is_current": True}
    },
    {
        "document_id": "doc-interview-rubric",
        "source_id": "doc-interview-rubric",
        "title": "Standardized Technical Hiring Rubric",
        "document_version": "v2.0",
        "timestamp": "2026-01-01T00:00:00Z",
        "authority": "HIGH",
        "application_profile": "INTERNAL_KNOWLEDGE",
        "policy_scope": "HR",
        "content": "Technical interviews must follow structured coding rubrics with two independent interviewers. Subjective impressions or culture-fit vetoes without technical justification are strictly invalid.",
        "extra_metadata": {"is_current": True}
    },
    {
        "document_id": "doc-roaming-plan-a",
        "source_id": "doc-roaming-plan-a",
        "title": "Plan A Domestic Cellular Agreement",
        "document_version": "v1.0",
        "timestamp": "2026-01-01T00:00:00Z",
        "authority": "HIGH",
        "application_profile": "CUSTOMER_SUPPORT",
        "policy_scope": "TELECOM",
        "content": "Plan A covers domestic calls and data only. International roaming is strictly pay-per-use at $2.50 per megabyte unless an international bundle is purchased.",
        "extra_metadata": {"is_current": True}
    },
    {
        "document_id": "doc-roaming-plan-b",
        "source_id": "doc-roaming-plan-b",
        "title": "Plan B International Roaming Policy",
        "document_version": "v1.0",
        "timestamp": "2026-01-01T00:00:00Z",
        "authority": "HIGH",
        "application_profile": "CUSTOMER_SUPPORT",
        "policy_scope": "TELECOM",
        "content": "Plan B provides complimentary international roaming across 45 designated countries in North America and Europe, but roaming in other territories is excluded and requires an add-on pass.",
        "extra_metadata": {"is_current": True}
    },
    {
        "document_id": "doc-auth-mfa",
        "source_id": "doc-auth-mfa",
        "title": "Enterprise Security MFA Standards",
        "document_version": "v2.0",
        "timestamp": "2026-01-01T00:00:00Z",
        "authority": "HIGH",
        "application_profile": "INTERNAL_KNOWLEDGE",
        "policy_scope": "SECURITY",
        "content": "Multi-factor authentication (MFA) via hardware security key or authenticator app is strictly mandatory for all administrative access. SMS-based 2FA is prohibited for production environments due to SIM swapping risks.",
        "extra_metadata": {"is_current": True}
    },
    {
        "document_id": "doc-password-policy",
        "source_id": "doc-password-policy",
        "title": "Corporate Credential and Password Standard",
        "document_version": "v2.5",
        "timestamp": "2026-01-01T00:00:00Z",
        "authority": "HIGH",
        "application_profile": "INTERNAL_KNOWLEDGE",
        "policy_scope": "SECURITY",
        "content": "Corporate passwords must be at least 14 characters long containing letters, numbers, and symbols. Passwords must be rotated every 90 days and reuse of the last 10 passwords is prohibited.",
        "extra_metadata": {"is_current": True}
    },
    {
        "document_id": "doc-travel-flights",
        "source_id": "doc-travel-flights",
        "title": "Business Travel Airfare Guidelines",
        "document_version": "v1.8",
        "timestamp": "2026-01-01T00:00:00Z",
        "authority": "HIGH",
        "application_profile": "INTERNAL_KNOWLEDGE",
        "policy_scope": "TRAVEL",
        "content": "Economy class is mandatory for all domestic flights under 6 hours duration. Business class airfare requires VP approval and is only permitted on nonstop flights exceeding 6 hours.",
        "extra_metadata": {"is_current": True}
    },
    {
        "document_id": "doc-travel-meals",
        "source_id": "doc-travel-meals",
        "title": "Travel Meals and Per Diem Expense Policy",
        "document_version": "v1.2",
        "timestamp": "2026-01-01T00:00:00Z",
        "authority": "HIGH",
        "application_profile": "INTERNAL_KNOWLEDGE",
        "policy_scope": "TRAVEL",
        "content": "Daily business travel meal per diem is capped at $75 per day. Itemized receipts are mandatory for all client meals or expenditures involving alcohol.",
        "extra_metadata": {"is_current": True}
    }
]

with open(corpus_dir / "enterprise_corpus.json", "w", encoding="utf-8") as f:
    json.dump(documents, f, indent=2)

print(f"Created {len(documents)} enterprise corpus documents in {corpus_dir / 'enterprise_corpus.json'}")
