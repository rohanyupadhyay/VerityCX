/** Validate public bank data and encode shareable browser navigation without persisting queries. */
export const categoryInfo = {
  accounts: {
    title: "Accounts & everyday banking",
    description:
      "Explore account fees, statements, notices, and everyday account policies.",
  },
  savings: {
    title: "Savings",
    description:
      "Learn about opening deposits, withdrawal notices, and interest posting.",
  },
  cards: {
    title: "Cards",
    description:
      "Explore card replacement, foreign fees, and activation policies.",
  },
  payments: {
    title: "Payments & transfers",
    description:
      "Find transfer cutoffs, cancellation windows, and payment policies.",
  },
  deposits: {
    title: "Deposits & cash access",
    description:
      "Read about deposit holds, mobile deposit limits, and ATM access.",
  },
  other: {
    title: "Other policies",
    description:
      "Browse additional information and source versions that need clarification.",
  },
};
export type Category = keyof typeof categoryInfo;
export interface PolicySummary {
  id: string;
  title: string;
  category: Category;
  excerpt: string;
  conflict_ids: string[];
  related_ids: string[];
}
export interface CategoryCount {
  key: Category;
  title: string;
  count: number;
}
export interface PolicyListing {
  corpus_version: string;
  mode: "synthetic" | "official";
  categories: CategoryCount[];
  total: number;
  page: number;
  page_size: number;
  policies: PolicySummary[];
}
export interface PolicyDetail extends PolicySummary {
  content: string;
  corpus_version: string;
  mode: "synthetic" | "official";
}
export type BankRoute =
  | {
      kind: "listing";
      category: Category | "";
      query: string;
      page: number;
      service: boolean;
    }
  | { kind: "policy"; id: string }
  | { kind: "missing" };

/** Narrow JSON objects without trusting arrays, nulls, or unchecked casts. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
/** Reject unknown fields so private configuration cannot accidentally enter page state. */
function record(value: unknown, keys: string[]): Record<string, unknown> {
  if (!isRecord(value) || Object.keys(value).some((key) => !keys.includes(key)))
    throw new Error("Invalid bank information");
  return value;
}
/** Require real source strings instead of coercing malformed API fields. */
function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim())
    throw new Error("Invalid bank text");
  return value;
}
/** Validate nonnegative integral counts at the public boundary. */
function count(value: unknown, minimum = 0): number {
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value < minimum
  )
    throw new Error("Invalid bank count");
  return value;
}
/** Map validated JSON arrays into fully typed page data. */
function array<T>(value: unknown, parse: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) throw new Error("Invalid bank list");
  return value.map((item: unknown) => parse(item));
}
/** Accept only the server's documented public category keys. */
export function isCategory(value: string): value is Category {
  return Object.hasOwn(categoryInfo, value);
}
/** Require a supported category, keeping arbitrary server strings out of navigation. */
function category(value: unknown): Category {
  const name = text(value);
  if (!isCategory(name)) throw new Error("Invalid bank category");
  return name;
}
/** Preserve the source mode label without conflating official and authored synthetic content. */
function mode(value: unknown): "synthetic" | "official" {
  if (value !== "synthetic" && value !== "official")
    throw new Error("Invalid bank source");
  return value;
}
/** Validate the common public policy fields. */
function summary(value: Record<string, unknown>): PolicySummary {
  return {
    id: text(value.id),
    title: text(value.title),
    category: category(value.category),
    excerpt: text(value.excerpt),
    conflict_ids: array(value.conflict_ids, text),
    related_ids: array(value.related_ids, text),
  };
}
const summaryKeys = [
  "id",
  "title",
  "category",
  "excerpt",
  "conflict_ids",
  "related_ids",
];

/** Parse a closed listing envelope before displaying policy discovery results. */
export function parseListing(value: unknown): PolicyListing {
  const item = record(value, [
    "corpus_version",
    "mode",
    "categories",
    "total",
    "page",
    "page_size",
    "policies",
  ]);
  return {
    corpus_version: text(item.corpus_version),
    mode: mode(item.mode),
    total: count(item.total),
    page: count(item.page, 1),
    page_size: count(item.page_size, 1),
    categories: array(item.categories, (entry) => {
      const group = record(entry, ["key", "title", "count"]);
      return {
        key: category(group.key),
        title: text(group.title),
        count: count(group.count),
      };
    }),
    policies: array(item.policies, (entry) =>
      summary(record(entry, summaryKeys)),
    ),
  };
}
/** Parse full source text and metadata; HTML in content remains an ordinary string. */
export function parsePolicy(value: unknown): PolicyDetail {
  const item = record(value, [
    ...summaryKeys,
    "content",
    "corpus_version",
    "mode",
  ]);
  return {
    ...summary(item),
    content: text(item.content),
    corpus_version: text(item.corpus_version),
    mode: mode(item.mode),
  };
}

/** Keep missing-document errors distinct from connection or source-validation failures. */
export class BankError extends Error {
  constructor(public readonly status: number) {
    super("Bank information request failed");
  }
}

/** Fetch and validate same-origin public content with independent timeout and navigation cancellation. */
export async function fetchBank<T>(
  url: string,
  parse: (value: unknown) => T,
  signal: AbortSignal,
): Promise<T> {
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), 10000);
  try {
    const response = await fetch(url, {
      credentials: "omit",
      cache: "no-store",
      signal: AbortSignal.any([signal, timeout.signal]),
    });
    if (!response.ok) throw new BankError(response.status);
    const value: unknown = await response.json();
    return parse(value);
  } finally {
    clearTimeout(timer);
  }
}

/** Build a compact, shareable search URL with explicit category and paging state. */
export function searchUrl(
  query: string,
  group: Category | "" = "",
  page = 1,
): string {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  if (group) params.set("category", group);
  if (page > 1) params.set("page", String(page));
  return "/bank/search" + (params.size ? "?" + params.toString() : "");
}

/** Parse only supported frontend routes, rejecting malformed paths instead of guessing. */
export function routeFor(pathname: string, search: string): BankRoute {
  const params = new URLSearchParams(search);
  const rawPage = params.get("page") ?? "1";
  const page = Number(rawPage);
  const query = params.get("q") ?? "";
  const group = params.get("category") ?? "";
  if (
    !/^\d+$/.test(rawPage) ||
    !Number.isSafeInteger(page) ||
    page < 1 ||
    page > 100000 ||
    query.length > 200 ||
    (group && !isCategory(group))
  )
    return { kind: "missing" };
  if (pathname === "/bank" || pathname === "/bank/search")
    return {
      kind: "listing",
      category: isCategory(group) ? group : "",
      query,
      page,
      service: false,
    };
  const service = /^\/bank\/services\/([^/]+)$/.exec(pathname)?.[1];
  if (service && isCategory(service))
    return { kind: "listing", category: service, query, page, service: true };
  const id = /^\/bank\/policies\/(.+)$/.exec(pathname)?.[1];
  if (id) {
    try {
      return { kind: "policy", id: decodeURIComponent(id) };
    } catch {
      return { kind: "missing" };
    }
  }
  return { kind: "missing" };
}

/** Change only local bank-page history; the page component listens to the popstate event. */
export function navigateBank(url: string): void {
  window.history.pushState(null, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

/** Encode the entire source identifier so slashes and punctuation survive detail navigation. */
export function policyUrl(id: string): string {
  return "/bank/policies/" + encodeURIComponent(id);
}
