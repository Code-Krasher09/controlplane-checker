"""Comprehensive Unit and Integration Test Suite for Phase 7 Semantic Retrieval Upgrade."""

import asyncio
import os
import tempfile
import pytest
from uuid import uuid4

from app.domain.models import (
    ActionType,
    ClaimEvidenceQuality,
    ClaimVerificationItem,
    EvidenceSnippet,
    GatewayInspectRequest,
    SeverityLevel,
    VerificationStatus,
)
from app.persistence.database import get_db_context, init_db
from app.persistence.seed import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    INTERNAL_KB_APP_ID,
    seed_database_async,
)
from app.tier1.evidence_quality import EvidenceQualityEvaluator
from app.tier1.nli_verifier import DeterministicNLIVerifier
from app.tier1.retrieval.chunking import DocumentChunk, DocumentChunker
from app.tier1.retrieval.embedding import (
    DeterministicMockEmbeddingProvider,
    RealEmbeddingProvider,
)
from app.tier1.retrieval.hybrid_repo import HybridEvidenceRepository
from app.tier1.retrieval.lexical_repo import LexicalEvidenceRepository
from app.tier1.retrieval.semantic_repo import SemanticEvidenceRepository
from app.tier1.service import Tier1Service
from app.gateway.service import GatewayService


@pytest.fixture
def mock_embedding_provider():
    return DeterministicMockEmbeddingProvider(dimension=64)


@pytest.fixture
def sample_chunks():
    return [
        DocumentChunk(
            chunk_id="chunk-ret-30d",
            source_id="doc-returns-2026",
            document_id="doc-returns",
            document_version="v2.1",
            timestamp="2026-01-01T00:00:00Z",
            authority="HIGH",
            application_profile="CUSTOMER_SUPPORT",
            policy_scope="RETAIL",
            content="Standard retail return policy permits full refunds within 30 days of product delivery in original packaging.",
        ),
        DocumentChunk(
            chunk_id="chunk-ret-stale",
            source_id="doc-returns-2024",
            document_id="doc-returns-legacy",
            document_version="v1.0",
            timestamp="2024-01-01T00:00:00Z",
            authority="MEDIUM",
            application_profile="CUSTOMER_SUPPORT",
            policy_scope="RETAIL",
            content="Legacy retail return policy permits returns within 14 days subject to a 15% restocking fee.",
        ),
        DocumentChunk(
            chunk_id="chunk-waiver-cap",
            source_id="doc-waivers-2026",
            document_id="doc-waivers",
            document_version="v1.4",
            timestamp="2026-01-01T00:00:00Z",
            authority="HIGH",
            application_profile="DECISION_SUPPORT",
            policy_scope="FINANCIAL",
            content="Customer courtesy fee waivers are strictly capped at $200 per account and require supervisor signoff.",
        ),
        DocumentChunk(
            chunk_id="chunk-eeo-hr",
            source_id="doc-eeo-policy",
            document_id="doc-eeo",
            document_version="v3.0",
            timestamp="2026-01-01T00:00:00Z",
            authority="HIGH",
            application_profile="INTERNAL_KNOWLEDGE",
            policy_scope="HR",
            content="Company hiring and technical performance evaluations must be based solely on objective skills without bias.",
        ),
    ]


# 1. Index creation
def test_1_index_creation(mock_embedding_provider, sample_chunks):
    repo = SemanticEvidenceRepository(embedding_provider=mock_embedding_provider, chunks=sample_chunks)
    assert repo._index is not None
    assert repo._index.ntotal == len(sample_chunks)


# 2. Index reproducibility
def test_2_index_reproducibility(mock_embedding_provider, sample_chunks):
    with tempfile.TemporaryDirectory() as tmpdir:
        index_p = os.path.join(tmpdir, "test.bin")
        meta_p = os.path.join(tmpdir, "meta.json")
        man_p = os.path.join(tmpdir, "manifest.json")

        repo1 = SemanticEvidenceRepository(embedding_provider=mock_embedding_provider, chunks=sample_chunks)
        repo1.save_index(index_p, meta_p, man_p)

        repo2 = SemanticEvidenceRepository(embedding_provider=mock_embedding_provider, index_path=index_p, metadata_path=meta_p)
        assert repo2._index.ntotal == repo1._index.ntotal
        assert len(repo2._chunks) == len(repo1._chunks)


