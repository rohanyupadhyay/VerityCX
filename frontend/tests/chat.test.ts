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
  document.getElementById("chatwoot_live_chat_widget")?.remove();
  document.head
    .querySelectorAll("script[data-verity-chat]")
    .forEach((script) => script.remove());
  delete window.chatwootSDK;
  delete window.$chatwoot;
  delete window.chatwootSettings;
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

/** Simulate only the external SDK; exercise the actual connection and iframe boundary. */
async function readyConnection() {
  const connection = new ChatConnection();
  const frame = document.createElement("iframe");
  frame.id = "chatwoot_live_chat_widget";
  document.body.appendChild(frame);
  const toggle = vi.fn();
  const reset = vi.fn();
  const visibility = vi.fn();
  window.$chatwoot = { toggle, reset, toggleBubbleVisibility: visibility };
  window.chatwootSDK = { run: vi.fn() };
  await connection.start();
  document.head
    .querySelector("script[data-verity-chat]")
    ?.dispatchEvent(new Event("load"));
  widgetLoaded(frame, {
    data: 'chatwoot-widget:{"event":"loaded","config":{"authToken":"initial-session"}}',
  });
  window.dispatchEvent(new Event("chatwoot:ready"));
  return { connection, frame, toggle, reset, visibility };
}

/** Match the pinned SDK's loaded message, without including credentials or chat data. */
let sessionSequence = 0;
function widgetLoaded(
  frame: HTMLIFrameElement,
  overrides: MessageEventInit = {},
) {
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: "https://support.example.test",
      source: frame.contentWindow,
      data: `chatwoot-widget:${JSON.stringify({ event: "loaded", config: { authToken: `fresh-session-${++sessionSequence}` } })}`,
      ...overrides,
    }),
  );
}

describe("fresh conversation", () => {
  it("ignores readiness from earlier sessions of the same iframe during another reset", async () => {
    const { connection, frame, toggle } = await readyConnection();
    const previous =
      'chatwoot-widget:{"event":"loaded","config":{"authToken":"previous-session"}}';
    try {
      connection.startNew();
      widgetLoaded(frame, { data: previous });
      expect(connection.state).toBe("ready");
      toggle.mockClear();
      connection.startNew();
      widgetLoaded(frame, {
        data: 'chatwoot-widget:{"event":"loaded","config":{"authToken":"initial-session"}}',
      });
      widgetLoaded(frame, { data: previous });
      widgetLoaded(frame, { data: 'chatwoot-widget:{"event":"loaded"}' });
      expect(connection.state).toBe("starting");
      expect(toggle).not.toHaveBeenCalledWith("open");
      widgetLoaded(frame);
      expect(connection.state).toBe("ready");
    } finally {
      connection.dispose();
    }
  });
  it("resets each session and opens only after the actual widget is ready", async () => {
    const { connection, frame, reset, toggle, visibility } =
      await readyConnection();
    try {
      expect(connection.startNew()).toBe(true);
      expect(connection.state).toBe("starting");
      expect(reset).toHaveBeenCalledTimes(1);
      expect(visibility).toHaveBeenLastCalledWith("hide");
      expect(toggle).not.toHaveBeenCalledWith("open");
      expect(connection.startNew()).toBe(false);
      expect(connection.open()).toBe(false);
      expect(reset).toHaveBeenCalledTimes(1);
      window.dispatchEvent(new Event("chatwoot:ready"));
      expect(connection.state).toBe("starting");
      widgetLoaded(frame);
      expect(connection.state).toBe("ready");
      expect(toggle).toHaveBeenLastCalledWith("open");
      expect(visibility).toHaveBeenLastCalledWith("show");
      expect(connection.startNew()).toBe(true);
      expect(reset).toHaveBeenCalledTimes(2);
      widgetLoaded(frame);
      expect(connection.state).toBe("ready");
    } finally {
      connection.dispose();
    }
  });

  it("ignores unrelated, malformed, and untrusted readiness messages", async () => {
    const { connection, frame } = await readyConnection();
    try {
      connection.startNew();
      widgetLoaded(frame, { origin: "https://other.example.test" });
      widgetLoaded(frame, { source: window });
      widgetLoaded(frame, { data: "chatwoot-widget:invalid JSON" });
      widgetLoaded(frame, { data: "chatwoot-widget:null" });
      widgetLoaded(frame, { data: { event: "loaded" } });
      widgetLoaded(frame, { data: 'chatwoot-widget:{"event":"other"}' });
      expect(connection.state).toBe("starting");
      widgetLoaded(frame);
      expect(connection.state).toBe("ready");
    } finally {
      connection.dispose();
    }
  });

  it("times out a reset and ignores late readiness", async () => {
    vi.useFakeTimers();
    const { connection, frame, toggle } = await readyConnection();
    try {
      connection.startNew();
      await vi.advanceTimersByTimeAsync(15_000);
      expect(connection.state).toBe("unavailable");
      widgetLoaded(frame);
      expect(connection.state).toBe("unavailable");
      expect(toggle).not.toHaveBeenCalledWith("open");
    } finally {
      connection.dispose();
    }
  });

  it("reports a failed reset without reopening the old chat", async () => {
    const { connection, frame, reset, toggle } = await readyConnection();
    try {
      reset.mockImplementation(() => {
        throw new Error("private SDK failure");
      });
      expect(connection.startNew()).toBe(false);
      expect(connection.state).toBe("unavailable");
      widgetLoaded(frame);
      expect(toggle).not.toHaveBeenCalledWith("open");
    } finally {
      connection.dispose();
    }
  });

  it.each(["iframe", "reset"])(
    "fails closed when the SDK's %s is missing",
    async (missing) => {
      const { connection, frame, reset } = await readyConnection();
      try {
        if (missing === "iframe") frame.remove();
        else
          window.$chatwoot = {
            toggle: vi.fn(),
            toggleBubbleVisibility: vi.fn(),
          };
        expect(connection.startNew()).toBe(false);
        expect(connection.state).toBe("unavailable");
        expect(reset).not.toHaveBeenCalled();
      } finally {
        connection.dispose();
      }
    },
  );

  it("does not reset before initialization or after disposal", async () => {
    const unstarted = new ChatConnection();
    expect(unstarted.startNew()).toBe(false);
    unstarted.dispose();
    const { connection, frame, reset, toggle } = await readyConnection();
    connection.startNew();
    connection.dispose();
    widgetLoaded(frame);
    expect(connection.startNew()).toBe(false);
    expect(reset).toHaveBeenCalledTimes(1);
    expect(toggle).not.toHaveBeenCalledWith("open");
  });
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
