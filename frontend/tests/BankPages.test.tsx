/** Exercise real bank pages using a controlled HTTP boundary and browser history. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { BankPages } from "../src/BankPages";

let root: Root;
let container: HTMLDivElement;
const summary = {
  id: "policy-02",
  title: "Birch checking monthly fee",
  category: "accounts",
  excerpt: "An approved checking fee.",
  conflict_ids: [],
  related_ids: [],
};
const listing = {
  corpus_version: "synthetic-reviewed",
  mode: "synthetic",
  categories: [
    { key: "accounts", title: "Accounts & everyday banking", count: 13 },
  ],
  total: 13,
  page: 1,
  page_size: 12,
  policies: [summary],
};
const policy = {
  ...summary,
  content:
    "# Checking details\n\nFive synthetic dollars.\n\n<script>literal content</script>",
  corpus_version: "synthetic-reviewed",
  mode: "synthetic",
};

/** Set the route and notify the same history event used by Back/Forward. */
function visit(url: string): void {
  window.history.pushState(null, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
  window.history.replaceState(null, "", "/bank");
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL) =>
        new Response(
          JSON.stringify(
            String(input).startsWith("/bank/api/policies/") ? policy : listing,
          ),
        ),
    ),
  );
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  window.history.replaceState(null, "", "/");
  vi.unstubAllGlobals();
});

it("offers service navigation and policy reading with chat unavailable", async () => {
  await act(async () =>
    root.render(<BankPages state="unavailable" onOpen={vi.fn()} />),
  );
  expect(
    container.querySelector("a[href='/bank/services/accounts']"),
  ).not.toBeNull();
  const link = container.querySelector<HTMLAnchorElement>(
    "a[href='/bank/policies/policy-02']",
  );
  expect(link).not.toBeNull();
  await act(async () => link?.click());
  expect(window.location.pathname).toBe("/bank/policies/policy-02");
  expect(container.textContent).toContain("Five synthetic dollars.");
  expect(container.textContent).toContain("<script>literal content</script>");
  expect(container.querySelector("script")).toBeNull();
  expect(container.textContent).toContain("synthetic-reviewed");
  expect(container.textContent).toContain(
    "What should I know about Birch checking monthly fee?",
  );
  expect(
    container.querySelector<HTMLButtonElement>("[data-chat-launch]")?.disabled,
  ).toBe(true);
  expect(document.title).toContain("Birch checking");
  expect(document.activeElement).toBe(container.querySelector("h1"));
});

it("submits search, changes categories, clears search, and pages through shared URLs", async () => {
  await act(async () =>
    root.render(<BankPages state="unavailable" onOpen={vi.fn()} />),
  );
  const input = container.querySelector<HTMLInputElement>(
    "input[type='search']",
  );
  if (!input) throw new Error("Search input missing");
  input.value = "monthly fee";
  await act(async () =>
    container
      .querySelector("form")
      ?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
  );
  expect(window.location.search).toContain("q=monthly+fee");
  expect(container.textContent).toContain("13 policies");
  const next = Array.from(container.querySelectorAll("a")).find(
    (link) => link.textContent === "Next page →",
  );
  await act(async () => next?.click());
  expect(window.location.search).toContain("page=2");
  const select = container.querySelector<HTMLSelectElement>("select");
  if (!select) throw new Error("Category filter missing");
  select.value = "accounts";
  await act(async () =>
    select.dispatchEvent(new Event("change", { bubbles: true })),
  );
  expect(window.location.search).toContain("category=accounts");
  expect(window.location.search).not.toContain("page=2");
  const clear = Array.from(container.querySelectorAll("a")).find(
    (link) => link.textContent === "Clear search",
  );
  await act(async () => clear?.click());
  expect(window.location.href).not.toContain("q=");
});

it("keeps known conflicting versions visible and opens only the native chat action", async () => {
  const open = vi.fn();
  vi.mocked(fetch).mockResolvedValue(
    new Response(
      JSON.stringify({
        ...policy,
        id: "conflict-01-a",
        title: "Conflicting Zephyr 1 policy",
        conflict_ids: ["conflict-01-b"],
        related_ids: ["conflict-01-b"],
      }),
    ),
  );
  window.history.replaceState(null, "", "/bank/policies/conflict-01-a");
  await act(async () => root.render(<BankPages state="ready" onOpen={open} />));
  expect(container.textContent).toContain("Conflicting source versions");
  expect(
    container.querySelector("a[href='/bank/policies/conflict-01-b']"),
  ).not.toBeNull();
  await act(async () =>
    container.querySelector<HTMLButtonElement>("[data-chat-launch]")?.click(),
  );
  expect(open).toHaveBeenCalledOnce();
});

it("shows unavailable content with retry and honest empty results", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(new Response("{}", { status: 503 }));
  await act(async () =>
    root.render(<BankPages state="unavailable" onOpen={vi.fn()} />),
  );
  expect(container.textContent).toContain(
    "Bank information is currently unavailable",
  );
  const retry = container.querySelector<HTMLButtonElement>(
    "button[data-bank-retry]",
  );
  await act(async () => retry?.click());
  expect(container.textContent).toContain("Birch checking monthly fee");
  vi.mocked(fetch).mockResolvedValue(
    new Response(JSON.stringify({ ...listing, total: 0, policies: [] })),
  );
  await act(async () => visit("/bank/search?q=nonexistent"));
  expect(container.textContent).toContain("No policies found");
});

it("ignores old responses after navigation and responds to history changes", async () => {
  let resolveOld: ((response: Response) => void) | undefined;
  vi.mocked(fetch).mockImplementationOnce(
    () =>
      new Promise<Response>((resolve) => {
        resolveOld = resolve;
      }),
  );
  await act(async () =>
    root.render(<BankPages state="unavailable" onOpen={vi.fn()} />),
  );
  await act(async () => visit("/bank/policies/policy-02"));
  expect(container.textContent).toContain("Five synthetic dollars.");
  await act(async () => resolveOld?.(new Response(JSON.stringify(listing))));
  expect(container.querySelector("h1")?.textContent).toBe(
    "Birch checking monthly fee",
  );
  await act(async () => visit("/bank/unknown"));
  expect(container.textContent).toContain("Page not found");
});