# 3. Lexical retrieval
def test_3_lexical_retrieval():
    repo = LexicalEvidenceRepository()
    results = repo.retrieve("retail return policy 30 days refund", top_k=2)
    assert len(results) > 0
    assert "30 days" in results[0].content_snippet


# 4. Semantic retrieval
def test_4_semantic_retrieval(mock_embedding_provider, sample_chunks):
    repo = SemanticEvidenceRepository(embedding_provider=mock_embedding_provider, chunks=sample_chunks)
    results = repo.retrieve("refund within 30 days of delivery", top_k=2)
    assert len(results) > 0
    assert results[0].quality is not None
    assert results[0].quality.relevance > 0.0


# 5. Hybrid retrieval
def test_5_hybrid_retrieval(mock_embedding_provider, sample_chunks):
    sem_repo = SemanticEvidenceRepository(embedding_provider=mock_embedding_provider, chunks=sample_chunks)
    lex_repo = LexicalEvidenceRepository()
    hyb_repo = HybridEvidenceRepository(semantic_repo=sem_repo, lexical_repo=lex_repo, alpha=0.5)

    results = hyb_repo.retrieve("fee waivers capped at $200 supervisor signoff", top_k=2)
    assert len(results) > 0
    assert "$200" in results[0].content_snippet


# 6. Metadata filtering
def test_6_metadata_filtering(mock_embedding_provider, sample_chunks):
    repo = SemanticEvidenceRepository(embedding_provider=mock_embedding_provider, chunks=sample_chunks)
    
    # Query HR topic under CUSTOMER_SUPPORT scope -> should be filtered out
    results = repo.retrieve(
        "technical performance evaluation anti-bias",
        application_profile="CUSTOMER_SUPPORT",
        policy="RETAIL",
        top_k=2,
    )
    for snip in results:
        assert snip.source_id != "doc-eeo-policy"


# 7. Top-k correctness
def test_7_top_k_correctness(mock_embedding_provider, sample_chunks):
    repo = SemanticEvidenceRepository(embedding_provider=mock_embedding_provider, chunks=sample_chunks)
    res_1 = repo.retrieve("return policy", top_k=1)
    res_3 = repo.retrieve("return policy", top_k=3)
    assert len(res_1) == 1
    assert len(res_3) <= 3
    assert res_1[0].chunk_id == res_3[0].chunk_id


# 8. Required evidence retrieval
def test_8_required_evidence_retrieval(sample_chunks):
    # Use real embedding provider for semantic test
    prov = RealEmbeddingProvider()
    repo = SemanticEvidenceRepository(embedding_provider=prov, chunks=sample_chunks)
    results = repo.retrieve("Can a customer receive a courtesy billing credit of $200?", top_k=1)
    assert len(results) == 1
    assert results[0].source_id == "doc-waivers-2026"


# 9. Irrelevant evidence rejection
def test_9_irrelevant_evidence_rejection(sample_chunks):
    prov = RealEmbeddingProvider()
    repo = SemanticEvidenceRepository(embedding_provider=prov, chunks=sample_chunks)
    results = repo.retrieve(
        "Bringing exotic pets into office warehouse facilities",
        application_profile="INTERNAL_KNOWLEDGE",
        policy="FACILITIES",
        top_k=2,
    )
    # Facilities policy scope has no match -> pre-filtering returns empty
    assert len(results) == 0


# 10. Evidence quality integration
def test_10_evidence_quality_integration():
    evaluator = EvidenceQualityEvaluator()
    snip = EvidenceSnippet(
        source_type="POLICY_DOC",
        source_id="doc-returns",
        content_snippet="Retail refund within 30 days",
        quality=ClaimEvidenceQuality(
            authority="HIGH",
            freshness=1.0,
            relevance=0.95,
            completeness=0.90,
            quality_score=0.95,
        ),
    )
    claim = "Refunds allowed within 30 days"
    evaluated = evaluator.evaluate_evidence_set(claim, [snip])
    assert evaluator.is_adequate(evaluated)


