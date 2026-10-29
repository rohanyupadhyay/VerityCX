/** Verify the public configuration boundary and native SDK lifecycle without contacting a provider. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatConnection, parseChatConfig } from "../src/chat";

const publicConfig = {
  enabled: true,
  base_url: "https://support.example.test/",
  website_token: "public-website-token",
};

/** Return only the public settings expected from the same-origin backend. */
function configResponse(value: unknown = publicConfig): Response {
  return new Response(JSON.stringify(value), { status: 200 });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(configResponse()));
});

afterEach(() => {
  document.head
    .querySelectorAll("script[data-verity-chat]")
    .forEach((script) => script.remove());
  delete window.chatwootSDK;
  delete window.$chatwoot;
  delete window.chatwootSettings;
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("public configuration", () => {
  it("validates and narrows configuration instead of forwarding untrusted extra fields", () => {
    expect(
      parseChatConfig({ ...publicConfig, api_token: "must-not-be-forwarded" }),
    ).toEqual({
      enabled: true,
      baseUrl: "https://support.example.test",
      websiteToken: "public-website-token",
    });
  });

  it.each([
    null,
    { enabled: "true" },
    { ...publicConfig, website_token: "" },
    { ...publicConfig, base_url: "javascript:alert(1)" },
    { ...publicConfig, base_url: "https://private:password@example.test" },
    { ...publicConfig, base_url: "https://example.test/?secret=value" },
  ])(
    "rejects malformed or unsafe enabled configuration: %j",
    (input: unknown) => {
      expect(() => parseChatConfig(input)).toThrow();
    },
  );

  it("accepts a disabled backend without publishing or requiring credentials", () => {
    expect(
      parseChatConfig({ enabled: false, base_url: null, website_token: null }),
    ).toEqual({
      enabled: false,
    });
  });
});

describe("native widget connection", () => {
  it("waits for native readiness, disables uploads, and opens the actual widget", async () => {
    const connection = new ChatConnection();
    const toggle = vi.fn();
    window.$chatwoot = { toggle, toggleBubbleVisibility: vi.fn() };
    const run = vi.fn();
    window.chatwootSDK = { run };

    await connection.start();
    expect(fetch).toHaveBeenCalledWith(
      "/chat/config",
      expect.objectContaining({ credentials: "omit" }),
    );
    const script = document.head.querySelector<HTMLScriptElement>(
      "script[data-verity-chat]",
    );
    expect(script?.src).toBe("https://support.example.test/packs/js/sdk.js");
    expect(window.chatwootSettings?.enableFileUpload).toBe(false);
    expect(connection.state).toBe("loading");
    expect(connection.open()).toBe(false);

    script?.dispatchEvent(new Event("load"));
    expect(run).toHaveBeenCalledWith({
      baseUrl: "https://support.example.test",
      websiteToken: "public-website-token",
    });
    expect(connection.state).toBe("loading");
    window.dispatchEvent(new Event("chatwoot:ready"));
    expect(connection.state).toBe("ready");
    expect(connection.open()).toBe(true);
    expect(toggle).toHaveBeenCalledWith("open");
    connection.dispose();
  });

  it("never loads third-party scripts when chat is disabled", async () => {
    vi.mocked(fetch).mockResolvedValue(configResponse({ enabled: false }));
    const connection = new ChatConnection();
    await connection.start();
    expect(connection.state).toBe("unavailable");
    expect(document.head.querySelector("script[data-verity-chat]")).toBeNull();
    connection.dispose();
  });

  it("reports script failure without exposing raw errors or inventing chat", async () => {
    const connection = new ChatConnection();
    await connection.start();
    document.head
      .querySelector("script[data-verity-chat]")
      ?.dispatchEvent(new Event("error"));
    expect(connection.state).toBe("unavailable");
    expect(connection.open()).toBe(false);
    connection.dispose();
  });

  it("bounds a native widget that never becomes ready", async () => {
    vi.useFakeTimers();
    const connection = new ChatConnection();
    await connection.start();
    await vi.advanceTimersByTimeAsync(20_000);
    expect(connection.state).toBe("unavailable");
    window.dispatchEvent(new Event("chatwoot:ready"));
    expect(connection.state).toBe("unavailable");
    connection.dispose();
  });

  it("ignores late configuration after the page has unmounted", async () => {
    let finish: ((response: Response) => void) | undefined;
    vi.mocked(fetch).mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve;
        }),
    );
    const connection = new ChatConnection();
    const pending = connection.start();
    connection.dispose();
    finish?.(configResponse());
    await pending;
    expect(document.head.querySelector("script[data-verity-chat]")).toBeNull();
    expect(connection.open()).toBe(false);
  });

  it("surfaces a configuration failure as unavailable", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("private upstream error", { status: 503 }),
    );
    const connection = new ChatConnection();
    await connection.start();
    expect(connection.state).toBe("unavailable");
    expect(document.head.querySelector("script[data-verity-chat]")).toBeNull();
    connection.dispose();
  });
});
