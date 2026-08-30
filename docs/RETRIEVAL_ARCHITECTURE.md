# ControlPlane Retrieval Architecture (Phase 7)

## 1. Overview & Objectives
The retrieval subsystem supplies grounding evidence snippets to ControlPlane Tier 1 verification without changing the core ControlPlane orchestrator or epistemic invariants. It provides a clean, provider-agnostic interface supporting three retrieval configurations:
1. **LEXICAL**: Normalized keyword and stem overlap retrieval.
2. **SEMANTIC**: Dense vector retrieval powered by FAISS CPU and sentence transformers (`all-MiniLM-L6-v2`).
3. **HYBRID**: Convex combination of normalized semantic similarity and lexical overlap with metadata filtering.

```
                  +-----------------------------------+
                  |        ControlPlane Tier 1        |
                  +-----------------+-----------------+
                                    |
                    retrieve(query, app_profile, scope)
                                    |
                                    v
                  +-----------------------------------+
                  |     BaseEvidenceRepository        |
                  +-----------------+-----------------+
                                    |
          +-------------------------+-------------------------+
          |                         |                         |
          v                         v                         v
+-------------------+     +-------------------+     +-------------------+
|  Lexical Evidence |     | Semantic Evidence |     |  Hybrid Evidence  |
|    Repository     |     |    Repository     |     |    Repository     |
+-------------------+     +---------+---------+     +---------+---------+
                                    |                         |
                           +--------v--------+                |
                           |    FAISS CPU    |<---------------+
                           |  (IndexFlatIP)  |
                           +-----------------+
```

---

## 2. Abstractions & Interface Contract
All retrieval implementations adhere to `BaseEvidenceRepository`:

```python
class BaseEvidenceRepository(abc.ABC):
    @abc.abstractmethod
    def retrieve(
        self,
        query: str,
        application_profile: Optional[str] = None,
        policy: Optional[str] = None,
        top_k: int = 3,
    ) -> List[EvidenceSnippet]:
        """Retrieve relevant evidence snippets for a query under optional scope filters."""
        pass
```

### Embedding Abstraction
`SemanticEvidenceRepository` delegates vector generation to an `EmbeddingProvider` interface:
- **`RealEmbeddingProvider`**: Uses `SentenceTransformer("all-MiniLM-L6-v2")` to produce 384-dimensional normalized float32 embeddings.
- **`DeterministicMockEmbeddingProvider`**: Hash-based deterministic embedding generator for unit tests.

---

## 3. Document Chunking Strategy
Document chunking is handled deterministically by `DocumentChunker`:
- **Target Size**: 250 characters (~35-50 words) per chunk.
- **Overlap**: 1 sentence window.
- **Minimum Size**: 30 characters (suppresses meaningless fragments).
- **Boundary Splitting**: Splits along natural punctuation boundaries (`[.!?]`, newline) to preserve complete semantic propositions for NLI verifier consumption.
- **Provenance Metadata**: Every `DocumentChunk` retains:
  `chunk_id`, `source_id`, `document_id`, `document_version`, `timestamp`, `authority`, `application_profile`, `policy_scope`, `content`, `metadata`.

---

## 4. Vector Indexing Pipeline
- **Index Engine**: FAISS CPU (`IndexFlatIP`).
- **Vector Normalization**: All chunk and query vectors are L2-normalized, guaranteeing that FAISS Inner Product ($X \cdot Y$) corresponds exactly to Cosine Similarity.
- **Index Artifacts**:
  - `data/index/faiss_index.bin`: Binary FAISS index.
  - `data/index/metadata.json`: Chunk provenance list.
  - `data/index/manifest.json`: Index build manifest tracking model, dimension, chunk count, timestamp, and version.

---

## 5. Pre-Retrieval Metadata Filtering
To prevent cross-domain contamination (e.g. applying retail return rules to HR hiring claims), candidate chunks are filtered **BEFORE** top-k selection:
1. `application_profile`: Ensures chunks restricted to specific apps (e.g. `CUSTOMER_SUPPORT`, `INTERNAL_KNOWLEDGE`, `DECISION_SUPPORT`) are only retrieved within valid application contexts.
2. `policy_scope`: Isolates regulatory domains (`RETAIL`, `FINANCIAL`, `HR`, `TELECOM`, `SECURITY`, `TRAVEL`).
3. `authority`: Enforces minimum authority thresholds where required.

---

## 6. Hybrid Scoring Formulation
The `HybridEvidenceRepository` merges candidates from semantic and lexical channels using transparent scoring:

$$\text{HybridScore} = \alpha \cdot S_{\text{semantic}} + (1 - \alpha) \cdot S_{\text{lexical}}$$

- **Default $\alpha$**: 0.5 (equal weighting between dense semantic match and exact lexical overlap).
- **Quality Relevance**: Sets `relevance` in `ClaimEvidenceQuality` to the bounded score, allowing the post-retrieval `EvidenceQualityEvaluator` to assess evidence adequacy independently.

---

## 7. Performance & Caching
`SemanticEvidenceRepository` integrates an in-memory LRU query cache:
- **Cache Key**: `hash(query, app_profile, policy_scope, top_k)`
- **Cold Latency**: ~480-550ms (initial index search and embedding warm-up).
- **Warm Latency**: ~6-10ms per retrieval call.
