"""Serve public read-only discovery and complete policies from the active approved corpus."""

from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from starlette.responses import JSONResponse

from veritycx.knowledge.catalog import CATEGORIES, category_for, summary_for
from veritycx.knowledge.configuration import active_documents


def register_bank(app: FastAPI, mode: Literal["synthetic", "official"]) -> None:
    """Register database-independent policy routes; source mode is exclusively server owned."""

    @app.get("/bank/api/policies")
    def policies(
        request: Request,
        q: Annotated[str, Query(max_length=200)] = "",
        category: Annotated[str, Query(max_length=40)] = "",
        page: Annotated[int, Query(ge=1, le=100000)] = 1,
    ) -> JSONResponse:
        """Search full approved text and page results without silently dropping sources."""
        if set(request.query_params) - {"q", "category", "page"} or (
            category and category not in CATEGORIES
        ):
            raise HTTPException(422, "invalid_search")
        manifest, documents = active_documents(mode)
        ordered = sorted(documents, key=lambda document: (document.title.casefold(), document.id))
        terms = q.casefold().split()
        matching = [
            document
            for document in ordered
            if (not category or category_for(document, mode) == category)
            and all(term in f"{document.title} {document.content}".casefold() for term in terms)
        ]
        counts = {key: 0 for key in CATEGORIES}
        for document in documents:
            counts[category_for(document, mode)] += 1
        return JSONResponse(
            {
                "corpus_version": manifest.corpus_version,
                "mode": mode,
                "categories": [
                    {"key": key, "title": title, "count": counts[key]}
                    for key, title in CATEGORIES.items()
                    if counts[key]
                ],
                "total": len(matching),
                "page": page,
                "page_size": 12,
                "policies": [
                    summary_for(document, ordered, mode, q).model_dump(mode="json")
                    for document in matching[(page - 1) * 12 : page * 12]
                ],
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/bank/api/policies/{document_id:path}")
    def policy(document_id: str) -> JSONResponse:
        """Look up a document ID, never a filesystem path, and return the exact approved content."""
        manifest, documents = active_documents(mode)
        document = next((item for item in documents if item.id == document_id), None)
        if document is None:
            raise HTTPException(404, "policy_not_found")
        return JSONResponse(
            {
                **summary_for(document, documents, mode).model_dump(mode="json"),
                "content": document.content,
                "corpus_version": manifest.corpus_version,
                "mode": mode,
            },
            headers={"Cache-Control": "no-store"},
        )
