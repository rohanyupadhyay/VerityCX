"""Build deterministic paragraph/heading sections with stable non-overlapping anchors."""

import re
from hashlib import sha256

from veritycx.knowledge.models import EvidenceSection, KnowledgeDocument


def sections(document: KnowledgeDocument, corpus_version: str) -> list[EvidenceSection]:
    """Split normalized prose on paragraphs/word boundaries, capping each section at 2000."""
    result: list[EvidenceSection] = []
    heading = document.title
    for block in re.split(r"\n\s*\n|(?m:^[ \t]*(?=#))", document.content.replace("\r\n", "\n")):
        content = block.strip()
        if not content:
            continue
        if content.startswith("#"):
            heading = document.title + " / " + content.splitlines()[0].lstrip("# ")
        while content:
            end = min(2000, len(content))
            if end < len(content):
                boundary = content.rfind(" ", 0, end)
                if boundary > 0:
                    end = boundary
            passage = content[:end].strip()
            content = content[end:].lstrip()
            if passage:
                result.append(
                    EvidenceSection(
                        corpus_version=corpus_version,
                        document_id=document.id,
                        section_id=f"{document.id}:{len(result) + 1:04}",
                        section_hash=sha256(passage.encode()).hexdigest(),
                        title=heading,
                        content=passage,
                    )
                )
    return result
