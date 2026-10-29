/** Render bank service discovery, shared search, and full source-backed policies around native chat. */
import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type MouseEvent,
  type ReactElement,
} from "react";
import {
  BankError,
  categoryInfo,
  fetchBank,
  isCategory,
  navigateBank,
  parseListing,
  parsePolicy,
  policyUrl,
  routeFor,
  searchUrl,
  type Category,
  type PolicyDetail,
  type PolicyListing,
} from "./bank";
import type { ChatState } from "./chat";

type ContentState =
  | { kind: "loading" }
  | { kind: "listing"; value: PolicyListing }
  | { kind: "policy"; value: PolicyDetail }
  | { kind: "missing" }
  | { kind: "unavailable" };

/** Submit a regular GET form on the homepage and local history navigation on bank pages. */
export function BankSearch({
  query = "",
  category = "",
  local = false,
}: {
  query?: string;
  category?: Category | "";
  local?: boolean;
}): ReactElement {
  /** Read form data on submission so URL state survives both keyboard and pointer input. */
  function submit(event: FormEvent<HTMLFormElement>): void {
    if (!local) return;
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("q");
    navigateBank(searchUrl(typeof value === "string" ? value : "", category));
  }
  return (
    <form
      className="bank-search"
      role="search"
      action="/bank/search"
      method="get"
      onSubmit={submit}
    >
      <label htmlFor="bank-query">Search bank information</label>
      <div className="bank-search-row">
        <input
          key={query}
          id="bank-query"
          name="q"
          type="search"
          maxLength={200}
          defaultValue={query}
          placeholder="Try monthly fees, card replacement, or transfer cutoffs"
        />
        <button type="submit" className="button button-primary">
          Search <span aria-hidden="true">↗</span>
        </button>
      </div>
      {!local && category && (
        <input type="hidden" name="category" value={category} />
      )}
    </form>
  );
}

/** Show source paragraphs and headings as safe text without discarding any policy characters. */
function PolicyText({ content }: { content: string }): ReactElement {
  return (
    <div className="policy-prose">
      {content
        .replace(/\r\n/g, "\n")
        .split(/\n\s*\n/)
        .map((paragraph, index) => {
          const heading = /^#{1,6} +([^\n]+)$/.exec(paragraph.trim())?.[1];
          return heading ? (
            <h2 key={index}>{heading}</h2>
          ) : (
            <p key={index}>{paragraph}</p>
          );
        })}
    </div>
  );
}