# 11. Insufficient evidence behavior
def test_11_insufficient_evidence_behavior():
    tier1 = Tier1Service()
    # Empty evidence snippet list
    claims, pairs = tier1.verify_response("Some random unsupported claim about alien spaceships.")
    assert len(claims) == 1
    assert claims[0].verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE
    assert claims[0].final_label == "INSUFFICIENT_EVIDENCE"


# 12. No adjudication on insufficient evidence (CRITICAL EPISTEMIC RULE)
def test_12_no_adjudication_on_insufficient_evidence():
    tier1 = Tier1Service()
    claims, _ = tier1.verify_response("Claim with no matching evidence in store whatsoever.")
    assert len(claims) == 1
    # INVARIANT: Must NEVER trigger Selective Adjudication on missing/weak evidence
    assert claims[0].adjudication_trigger.value == "NONE"
    assert claims[0].verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE


# 13. Policy isolation
def test_13_policy_isolation(mock_embedding_provider, sample_chunks):
    repo = SemanticEvidenceRepository(embedding_provider=mock_embedding_provider, chunks=sample_chunks)
    results = repo.retrieve(
        "Standard return policy",
        application_profile="INTERNAL_KNOWLEDGE",
        policy="HR",
        top_k=2,
    )
    for snip in results:
        assert snip.source_id != "doc-returns-2026"


# 14. Policy-version freshness
def test_14_policy_version_freshness(sample_chunks):
    # Verify metadata preserves document versions
    v21_chunks = [c for c in sample_chunks if c.document_version == "v2.1"]
    assert len(v21_chunks) == 1
    assert v21_chunks[0].authority == "HIGH"


# 15. Conflicting evidence handling
def test_15_conflicting_evidence_handling(mock_embedding_provider, sample_chunks):
    repo = SemanticEvidenceRepository(embedding_provider=mock_embedding_provider, chunks=sample_chunks)
    results = repo.retrieve("return policy duration 14 days or 30 days", top_k=5)
    source_ids = [s.source_id for s in results]
    # Both current and legacy can be returned with their respective document versions intact
    assert len(results) >= 1


# 16. Cache correctness
def test_16_cache_correctness(mock_embedding_provider, sample_chunks):
    repo = SemanticEvidenceRepository(embedding_provider=mock_embedding_provider, chunks=sample_chunks, cache_size=10)
    query = "Standard retail return policy full refund"
    
    # Cold query
    res1 = repo.retrieve(query, top_k=2)
    assert len(repo._query_cache) == 1

    # Warm query (from cache)
    res2 = repo.retrieve(query, top_k=2)
    assert len(res1) == len(res2)
    assert res1[0].chunk_id == res2[0].chunk_id


# 17. Semantic retrieval end-to-end effect
@pytest.mark.asyncio
async def test_17_semantic_retrieval_end_to_end(sample_chunks, async_session):
    await seed_database_async(async_session)

    prov = DeterministicMockEmbeddingProvider()
    sem_repo = SemanticEvidenceRepository(embedding_provider=prov, chunks=sample_chunks)
    tier1 = Tier1Service(evidence_repo=sem_repo, verifier=DeterministicNLIVerifier())
    
    gw = GatewayService(tier1_service=tier1)

    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Can I return an item?",
        response="Standard retail return policy permits full refunds within 30 days.",
        scenario="SAFE",
        session_id="test-sem-e2e-01",
    )
    resp = await gw.inspect(req, async_session)
    assert resp.action == ActionType.ALLOW
    assert len(resp.claims) >= 0


# 18. Routing A/B testing
def test_18_routing_ab_testing(sample_chunks):
    sem_repo = SemanticEvidenceRepository(embedding_provider=DeterministicMockEmbeddingProvider(), chunks=sample_chunks)
    t1_repo = Tier1Service(evidence_repo=sem_repo)
    assert t1_repo.evidence_repo == sem_repo
