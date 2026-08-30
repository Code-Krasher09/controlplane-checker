"""ControlPlane Gateway Orchestrator Service with Multi-Label Risk, Session Risk, and Evidence Quality."""

import time
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.actions.service import ActionEngine
from app.adjudication.service import AdjudicationService
from app.domain.models import (
    ActionType,
    ClaimVerificationItem,
    CostTelemetry,
    EvidenceSnippet,
    GatewayInspectRequest,
    GatewayInspectResponse,
    PolicyEventItem,
    PreflightRequest,
    RiskAssessmentResult,
    RiskLevel,
    SessionRiskTelemetry,
    SeverityLevel,
    TimingTelemetry,
)
from app.gateway.model_adapter import MockModelProvider, ModelProvider
from app.persistence.models import (
    AuditEvent,
    Claim,
    ClaimEvidence,
    Evidence,
    Intervention,
    NLIResult,
    PolicyEvent,
    RepairAttempt,
    Request,
    Response,
    RiskAssessment,
)
from app.persistence.redis import RuntimeStateStore
from app.preflight.service import PreflightService
from app.repair.service import RepairPlanner, RepairService
from app.risk.multi_label import MultiLabelRiskAggregator
from app.risk.service import RiskEngine
from app.risk.session_risk import SessionRiskTracker
from app.tier0.service import Tier0Service
from app.tier1.service import Tier1Service


