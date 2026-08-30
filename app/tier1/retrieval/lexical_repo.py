"""Lexical and keyword/stemming evidence repository."""

import re
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4
from app.domain.models import ClaimEvidenceQuality, EvidenceSnippet
from .base import BaseEvidenceRepository


class LexicalEvidenceRepository(BaseEvidenceRepository):
    """Lexical keyword and stem overlap retrieval implementation."""

    def __init__(self, snippets: Optional[List[EvidenceSnippet]] = None):
        if snippets is not None:
            self._corpus = list(snippets)
        else:
            self._corpus: List[EvidenceSnippet] = []
            self._seed_default_corpus()

    def _seed_default_corpus(self):
        """Populate baseline enterprise snippets."""
        self._corpus = [
            EvidenceSnippet(
                evidence_id=UUID("aaaaaaaa-0000-0000-0000-000000000001"),
                source_type="POLICY_DOC",
                source_id="doc-returns-2026",
                document_version="v2.1",
                chunk_id="chunk-ret-30d",
                content_snippet="Standard retail return policy permits full refunds within 30 days of product delivery in original packaging.",
                quality=ClaimEvidenceQuality(
                    authority="HIGH",
                    freshness=1.0,
                    relevance=0.98,
                    completeness=0.95,
                    quality_score=0.97,
                ),
            ),
            EvidenceSnippet(
                evidence_id=UUID("aaaaaaaa-0000-0000-0000-000000000002"),
                source_type="POLICY_DOC",
                source_id="doc-waivers-2026",
                document_version="v1.4",
                chunk_id="chunk-waiver-cap",
                content_snippet="Customer courtesy fee waivers are strictly capped at $200 per account and require formal supervisor signoff. Unlimited or $1000 waivers are strictly prohibited.",
                quality=ClaimEvidenceQuality(
                    authority="HIGH",
                    freshness=1.0,
                    relevance=0.95,
                    completeness=0.90,
                    quality_score=0.95,
                ),
            ),
            EvidenceSnippet(
                evidence_id=UUID("aaaaaaaa-0000-0000-0000-000000000003"),
                source_type="HR_DOC",
                source_id="doc-eeo-policy",
                document_version="v3.0",
                chunk_id="chunk-fairness-01",
                content_snippet="Company hiring and technical performance evaluations must be based solely on objective skills without bias regarding age, gender, or background.",
                quality=ClaimEvidenceQuality(
                    authority="HIGH",
                    freshness=1.0,
                    relevance=0.92,
                    completeness=0.90,
                    quality_score=0.94,
                ),
            ),
            EvidenceSnippet(
                evidence_id=UUID("aaaaaaaa-0000-0000-0000-000000000004"),
                source_type="TELECOM_DOC",
                source_id="doc-roaming-plan-b",
                document_version="v1.0",
                chunk_id="chunk-roam-45c",
                content_snippet="Plan B provides complimentary international roaming across 45 designated countries in North America and Europe, but roaming in other territories is excluded and requires an add-on pass.",
                quality=ClaimEvidenceQuality(
                    authority="HIGH",
                    freshness=1.0,
                    relevance=0.94,
                    completeness=0.92,
                    quality_score=0.95,
                ),
            ),
        ]

    def _extract_stems(self, text: str) -> Set[str]:
        """Normalize and stem words for keyword matching."""
        words = re.findall(r"\b[a-z0-9]{3,}\b", text.lower().replace("$", " ").replace(",", ""))
        stems = set()
        for w in words:
            stems.add(w)
            if w.endswith("s") and len(w) > 3:
                stems.add(w[:-1])
            if w.endswith("ed") and len(w) > 4:
                stems.add(w[:-2])
            if w.endswith("ing") and len(w) > 5:
                stems.add(w[:-3])
        return stems

    def add_snippets(self, snippets: List[EvidenceSnippet]):
        """Append snippets to corpus."""
        self._corpus.extend(snippets)

    def retrieve(
        self,
        query: str,
        application_profile: Optional[str] = None,
        policy: Optional[str] = None,
        top_k: int = 3,
    ) -> List[EvidenceSnippet]:
        """Find relevant evidence snippets matching claim text keywords with metadata filtering."""
        if not query:
            return []

        claim_stems = self._extract_stems(query)
        scored_snippets = []

        for snippet in self._corpus:
            # Metadata filtering if snippet has explicit restriction
            if application_profile and hasattr(snippet, "metadata") and snippet.metadata:
                allowed_apps = snippet.metadata.get("allowed_applications")
                if allowed_apps and application_profile not in allowed_apps and application_profile != "ALL":
                    continue

            snippet_stems = self._extract_stems(snippet.content_snippet)
            overlap = claim_stems.intersection(snippet_stems)
            if overlap:
                score = len(overlap) / max(1, len(claim_stems))
                if score >= 0.12:
                    scored_snippets.append((score, snippet))

        scored_snippets.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored_snippets[:top_k]]
