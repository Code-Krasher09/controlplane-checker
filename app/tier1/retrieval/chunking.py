"""Deterministic document chunker for enterprise evidence retrieval."""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Deterministic document chunk with rich provenance metadata."""

    chunk_id: str
    source_id: str
    document_id: str
    document_version: str
    timestamp: str
    authority: str
    application_profile: Optional[str] = None
    policy_scope: Optional[str] = None
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentChunker:
    """Chunks structured enterprise documents while preserving semantic boundaries and metadata."""

    def __init__(
        self,
        target_chunk_chars: int = 250,
        overlap_sentences: int = 1,
        min_chunk_chars: int = 30,
    ):
        self.target_chunk_chars = target_chunk_chars
        self.overlap_sentences = overlap_sentences
        self.min_chunk_chars = min_chunk_chars

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentence units preserving punctuation."""
        # Split on sentence boundaries or paragraph breaks
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
        sentences = [s.strip() for s in raw_sentences if s.strip()]
        return sentences

    def chunk_document(
        self,
        document_id: str,
        source_id: str,
        text: str,
        document_version: str = "v1.0",
        timestamp: str = "2026-01-01T00:00:00Z",
        authority: str = "HIGH",
        application_profile: Optional[str] = None,
        policy_scope: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[DocumentChunk]:
        """Chunk a document into overlapping, metadata-rich DocumentChunk objects."""
        if not text or not text.strip():
            return []

        sentences = self._split_into_sentences(text)
        if not sentences:
            return []

        chunks: List[DocumentChunk] = []
        current_sentences: List[str] = []
        current_len = 0
        chunk_idx = 0

        for i, sentence in enumerate(sentences):
            current_sentences.append(sentence)
            current_len += len(sentence) + 1

            # When target length reached or at the end
            if current_len >= self.target_chunk_chars or i == len(sentences) - 1:
                chunk_text = " ".join(current_sentences).strip()
                if len(chunk_text) >= self.min_chunk_chars:
                    chunk_id = f"{document_id}__chunk_{chunk_idx:03d}"
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            source_id=source_id,
                            document_id=document_id,
                            document_version=document_version,
                            timestamp=timestamp,
                            authority=authority,
                            application_profile=application_profile,
                            policy_scope=policy_scope,
                            content=chunk_text,
                            metadata=extra_metadata or {},
                        )
                    )
                    chunk_idx += 1

                # Overlap: keep the last N sentences for the next window
                if self.overlap_sentences > 0 and len(current_sentences) > self.overlap_sentences:
                    current_sentences = current_sentences[-self.overlap_sentences :]
                    current_len = sum(len(s) + 1 for s in current_sentences)
                else:
                    current_sentences = []
                    current_len = 0

        # If any trailing text wasn't added and exceeds min size
        if current_sentences:
            chunk_text = " ".join(current_sentences).strip()
            if len(chunk_text) >= self.min_chunk_chars:
                chunk_id = f"{document_id}__chunk_{chunk_idx:03d}"
                # avoid exact duplicate of previous chunk
                if not chunks or chunks[-1].content != chunk_text:
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            source_id=source_id,
                            document_id=document_id,
                            document_version=document_version,
                            timestamp=timestamp,
                            authority=authority,
                            application_profile=application_profile,
                            policy_scope=policy_scope,
                            content=chunk_text,
                            metadata=extra_metadata or {},
                        )
                    )

        return chunks
