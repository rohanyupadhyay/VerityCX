-- Extend the rewrite journal additively; historical rows keep unknown scope.
ALTER TABLE support_app.query_rewrites
 DROP CONSTRAINT query_rewrites_prompt_version_check,
 ADD CONSTRAINT query_rewrites_prompt_version_check CHECK (prompt_version IN (1,2)),
 DROP CONSTRAINT query_rewrites_retrieval_mode_check,
 ADD CONSTRAINT query_rewrites_retrieval_mode_check
   CHECK (retrieval_mode IN ('primary','synonym','category','empty')),
 ADD COLUMN search_scope text CHECK (search_scope IN ('focused','category_overview')),
 ADD COLUMN category_keys jsonb CHECK (
   category_keys IS NULL OR (
     jsonb_typeof(category_keys) = 'array' AND jsonb_array_length(category_keys) <= 6
     AND category_keys <@ '["accounts","savings","cards","payments","deposits","other"]'::jsonb
   )
 ),
 ADD COLUMN eligible_document_count integer CHECK (eligible_document_count >= 0),
 ADD COLUMN represented_document_count integer CHECK (represented_document_count >= 0),
 ADD COLUMN coverage_truncated boolean,
 ADD CONSTRAINT query_rewrites_scope_consistency CHECK (
   (search_scope IS NULL AND category_keys IS NULL AND eligible_document_count IS NULL
    AND represented_document_count IS NULL AND coverage_truncated IS NULL)
   OR
   (search_scope IS NOT NULL AND search_scope='focused'
    AND category_keys IS NOT NULL AND category_keys='[]'::jsonb
    AND eligible_document_count IS NULL AND represented_document_count IS NULL
    AND coverage_truncated IS NULL AND retrieval_mode IS NOT NULL
    AND retrieval_mode IN ('primary','synonym','empty'))
   OR
   (search_scope IS NOT NULL AND search_scope='category_overview'
    AND category_keys IS NOT NULL AND jsonb_array_length(category_keys)>0
    AND eligible_document_count IS NOT NULL AND represented_document_count IS NOT NULL
    AND coverage_truncated IS NOT NULL
    AND represented_document_count<=eligible_document_count
    AND coverage_truncated=(represented_document_count<eligible_document_count)
    AND retrieval_mode IS NOT NULL
    AND ((represented_document_count=0 AND retrieval_mode='empty')
      OR (represented_document_count>0 AND retrieval_mode='category')))
 );

-- Store event provenance instead of assigning the newest prompt to recovered history.
ALTER TABLE support_app.audit
 ADD COLUMN prompt_version integer CHECK (prompt_version IN (1,2,3));
