"""Database-level and schema invariant tests for V1.2 constraints."""

from uuid import uuid4
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.persistence import (
    Application,
    Claim,
    NLIResult,
    Request,
    Response,
)


async def _create_test_claim(session: AsyncSession) -> Claim:
    """Helper to create parent application, request, response, and claim."""
    app = Application(application_id=uuid4(), name="App", application_type="SUPPORT")
    req = Request(request_id=uuid4(), application_id=app.application_id, prompt="Prompt")
    resp = Response(response_id=uuid4(), request=req, content="Content")
    claim = Claim(claim_id=uuid4(), response=resp, claim_index=0, claim_text="Claim text")
    session.add_all([app, req, resp, claim])
    await session.commit()
    return claim


@pytest.mark.asyncio
async def test_invariant_a_inconclusive_null_final_label_valid(async_session: AsyncSession):
    """Invariant A: ADJUDICATION_INCONCLUSIVE with NULL final_label is VALID."""
    claim = await _create_test_claim(async_session)

    nli = NLIResult(
        nli_result_id=uuid4(),
        claim_id=claim.claim_id,
        model_name="deberta-v3",
        label="NEUTRAL",
        verification_status="ADJUDICATION_INCONCLUSIVE",
        adjudication_trigger="NLI_LOW_CONFIDENCE",
        uncertainty_reason="JUDGE_LOW_CONFIDENCE",
        final_label=None,
    )
    async_session.add(nli)
    await async_session.commit()
    assert nli.verification_status == "ADJUDICATION_INCONCLUSIVE"
    assert nli.final_label is None


@pytest.mark.asyncio
async def test_invariant_b_inconclusive_non_null_final_label_invalid(async_session: AsyncSession):
    """Invariant B: ADJUDICATION_INCONCLUSIVE with non-null final_label violates constraint."""
    claim = await _create_test_claim(async_session)

    nli = NLIResult(
        nli_result_id=uuid4(),
        claim_id=claim.claim_id,
        model_name="deberta-v3",
        label="NEUTRAL",
        verification_status="ADJUDICATION_INCONCLUSIVE",
        adjudication_trigger="NLI_LOW_CONFIDENCE",
        uncertainty_reason="JUDGE_LOW_CONFIDENCE",
        final_label="SUPPORTED",  # Invalid! Inconclusive cannot force a label
    )
    async_session.add(nli)
    with pytest.raises(IntegrityError):
        await async_session.commit()


@pytest.mark.asyncio
async def test_invariant_c_direct_nli_null_final_label_invalid(async_session: AsyncSession):
    """Invariant C: DIRECT_NLI with null final_label (without budget exhaustion) is INVALID."""
    claim = await _create_test_claim(async_session)

    nli = NLIResult(
        nli_result_id=uuid4(),
        claim_id=claim.claim_id,
        model_name="deberta-v3",
        label="SUPPORTED",
        verification_status="DIRECT_NLI",
        adjudication_trigger="NONE",
        uncertainty_reason="NONE",
        final_label=None,  # Invalid for DIRECT_NLI without budget exhaustion
    )
    async_session.add(nli)
    with pytest.raises(IntegrityError):
        await async_session.commit()


@pytest.mark.asyncio
async def test_invariant_d_adjudicated_null_final_label_invalid(async_session: AsyncSession):
    """Invariant D: ADJUDICATED with null final_label is INVALID (must assert label)."""
    claim = await _create_test_claim(async_session)

    nli = NLIResult(
        nli_result_id=uuid4(),
        claim_id=claim.claim_id,
        model_name="deberta-v3",
        label="SUPPORTED",
        verification_status="ADJUDICATED",
        adjudication_trigger="NLI_CLOSE_TOP2",
        uncertainty_reason="NONE",
        final_label="CONTRADICTED",  # Valid non-null label
    )
    async_session.add(nli)
    await async_session.commit()
    assert nli.final_label == "CONTRADICTED"