/** Keep page fetching independent of messaging and discard stale responses after navigation. */
export function BankPages({
  state,
  onOpen,
}: {
  state: ChatState;
  onOpen: () => void;
}): ReactElement {
  const [location, setLocation] = useState(
    () => window.location.pathname + window.location.search,
  );
  const [retry, setRetry] = useState(0);
  const [content, setContent] = useState<ContentState>({ kind: "loading" });
  const headingRef = useRef<HTMLHeadingElement>(null);
  const url = new URL(location, window.location.origin);
  const route = routeFor(url.pathname, url.search);

  useEffect(() => {
    /** Synchronize local navigation with browser Back and Forward. */
    function changed(): void {
      setLocation(window.location.pathname + window.location.search);
    }
    window.addEventListener("popstate", changed);
    return () => window.removeEventListener("popstate", changed);
  }, []);

  useEffect(() => {
    const current = new URL(location, window.location.origin);
    const target = routeFor(current.pathname, current.search);
    const controller = new AbortController();
    setContent({ kind: "loading" });
    if (target.kind === "missing") {
      setContent({ kind: "missing" });
      return () => controller.abort();
    }
    const request =
      target.kind === "policy"
        ? fetchBank(
            "/bank/api/policies/" + encodeURIComponent(target.id),
            parsePolicy,
            controller.signal,
          ).then((value): ContentState => ({ kind: "policy", value }))
        : fetchBank(
            "/bank/api/policies" +
              searchUrl(target.query, target.category, target.page).replace(
                "/bank/search",
                "",
              ),
            parseListing,
            controller.signal,
          ).then((value): ContentState => ({ kind: "listing", value }));
    void request
      .then((value) => {
        if (!controller.signal.aborted) setContent(value);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setContent({
            kind:
              error instanceof BankError && error.status === 404
                ? "missing"
                : "unavailable",
          });
      });
    return () => controller.abort();
  }, [location, retry]);

  const title =
    content.kind === "policy"
      ? content.value.title
      : content.kind === "missing"
        ? "Page not found"
        : content.kind === "unavailable"
          ? "Bank information is currently unavailable"
          : route.kind === "listing" && route.service && route.category
            ? categoryInfo[route.category].title
            : url.pathname === "/bank/search"
              ? "Find your answer."
              : "Get to know your bank.";
  useEffect(() => {
    document.title = title + " | Verity Bank information";
    headingRef.current?.focus({ preventScroll: true });
  }, [location, title]);

  /** Intercept only ordinary bank navigation; preserve new-tab and external-link browser behavior. */
  function follow(event: MouseEvent<HTMLDivElement>): void {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    )
      return;
    if (!(event.target instanceof Element)) return;
    const link = event.target.closest("a");
    if (
      !(link instanceof HTMLAnchorElement) ||
      link.target ||
      link.hasAttribute("download")
    )
      return;
    const next = new URL(link.href);
    if (
      next.origin !== window.location.origin ||
      !(next.pathname === "/bank" || next.pathname.startsWith("/bank/"))
    )
      return;
    event.preventDefault();
    navigateBank(next.pathname + next.search);
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  return (
    <div className="bank-pages shell" onClick={follow}>
      <nav className="bank-breadcrumb" aria-label="Breadcrumb">
        <a href="/">Verity home</a>
        <span aria-hidden="true">/</span>
        <a href="/bank">Bank information</a>
        {route.kind === "listing" && route.service && route.category && (
          <>
            <span aria-hidden="true">/</span>
            <span>{categoryInfo[route.category].title}</span>
          </>
        )}
      </nav>
      <p className="bank-chat-status" id="chat-status" role="status">
        <span className="status-dot" />
        {state === "ready"
          ? "VerityCX chat is ready"
          : state === "loading"
            ? "VerityCX chat is connecting"
            : "VerityCX chat is currently unavailable"}{" "}
        · Bank information is available independently.
      </p>
      <div className="bank-heading">
        <p className="eyebrow">EXPLORE. UNDERSTAND. ASK.</p>
        <h1 ref={headingRef} tabIndex={-1}>
          {title}
        </h1>
        <p>
          {route.kind === "listing" && route.service && route.category
            ? categoryInfo[route.category].description
            : "Start with the details. Find a product, read its policies, and bring your follow-up questions to VerityCX."}
        </p>
      </div>
      {content.kind === "loading" && (
        <p className="bank-message" role="status">
          Loading approved bank information…
        </p>
      )}
      {content.kind === "missing" && (
        <p className="bank-message">
          We couldn’t find that page or policy.{" "}
          <a href="/bank">Explore bank information →</a>
        </p>
      )}
      {content.kind === "unavailable" && (
        <div className="bank-message" role="alert">
          <p>
            We couldn’t load the current approved policies. Please try again.
          </p>
          <button
            type="button"
            className="button button-primary"
            data-bank-retry
            onClick={() => setRetry((value) => value + 1)}
          >
            Try again
          </button>
        </div>
      )}
      {content.kind === "listing" && route.kind === "listing" && (
        <>
          <BankSearch query={route.query} category={route.category} local />
          {url.pathname === "/bank" && !route.query && (
            <section
              className="bank-services"
              aria-labelledby="services-heading"
            >
              <div className="section-heading">
                <div>
                  <p className="eyebrow">A PLACE FOR EVERY QUESTION</p>
                  <h2 id="services-heading">
                    Explore our <em>services.</em>
                  </h2>
                </div>
                <p>What’s available, and the details that matter.</p>
              </div>
              <div className="service-grid">
                {content.value.categories.map((group, index) => (
                  <a
                    className="service-card"
                    key={group.key}
                    href={"/bank/services/" + group.key}
                  >
                    <span className="eyebrow">
                      0{index + 1} / {group.count} policies
                    </span>
                    <h3>{categoryInfo[group.key].title}</h3>
                    <p>{categoryInfo[group.key].description}</p>
                    <span className="text-link">
                      Explore policies <span aria-hidden="true">↗</span>
                    </span>
                  </a>
                ))}
              </div>
            </section>
          )}
          <section className="bank-results" aria-labelledby="results-heading">
            <div className="results-heading">
              <div>
                <p className="eyebrow">FROM OUR APPROVED DOCUMENTS</p>
                <h2 id="results-heading">
                  {route.service ? "Product & policy details" : "Bank policies"}
                </h2>
                <p role="status">
                  {content.value.total}{" "}
                  {content.value.total === 1 ? "policy" : "policies"}
                  {route.query && <> matching “{route.query}”</>}
                </p>
              </div>
              <div className="bank-filter">
                <label htmlFor="bank-category">Browse by service</label>
                <select
                  id="bank-category"
                  value={route.category}
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    navigateBank(
                      searchUrl(route.query, isCategory(value) ? value : ""),
                    );
                  }}
                >
                  <option value="">All services</option>
                  {content.value.categories.map((group) => (
                    <option key={group.key} value={group.key}>
                      {categoryInfo[group.key].title} ({group.count})
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {(route.query || route.category) && (
              <a className="clear-search" href="/bank/search">
                Clear search
              </a>
            )}
            {content.value.policies.length === 0 ? (
              <div className="bank-message">
                <h3>
                  {content.value.total === 0
                    ? "No policies found"
                    : "No policies on this page"}
                </h3>
                <p>
                  Try a product name or a shorter search, or browse all
                  available policies.
                </p>
                <a className="text-link" href="/bank/search">
                  Browse all policies →
                </a>
              </div>
            ) : (
              <div className="policy-list">
                {content.value.policies.map((policy) => (
                  <article className="policy-card" key={policy.id}>
                    <p className="eyebrow">
                      {categoryInfo[policy.category].title}
                    </p>
                    <h3>
                      <a href={policyUrl(policy.id)}>
                        {policy.title} <span aria-hidden="true">↗</span>
                      </a>
                    </h3>
                    <p>{policy.excerpt}</p>
                    {policy.conflict_ids.length > 0 && (
                      <span className="policy-badge">
                        Conflicting source versions
                      </span>
                    )}
                    <a className="text-link" href={policyUrl(policy.id)}>
                      Read full policy →
                    </a>
                  </article>
                ))}
              </div>
            )}
            <nav className="bank-pagination" aria-label="Policy result pages">
              {route.page > 1 && (
                <a
                  href={searchUrl(route.query, route.category, route.page - 1)}
                >
                  ← Previous page
                </a>
              )}
              <span>
                Page {route.page} of{" "}
                {Math.max(
                  1,
                  Math.ceil(content.value.total / content.value.page_size),
                )}
              </span>
              {route.page * content.value.page_size < content.value.total && (
                <a
                  href={searchUrl(route.query, route.category, route.page + 1)}
                >
                  Next page →
                </a>
              )}
            </nav>
          </section>
          <p className="bank-source-note">
            Showing the approved{" "}
            {content.value.mode === "synthetic"
              ? "synthetic demonstration"
              : "banking knowledge"}{" "}
            documents. Details not covered by these sources are not supplied
            here.
          </p>
        </>
      )}
      {content.kind === "policy" && (
        <div className="policy-layout">
          <article className="policy-document">
            <a
              className="text-link"
              href={"/bank/services/" + content.value.category}
            >
              ← {categoryInfo[content.value.category].title}
            </a>
            {content.value.conflict_ids.length > 0 && (
              <aside className="conflict-notice">
                <h2>Conflicting source versions</h2>
                <p>
                  These documents disagree. Both versions are available; ask
                  VerityCX for clarification before drawing a conclusion.
                </p>
                {content.value.conflict_ids.map((id) => (
                  <a key={id} href={policyUrl(id)}>
                    Read the other source version →
                  </a>
                ))}
              </aside>
            )}
            <PolicyText content={content.value.content} />
            {content.value.related_ids.length > 0 &&
              content.value.conflict_ids.length === 0 && (
                <aside className="conflict-notice">
                  <h2>Multiple sources for this policy</h2>
                  <p>
                    More than one document uses this title. Read each source for
                    its details.
                  </p>
                  {content.value.related_ids.map((id) => (
                    <a key={id} href={policyUrl(id)}>
                      Read related source {id} →
                    </a>
                  ))}
                </aside>
              )}
            <details className="policy-source">
              <summary>About this source</summary>
              <dl>
                <dt>Document</dt>
                <dd>{content.value.id}</dd>
                <dt>Collection</dt>
                <dd>
                  {content.value.mode === "synthetic"
                    ? "Synthetic demonstration policies"
                    : "Approved banking knowledge"}
                </dd>
                <dt>Corpus version</dt>
                <dd>{content.value.corpus_version}</dd>
              </dl>
            </details>
          </article>
          <aside className="policy-question">
            <p className="eyebrow">MAKE IT A CONVERSATION</p>
            <h2>A detail you’d like to understand?</h2>
            <p>Here’s a question you can copy into VerityCX:</p>
            <blockquote>
              What should I know about {content.value.title}?
            </blockquote>
            <button
              type="button"
              className="button button-primary"
              data-chat-launch
              disabled={state !== "ready"}
              aria-describedby="chat-status"
              onClick={onOpen}
            >
              Ask VerityCX <span aria-hidden="true">↗</span>
            </button>
            <p className="question-note">
              Opens support chat. Your question is not sent automatically.
            </p>
            {state !== "ready" && (
              <p role="status">
                {state === "loading"
                  ? "Chat is connecting. You can keep reading."
                  : "Chat is currently unavailable. You can still read every policy."}
              </p>
            )}
          </aside>
        </div>
      )}
      <div className="bank-boundary">
        <span aria-hidden="true">✳</span>
        <p>
          <strong>A little context helps.</strong> This is a synthetic banking
          demonstration. Use invented examples and keep real account details
          private.
        </p>
        <a href="/#good-to-know">About support →</a>
      </div>
    </div>
  );
}
