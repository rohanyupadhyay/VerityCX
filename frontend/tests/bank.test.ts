/** Verify bank API validation and local URL state without a provider or widget. */
import { expect, it } from "vitest";
import { parseListing, parsePolicy, searchUrl, routeFor } from "../src/bank";

const summary = {
  id: "policy-02",
  title: "Birch checking monthly fee",
  category: "accounts",
  excerpt: "A source excerpt.",
  conflict_ids: [],
  related_ids: [],
};
const listing = {
  corpus_version: "synthetic-reviewed",
  mode: "synthetic",
  categories: [{ key: "accounts", title: "Accounts", count: 1 }],
  total: 1,
  page: 1,
  page_size: 12,
  policies: [summary],
};

it("validates complete policy envelopes and rejects malformed public content", () => {
  expect(parseListing(listing).policies[0]?.id).toBe("policy-02");
  expect(() => parseListing({ ...listing, total: -1 })).toThrow();
  expect(() =>
    parseListing({
      ...listing,
      policies: [{ ...summary, category: "unknown" }],
    }),
  ).toThrow();
  expect(() =>
    parseListing({ ...listing, private_token: "not-public" }),
  ).toThrow();
  expect(() =>
    parseListing({ ...listing, policies: [{ ...summary, title: 4 }] }),
  ).toThrow();
  expect(() =>
    parseListing({
      ...listing,
      categories: [{ key: "accounts", title: "Accounts", count: "1" }],
    }),
  ).toThrow();
  const policy = {
    ...summary,
    content: "<script>literal text</script>",
    corpus_version: "synthetic-reviewed",
    mode: "synthetic",
  };
  expect(parsePolicy(policy).content).toBe("<script>literal text</script>");
  expect(() => parsePolicy({ ...policy, content: null })).toThrow();
  expect(() => parsePolicy({ ...policy, mode: "private" })).toThrow();
});

it("encodes shared search and parses direct policy links without losing IDs", () => {
  expect(searchUrl("fee & limits", "cards", 2)).toBe(
    "/bank/search?q=fee+%26+limits&category=cards&page=2",
  );
  expect(searchUrl("", "", 1)).toBe("/bank/search");
  expect(routeFor("/bank/policies/custom%2Fone", "")).toEqual({
    kind: "policy",
    id: "custom/one",
  });
  expect(routeFor("/bank/services/cards", "")).toEqual({
    kind: "listing",
    category: "cards",
    query: "",
    page: 1,
    service: true,
  });
  expect(routeFor("/bank/services/unknown", "").kind).toBe("missing");
  expect(routeFor("/bank/policies/%zz", "").kind).toBe("missing");
});