class GatewayService:
    """End-to-end orchestrator for the ControlPlane pipeline with Phase 3 enterprise capabilities."""

    def __init__(
        self,
        model_provider: Optional[ModelProvider] = None,
        preflight_service: Optional[PreflightService] = None,
        tier0_service: Optional[Tier0Service] = None,
        risk_engine: Optional[RiskEngine] = None,
        tier1_service: Optional[Tier1Service] = None,
        adjudication_service: Optional[AdjudicationService] = None,
        repair_service: Optional[RepairService] = None,
        action_engine: Optional[ActionEngine] = None,
        state_store: Optional[RuntimeStateStore] = None,
        session_risk_tracker: Optional[SessionRiskTracker] = None,
        multi_label_aggregator: Optional[MultiLabelRiskAggregator] = None,
    ):
        self.model_provider = model_provider or MockModelProvider()
        self.preflight_service = preflight_service or PreflightService()
        self.tier0_service = tier0_service or Tier0Service()
        self.risk_engine = risk_engine or RiskEngine()
        if tier1_service is None:
            from app.tier1.hybrid_verifier import HighSeverityHybridVerifier
            self.tier1_service = Tier1Service(verifier=HighSeverityHybridVerifier(enable_gemini=True))
        else:
            self.tier1_service = tier1_service
        self.state_store = state_store or RuntimeStateStore()
        self.adjudication_service = adjudication_service or AdjudicationService(state_store=self.state_store)
        self.repair_service = repair_service or RepairService()
        self.action_engine = action_engine or ActionEngine()
        self.session_risk_tracker = session_risk_tracker or SessionRiskTracker(self.state_store)
        self.multi_label_aggregator = multi_label_aggregator or MultiLabelRiskAggregator()

    async def inspect(
        self,
        request: GatewayInspectRequest,
        db_session: AsyncSession,
    ) -> GatewayInspectResponse:
        """Execute full runtime pipeline from Pre-flight to Audit with Session Risk and Multi-label evaluation."""
        timing = TimingTelemetry()
        start_total = time.perf_counter()
        req_id = request.request_id or uuid4()
        session_id = request.session_id or str(req_id)

        # -------------------------------------------------------------
        # STEP 1: PRE-FLIGHT GATE
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        preflight_req = PreflightRequest(
            application_id=request.application_id,
            policy_version_id=request.policy_version_id,
            prompt=request.prompt,
            session_id=session_id,
        )
        preflight_resp, app_model, policy_version = await self.preflight_service.evaluate(preflight_req, db_session)
        timing.preflight_ms = round((time.perf_counter() - t0) * 1000, 2)

        # If Pre-flight Denies: Stop immediately and persist trace
        if preflight_resp.action != ActionType.ALLOW:
            req_db = Request(
                request_id=req_id,
                application_id=request.application_id,
                policy_version_id=policy_version.policy_version_id if policy_version else None,
                session_id=session_id,
                prompt=request.prompt,
                status="DENIED_PREFLIGHT",
                preflight_action=preflight_resp.action.value,
            )
            interv_db = Intervention(
                intervention_id=uuid4(),
                request_id=req_id,
                action=preflight_resp.action.value,
                trigger_type="PREFLIGHT_BUDGET_DENIAL",
                trigger_reason=", ".join(preflight_resp.reasons),
                policy_version_id=policy_version.policy_version_id if policy_version else None,
            )
            audit_db = AuditEvent(
                event_id=uuid4(),
                request_id=req_id,
                event_type="REQUEST_DENIED_PREFLIGHT",
                component="PreflightGate",
                event_data={"reasons": preflight_resp.reasons, "action": preflight_resp.action.value},
            )
            db_session.add_all([req_db, interv_db, audit_db])
            await db_session.commit()

            timing.total_controlplane_ms = round((time.perf_counter() - start_total) * 1000, 2)
            return GatewayInspectResponse(
                request_id=req_id,
                application_id=request.application_id,
                policy_version_id=policy_version.policy_version_id if policy_version else None,
                action=preflight_resp.action,
                final_content=None,
                risk_assessment=RiskAssessmentResult(
                    risk_level=RiskLevel.CRITICAL,
                    severity=SeverityLevel.HIGH,
                    verification_required=False,
                    reasons=preflight_resp.reasons,
                ),
                cost_telemetry=CostTelemetry(),
                timing_telemetry=timing,
            )

        policy_config = app_model.policies[0]
        thresholds = policy_version.thresholds if policy_version and policy_version.thresholds else {}
        input_tokens = len(request.prompt) // 4

        # -------------------------------------------------------------
        # STEP 2: SESSION RISK LOOKUP
        # -------------------------------------------------------------
        t0_sess = time.perf_counter()
        session_telemetry = await self.session_risk_tracker.get_session_telemetry(session_id, thresholds)
        prior_session_score = session_telemetry.current_score
        timing.session_risk_ms += round((time.perf_counter() - t0_sess) * 1000, 2)

        # -------------------------------------------------------------
        # STEP 3: INITIAL AI MODEL GENERATION
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        if request.response:
            response_content = request.response
            model_latency = int(request.model_metadata.get("latency_ms", 20))
            output_tokens = int(request.model_metadata.get("output_tokens", len(response_content) // 4))
            model_id = None
        else:
            model_res = await self.model_provider.generate(
                prompt=request.prompt,
                scenario=request.scenario,
                max_tokens=preflight_resp.output_token_budget,
            )
            response_content = model_res.content
            model_latency = model_res.latency_ms
            output_tokens = model_res.output_tokens
            model_id = model_res.model_id
        timing.model_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Create Root Request DB record
        req_db = Request(
            request_id=req_id,
            application_id=request.application_id,
            model_id=model_id,
            policy_version_id=policy_version.policy_version_id if policy_version else None,
            session_id=session_id,
            prompt=request.prompt,
            mode=request.model_metadata.get("mode", "REALTIME"),
            status="PROCESSING",
            preflight_action="ALLOW",
            input_tokens=input_tokens,
        )
        db_session.add(req_db)
        
        ablation_mode = request.model_metadata.get("ablation_mode", "CONTROLPLANE_NLI_ADJUDICATION")

        # -------------------------------------------------------------
        # ABLATION MODE: NO_CHECKER
        # -------------------------------------------------------------
        if ablation_mode == "NO_CHECKER":
            timing.total_controlplane_ms = round((time.perf_counter() - start_total) * 1000, 2)
            cost_telemetry = self.tier0_service.cost_estimator.calculate_cost(
                input_tokens=input_tokens,
                output_tokens=len(response_content) // 4,
                adjudication_calls=0,
                latency_ms=int(timing.total_controlplane_ms),
                retry_attempts=0,
            )
            return GatewayInspectResponse(
                request_id=req_id,
                application_id=request.application_id,
                policy_version_id=policy_version.policy_version_id if policy_version else None,
                action=ActionType.ALLOW,
                final_content=response_content,
                risk_assessment=RiskAssessmentResult(
                    risk_level=RiskLevel.LOW,
                    severity=SeverityLevel.LOW,
                    verification_required=False,
                ),
                cost_telemetry=cost_telemetry,
                timing_telemetry=timing,
            )

        # -------------------------------------------------------------
        # REPAIR & VERIFICATION LOOP (Bounded)
        # -------------------------------------------------------------
        attempt_number = 0
        max_repairs = int(policy_config.max_repair_attempts or 2)
        repair_history: List[Dict[str, Any]] = []
        total_adjudication_calls = 0
        total_adjudication_cost = 0.0
        persisted_evidence_ids: Set[UUID] = set()
        accumulated_risk_types: Set[str] = set()

        current_response_content = response_content
        current_resp_id = uuid4()

        final_action = ActionType.ALLOW
        current_risk_result: Optional[RiskAssessmentResult] = None
        current_policy_events: List[PolicyEventItem] = []
        current_verified_claims: List[ClaimVerificationItem] = []

        while True:
            # 1. Persist Response DB entity
            resp_db = Response(
                response_id=current_resp_id,
                request_id=req_id,
                attempt_number=attempt_number,
                content=current_response_content,
                output_tokens=len(current_response_content) // 4,
                latency_ms=model_latency if attempt_number == 0 else 30,
                generated_by_model=model_id,
            )
            db_session.add(resp_db)

            # 2. Tier 0 Responsibility & Consistency
            t0 = time.perf_counter()
            semantic_consistency_enabled = request.model_metadata.get("semantic_consistency_enabled", False)
            policy_events, consistency_score = self.tier0_service.run_checks(
                request.prompt, current_response_content, semantic_consistency_enabled=semantic_consistency_enabled
            )
            timing.tier0_ms += round((time.perf_counter() - t0) * 1000, 2)
            current_policy_events = policy_events

            for ev in policy_events:
                ev_db = PolicyEvent(
                    policy_event_id=uuid4(),
                    response_id=current_resp_id,
                    event_type=ev.event_type,
                    detector=ev.detector,
                    severity=ev.severity.value if ev.severity else None,
                    confidence=ev.confidence,
                    matched_text=ev.matched_text,
                    metadata_=ev.metadata,
                    action_taken=ev.action_taken.value if ev.action_taken else None,
                )
                db_session.add(ev_db)

            # 3. Risk & Severity Assessment (Aware of Session Risk State)
            t0 = time.perf_counter()
            risk_result = self.risk_engine.assess(
                prompt=request.prompt,
                response=current_response_content,
                policy_config=policy_config,
                policy_version=policy_version,
                policy_events=policy_events,
                semantic_consistency_score=consistency_score,
                task_signals=request.model_metadata.get("task_signals", {}),
                session_state={"score": session_telemetry.current_score, "level": session_telemetry.level},
            )
            timing.risk_ms += round((time.perf_counter() - t0) * 1000, 2)
            current_risk_result = risk_result

            # 4. Tier 1 Semantic Verification & Evidence Quality
            verified_claims: List[ClaimVerificationItem] = []
            claim_evidence_pairs: List[Tuple[ClaimVerificationItem, List[EvidenceSnippet]]] = []

            is_hard_blocked = any(ev.severity == SeverityLevel.CRITICAL for ev in policy_events)

            if risk_result.verification_required and not is_hard_blocked:
                t0_t1 = time.perf_counter()
                app_type = app_model.application_type if app_model else None
                pol_scope = policy_version.industry if policy_version else None
                verified_claims, claim_evidence_pairs = self.tier1_service.verify_response(
                    current_response_content,
                    policy_thresholds=thresholds,
                    application_profile=app_type,
                    policy_scope=pol_scope,
                )
                timing.tier1_ms += round((time.perf_counter() - t0_t1) * 1000, 2)

                # Execute Confidence Gate & Selective Adjudication per claim
                t0_adj = time.perf_counter()
                adjudicated_claims: List[ClaimVerificationItem] = []
                for claim_item, evidence_list in claim_evidence_pairs:
                    # Construct pseudo-NLI response for gate evaluation
                    from app.domain.models import VerifierResponse
                    pseudo_nli = VerifierResponse(
                        label=claim_item.final_label or "SUPPORTED",
                        nli_confidence=claim_item.nli_confidence or 0.9,
                        top2_scores=claim_item.top2_scores,
                        evidence_ids=[e.evidence_id for e in evidence_list],
                        verification_status=claim_item.verification_status,
                        evidence_quality=claim_item.evidence_quality,
                    )

                    force_adjudicate = ablation_mode in ("ALWAYS_ON_JUDGE_REAL", "ALWAYS_ON_JUDGE_MOCK")
                    skip_adjudicate = ablation_mode == "CONTROLPLANE_NLI_ONLY"

                    updated_claim, was_invoked, adj_cost = await self.adjudication_service.evaluate_and_adjudicate(
                        claim=claim_item,
                        evidence=evidence_list,
                        nli_result=pseudo_nli,
                        policy_config=policy_config,
                        policy_version=policy_version,
                        session_id=session_id,
                        request_id=req_id,
                        scenario=request.judge_scenario,
                        force_adjudicate=force_adjudicate,
                        skip_adjudicate=skip_adjudicate,
                    )
                    if was_invoked:
                        total_adjudication_calls += 1
                        total_adjudication_cost += adj_cost
                    elif updated_claim.adjudicator_model and ("gemini" in updated_claim.adjudicator_model.lower() or "flash" in updated_claim.adjudicator_model.lower()):
                        total_adjudication_calls += 1
                        total_adjudication_cost += 0.0003

                    adjudicated_claims.append(updated_claim)

                    # Persist Claim, Evidence, and NLI Results
                    claim_db = Claim(
                        claim_id=updated_claim.claim_id,
                        response_id=current_resp_id,
                        claim_index=updated_claim.claim_index,
                        claim_text=updated_claim.claim_text,
                        severity=updated_claim.severity.value if updated_claim.severity else "MEDIUM",
                    )
                    db_session.add(claim_db)

                    primary_ev_id = None
                    for ev_snippet in evidence_list:
                        existing_ev = await db_session.get(Evidence, ev_snippet.evidence_id)
                        if existing_ev is None and ev_snippet.evidence_id not in persisted_evidence_ids:
                            ev_db = Evidence(
                                evidence_id=ev_snippet.evidence_id,
                                source_type=ev_snippet.source_type or "KB",
                                source_id=ev_snippet.source_id,
                                content_snippet=ev_snippet.content_snippet,
                                quality_score=ev_snippet.quality.quality_score if ev_snippet.quality else 0.9,
                            )
                            db_session.add(ev_db)
                            persisted_evidence_ids.add(ev_snippet.evidence_id)

                        link_db = ClaimEvidence(
                            claim_id=updated_claim.claim_id,
                            evidence_id=ev_snippet.evidence_id,
                            relevance_score=ev_snippet.quality.relevance if ev_snippet.quality else 0.95,
                        )
                        db_session.add(link_db)
                        if primary_ev_id is None:
                            primary_ev_id = ev_snippet.evidence_id

                    if primary_ev_id is not None:
                        v_status = updated_claim.verification_status.value if updated_claim.verification_status.value in ('DIRECT_NLI', 'ADJUDICATED', 'ADJUDICATION_INCONCLUSIVE') else 'DIRECT_NLI'
                        adj_trigger = updated_claim.adjudication_trigger.value
                        unc_reason = updated_claim.uncertainty_reason.value if updated_claim.uncertainty_reason else "NONE"

                        # Ensure compliance with chk_nli_trigger_status_consistency
                        if v_status == 'DIRECT_NLI' and unc_reason != 'ADJUDICATION_BUDGET_EXHAUSTED':
                            adj_trigger = 'NONE'
                            unc_reason = 'NONE'
                        elif v_status in ('ADJUDICATED', 'ADJUDICATION_INCONCLUSIVE') and adj_trigger == 'NONE':
                            adj_trigger = 'NLI_LOW_CONFIDENCE'

                        nli_db = NLIResult(
                            nli_result_id=uuid4(),
                            claim_id=updated_claim.claim_id,
                            evidence_id=primary_ev_id,
                            model_name=getattr(self.tier1_service.verifier, "model_name", "deterministic-nli-v1"),
                            label=updated_claim.final_label or "SUPPORTED",
                            nli_confidence=updated_claim.nli_confidence or 0.9,
                            verification_status=v_status,
                            adjudication_trigger=adj_trigger,
                            uncertainty_reason=unc_reason,
                            adjudicator_model=updated_claim.adjudicator_model,
                            adjudicator_confidence=updated_claim.adjudicator_confidence,
                            final_label=updated_claim.final_label if v_status != 'ADJUDICATION_INCONCLUSIVE' else None,
                        )
                        db_session.add(nli_db)

                timing.adjudication_ms += round((time.perf_counter() - t0_adj) * 1000, 2)
                verified_claims = adjudicated_claims

            current_verified_claims = verified_claims

            # 5. Multi-Label Risk Aggregation and Action Resolution
            t0 = time.perf_counter()
            (
                all_risk_types,
                highest_sev,
                candidate_actions,
                resolved_action,
                precedence_reason,
            ) = self.multi_label_aggregator.aggregate_risks(
                policy_events=policy_events,
                claims=verified_claims,
                base_risk_result=risk_result,
                policy_config=policy_config,
                policy_version=policy_version,
                current_repair_attempt=attempt_number,
            )
            timing.action_ms += round((time.perf_counter() - t0) * 1000, 2)

            accumulated_risk_types.update(all_risk_types)
            risk_result.risk_types = sorted(list(accumulated_risk_types))
            risk_result.highest_severity = highest_sev
            risk_result.candidate_actions = candidate_actions
            final_action = resolved_action

            # Persist Risk Assessment DB record
            risk_db = RiskAssessment(
                risk_assessment_id=uuid4(),
                request_id=req_id,
                response_id=current_resp_id,
                task_risk_score=risk_result.task_risk_score,
                response_risk_score=risk_result.response_risk_score,
                evidence_availability_score=risk_result.evidence_availability_score,
                sensitivity_score=risk_result.sensitivity_score,
                severity_score=risk_result.severity_score,
                final_risk_score=risk_result.final_risk_score,
                risk_level=risk_result.risk_level.value,
                verification_required=risk_result.verification_required,
                reason={
                    "reasons": risk_result.reasons,
                    "risk_types": all_risk_types,
                    "candidate_actions": [a.value for a in candidate_actions],
                    "precedence_reason": precedence_reason,
                    "session_level": session_telemetry.level,
                },
            )
            db_session.add(risk_db)

            # 6. Check if REPAIR loop should execute
            if resolved_action == ActionType.REPAIR and attempt_number < max_repairs:
                t0_rep = time.perf_counter()
                failed_claims = [c for c in verified_claims if c.final_label == "CONTRADICTED"]
                all_evidence: List[EvidenceSnippet] = []
                for _, ev_list in claim_evidence_pairs:
                    all_evidence.extend(ev_list)

                # Plan repair
                repair_plan = self.repair_service.planner.plan_repair(
                    failed_claims=failed_claims,
                    evidence=all_evidence,
                    previous_response=current_response_content,
                    attempt_number=attempt_number + 1,
                    policy_config=policy_config,
                )

                # Call Model Adapter for repair
                next_resp_id = uuid4()
                repaired_res = await self.model_provider.generate_repair(
                    original_prompt=request.prompt,
                    previous_response=current_response_content,
                    failed_claims=failed_claims,
                    evidence=all_evidence,
                    repair_prompt=repair_plan.repair_prompt,
                    scenario=request.scenario,
                )

                # Record RepairAttempt DB entity
                repair_db = RepairAttempt(
                    repair_id=uuid4(),
                    request_id=req_id,
                    source_response_id=current_resp_id,
                    repaired_response_id=next_resp_id,
                    attempt_number=attempt_number + 1,
                    failed_claim_id=failed_claims[0].claim_id if failed_claims else None,
                    repair_prompt=repair_plan.repair_prompt,
                    outcome="RETRY_REQUIRED",
                )
                db_session.add(repair_db)

                repair_history.append({
                    "attempt": attempt_number + 1,
                    "failed_claims_count": len(failed_claims),
                    "repair_prompt": repair_plan.repair_prompt,
                    "previous_content": current_response_content,
                    "repaired_content": repaired_res.content,
                    "repaired_preview": repaired_res.content[:80],
                })

                timing.repair_ms += round((time.perf_counter() - t0_rep) * 1000, 2)

                # Advance loop state
                attempt_number += 1
                current_response_content = repaired_res.content
                current_resp_id = next_resp_id
                await self.state_store.increment_retry_count(str(req_id))
                continue
            else:
                break

        # If repair was needed but attempts exhausted, ensure final action is ESCALATE
        if final_action == ActionType.REPAIR:
            final_action = ActionType.ESCALATE

        # -------------------------------------------------------------
        # STEP 7: SESSION RISK RECORDING & UPDATE
        # -------------------------------------------------------------
        t0_sess = time.perf_counter()
        final_session_telemetry = await self.session_risk_tracker.record_turn_outcome(
            session_id=session_id,
            prior_score=prior_session_score,
            policy_events=current_policy_events,
            claims=current_verified_claims,
            action=final_action,
            policy_thresholds=thresholds,
        )
        timing.session_risk_ms += round((time.perf_counter() - t0_sess) * 1000, 2)

        # -------------------------------------------------------------
        # STEP 8: FINAL PERSISTENCE & AUDIT
        # -------------------------------------------------------------
        req_db.status = "COMPLETED" if final_action in (ActionType.ALLOW, ActionType.WARN) else "INTERVENED"

        interv_db = Intervention(
            intervention_id=uuid4(),
            request_id=req_id,
            response_id=current_resp_id,
            action=final_action.value,
            trigger_type="PII_BLOCK" if final_action == ActionType.BLOCK else "POLICY_ACTION",
            trigger_reason=", ".join(current_risk_result.reasons if current_risk_result else []),
            policy_version_id=policy_version.policy_version_id if policy_version else None,
        )
        audit_db = AuditEvent(
            event_id=uuid4(),
            request_id=req_id,
            response_id=current_resp_id,
            event_type="REQUEST_INSPECT_COMPLETED",
            component="Gateway",
            event_data={
                "action": final_action.value,
                "repair_attempts": attempt_number,
                "adjudications": total_adjudication_calls,
                "risk_types": current_risk_result.risk_types if current_risk_result else [],
                "session_score": final_session_telemetry.current_score,
                "session_level": final_session_telemetry.level,
            },
        )
        db_session.add_all([interv_db, audit_db])
        await db_session.commit()

        # -------------------------------------------------------------
        # STEP 9: TELEMETRY & RESPONSE STRUCTURE
        # -------------------------------------------------------------
        timing.total_controlplane_ms = round((time.perf_counter() - start_total) * 1000, 2)

        cost_telemetry = self.tier0_service.cost_estimator.calculate_cost(
            input_tokens=input_tokens,
            output_tokens=len(current_response_content) // 4,
            adjudication_calls=total_adjudication_calls,
            latency_ms=int(timing.total_controlplane_ms),
            retry_attempts=attempt_number,
        )
        cost_telemetry.adjudication_calls = total_adjudication_calls
        cost_telemetry.repair_attempts = attempt_number

        final_content = current_response_content if final_action in (ActionType.ALLOW, ActionType.WARN) else None

        applied_policy_info = {
            "application_id": str(request.application_id),
            "application_name": app_model.name,
            "policy_name": policy_config.policy_name,
            "policy_version_number": policy_version.version_number if policy_version else 1,
            "risk_appetite": policy_config.risk_appetite,
            "require_grounding": policy_config.require_grounding,
            "thresholds": thresholds,
        }

        return GatewayInspectResponse(
            request_id=req_id,
            application_id=request.application_id,
            policy_version_id=policy_version.policy_version_id if policy_version else None,
            action=final_action,
            final_content=final_content,
            risk_assessment=current_risk_result or RiskAssessmentResult(
                risk_level=RiskLevel.LOW,
                severity=SeverityLevel.LOW,
                verification_required=False,
            ),
            policy_events=current_policy_events,
            claims=current_verified_claims,
            repair_history=repair_history,
            adjudication_invocations=total_adjudication_calls,
            session_risk=final_session_telemetry,
            applied_policy=applied_policy_info,
            cost_telemetry=cost_telemetry,
            timing_telemetry=timing,
        )