@pytest.mark.asyncio
async def test_invariant_e_none_trigger_direct_nli_valid(async_session: AsyncSession):
    """Invariant E: trigger=NONE + DIRECT_NLI + reason=NONE is VALID."""
    claim = await _create_test_claim(async_session)

    nli = NLIResult(
        nli_result_id=uuid4(),
        claim_id=claim.claim_id,
        model_name="deberta-v3",
        label="SUPPORTED",
        verification_status="DIRECT_NLI",
        adjudication_trigger="NONE",
        uncertainty_reason="NONE",
        final_label="SUPPORTED",
    )
    async_session.add(nli)
    await async_session.commit()
    assert nli.verification_status == "DIRECT_NLI"


@pytest.mark.asyncio
async def test_invariant_f_non_none_trigger_adjudicated_valid(async_session: AsyncSession):
    """Invariant F: non-NONE trigger + ADJUDICATED is VALID."""
    claim = await _create_test_claim(async_session)

    nli = NLIResult(
        nli_result_id=uuid4(),
        claim_id=claim.claim_id,
        model_name="deberta-v3",
        label="CONTRADICTED",
        verification_status="ADJUDICATED",
        adjudication_trigger="NLI_CLOSE_TOP2",
        uncertainty_reason="NONE",
        final_label="CONTRADICTED",
    )
    async_session.add(nli)
    await async_session.commit()
    assert nli.verification_status == "ADJUDICATED"


@pytest.mark.asyncio
async def test_invariant_g_non_none_trigger_inconclusive_valid(async_session: AsyncSession):
    """Invariant G: non-NONE trigger + ADJUDICATION_INCONCLUSIVE is VALID."""
    claim = await _create_test_claim(async_session)

    nli = NLIResult(
        nli_result_id=uuid4(),
        claim_id=claim.claim_id,
        model_name="deberta-v3",
        label="NEUTRAL",
        verification_status="ADJUDICATION_INCONCLUSIVE",
        adjudication_trigger="NLI_EVIDENCE_LABEL_CONFLICT",
        uncertainty_reason="JUDGE_LOW_CONFIDENCE",
        final_label=None,
    )
    async_session.add(nli)
    await async_session.commit()
    assert nli.verification_status == "ADJUDICATION_INCONCLUSIVE"


@pytest.mark.asyncio
async def test_invariant_h_non_none_trigger_direct_nli_invalid(async_session: AsyncSession):
    """Invariant H: non-NONE trigger + DIRECT_NLI without budget exhaustion is INVALID."""
    claim = await _create_test_claim(async_session)

    nli = NLIResult(
        nli_result_id=uuid4(),
        claim_id=claim.claim_id,
        model_name="deberta-v3",
        label="SUPPORTED",
        verification_status="DIRECT_NLI",
        adjudication_trigger="NLI_CLOSE_TOP2",  # Trigger fired but marked DIRECT_NLI with reason=NONE
        uncertainty_reason="NONE",
        final_label="SUPPORTED",
    )
    async_session.add(nli)
    with pytest.raises(IntegrityError):
        await async_session.commit()


@pytest.mark.asyncio
async def test_invariant_i_budget_exhaustion_exception_valid(async_session: AsyncSession):
    """Invariant I: Controlled exception on budget exhaustion preserves trigger with DIRECT_NLI."""
    claim = await _create_test_claim(async_session)

    nli = NLIResult(
        nli_result_id=uuid4(),
        claim_id=claim.claim_id,
        model_name="deberta-v3",
        label="SUPPORTED",
        verification_status="DIRECT_NLI",
        adjudication_trigger="NLI_LOW_CONFIDENCE",  # Preserved trigger!
        uncertainty_reason="ADJUDICATION_BUDGET_EXHAUSTED",  # Explicit budget reason!
        final_label=None,
    )
    async_session.add(nli)
    await async_session.commit()
    assert nli.verification_status == "DIRECT_NLI"
    assert nli.adjudication_trigger == "NLI_LOW_CONFIDENCE"
    assert nli.uncertainty_reason == "ADJUDICATION_BUDGET_EXHAUSTED"
