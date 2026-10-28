/** Validate public Chatwoot settings and coordinate one bounded native widget lifecycle. */

export type ChatState = "loading" | "ready" | "unavailable";
export type ChatConfig =
  { enabled: false } | { enabled: true; baseUrl: string; websiteToken: string };

interface ChatwootWidget {
  /** Show or close the native Chatwoot conversation. */
  toggle(state: "open" | "close"): void;
  /** Control only the native launcher's visibility. */
  toggleBubbleVisibility(state: "show" | "hide"): void;
}

declare global {
  interface Window {
    chatwootSDK?: {
      /** Initialize the SDK using public website settings only. */
      run(config: { baseUrl: string; websiteToken: string }): void;
    };
    $chatwoot?: ChatwootWidget;
    chatwootSettings?: {
      hideMessageBubble: boolean;
      position: "right";
      locale: "en";
      darkMode: "light";
      enableFileUpload: boolean;
      showUnreadMessagesDialog: boolean;
    };
  }
}

/** Reject malformed external settings before they become executable script locations. */
export function parseChatConfig(input: unknown): ChatConfig {
  if (typeof input !== "object" || input === null || !("enabled" in input)) {
    throw new Error("Invalid public chat configuration.");
  }
  if (input.enabled === false) return { enabled: false };
  if (
    input.enabled !== true ||
    !("base_url" in input) ||
    typeof input.base_url !== "string" ||
    !("website_token" in input) ||
    typeof input.website_token !== "string" ||
    !input.website_token ||
    input.website_token.length > 512 ||
    /\s/.test(input.website_token)
  ) {
    throw new Error("Invalid public chat configuration.");
  }
  const url = new URL(input.base_url);
  if (
    !["https:", "http:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/"
  ) {
    throw new Error("Invalid chat server origin.");
  }
  return {
    enabled: true,
    baseUrl: url.origin,
    websiteToken: input.website_token,
  };
}

/** Own the page's single native widget initialization without handling chat content. */
export class ChatConnection {
  private currentState: ChatState = "loading";
  private started = false;
  private disposed = false;
  private sdkStarted = false;
  private readonly request = new AbortController();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private script: HTMLScriptElement | undefined;
  private readonly listeners = new Set<() => void>();

  /** Expose connection state without allowing callers to bypass readiness checks. */
  get state(): ChatState {
    return this.currentState;
  }

  /** Subscribe to state transitions; the returned function releases the subscription. */
  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Publish a state change without handling or logging any conversation data. */
  private setState(state: ChatState): void {
    this.currentState = state;
    this.listeners.forEach((listener) => listener());
  }

  /** Accept readiness only from an SDK this connection has actually initialized. */
  private readonly onReady = (): void => {
    if (this.disposed || !this.sdkStarted || this.state !== "loading") return;
    if (typeof window.$chatwoot?.toggle !== "function") {
      this.fail();
      return;
    }
    clearTimeout(this.timer);
    this.setState("ready");
  };

  /** Hide a failed native widget so it cannot imply a working connection. */
  private hideWidget(): void {
    if (!this.sdkStarted) return;
    try {
      window.$chatwoot?.toggle("close");
      window.$chatwoot?.toggleBubbleVisibility("hide");
    } catch {
      // A partially loaded external SDK may not support cleanup; never expose its error.
    }
  }

  /** Bound failures to a generic public state and stop listening for stale readiness. */
  private readonly fail = (): void => {
    if (this.disposed) return;
    clearTimeout(this.timer);
    this.request.abort();
    window.removeEventListener("chatwoot:ready", this.onReady);
    window.removeEventListener("chatwoot:error", this.fail);
    this.script?.remove();
    this.hideWidget();
    this.setState("unavailable");
  };

  /** Load the public settings and initialize the native widget. */
  async start(): Promise<void> {
    if (this.started || this.disposed) return;
    this.started = true;
    this.timer = setTimeout(this.fail, 10_000);
    try {
      const response = await fetch("/chat/config", {
        credentials: "omit",
        headers: { Accept: "application/json" },
        signal: this.request.signal,
      });
      if (this.disposed || this.state !== "loading") return;
      if (!response.ok) {
        this.fail();
        return;
      }
      const payload: unknown = await response.json();
      if (this.disposed || this.state !== "loading") return;
      const config = parseChatConfig(payload);
      if (
        !config.enabled ||
        (location.protocol === "https:" && !config.baseUrl.startsWith("https:"))
      ) {
        this.fail();
        return;
      }
      clearTimeout(this.timer);
      this.timer = setTimeout(this.fail, 15_000);
      window.chatwootSettings = {
        hideMessageBubble: false,
        position: "right",
        locale: "en",
        darkMode: "light",
        enableFileUpload: false,
        showUnreadMessagesDialog: false,
      };
      window.addEventListener("chatwoot:ready", this.onReady);
      window.addEventListener("chatwoot:error", this.fail);
      const script = document.createElement("script");
      script.dataset.verityChat = "true";
      script.src = `${config.baseUrl}/packs/js/sdk.js`;
      script.async = true;
      script.referrerPolicy = "no-referrer";
      script.onerror = this.fail;
      /** Only SDK initialization receives the narrowed public configuration. */
      script.onload = (): void => {
        if (this.disposed || this.state !== "loading") return;
        if (typeof window.chatwootSDK?.run !== "function") {
          this.fail();
          return;
        }
        try {
          this.sdkStarted = true;
          window.chatwootSDK.run({
            baseUrl: config.baseUrl,
            websiteToken: config.websiteToken,
          });
        } catch {
          this.fail();
        }
      };
      this.script = script;
      document.head.appendChild(script);
    } catch {
      this.fail();
    }
  }

  /** Open the actual widget only after it signals readiness. */
  open(): boolean {
    if (this.disposed || this.state !== "ready" || !window.$chatwoot)
      return false;
    try {
      window.$chatwoot.toggle("open");
      return true;
    } catch {
      this.fail();
      return false;
    }
  }

  /** Release this page's requests, timers, and event handlers. */
  dispose(): void {
    this.disposed = true;
    this.request.abort();
    clearTimeout(this.timer);
    window.removeEventListener("chatwoot:ready", this.onReady);
    window.removeEventListener("chatwoot:error", this.fail);
    if (this.script) {
      this.script.onload = null;
      this.script.onerror = null;
      this.script.remove();
    }
    this.hideWidget();
    this.listeners.clear();
  }
}
