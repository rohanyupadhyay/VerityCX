/** Exercise the real page with a simulated native SDK boundary, never a substitute chat UI. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../src/App";

let root: Root;
let container: HTMLDivElement;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ enabled: false }))),
  );
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  document.getElementById("chatwoot_live_chat_widget")?.remove();
  delete window.chatwootSDK;
  delete window.$chatwoot;
  delete window.chatwootSettings;
  vi.unstubAllGlobals();
});

it("renders an honest demo, readable guidance, and unavailable chat controls", async () => {
  await act(async () => root.render(<App />));
  expect(container.querySelector("h1")?.textContent).toContain(
    "Clear answers.",
  );
  expect(container.textContent).toContain("Synthetic banking demonstration");
  expect(container.textContent).toContain("Chat is currently unavailable");
  expect(container.querySelectorAll("details").length).toBeGreaterThan(2);
  const launchers = container.querySelectorAll<HTMLButtonElement>(
    "button[data-chat-launch]",
  );
  expect(launchers.length).toBeGreaterThan(3);
  launchers.forEach((button) => expect(button.disabled).toBe(true));
  expect(container.querySelector("textarea, [role='log']")).toBeNull();
  expect(container.querySelector("form[role='search']")).not.toBeNull();
  expect(container.querySelector("a[href='#']")).toBeNull();
  expect(container.querySelector("a[href='/bank']")).not.toBeNull();
  expect(
    container.querySelector("a[href='/bank/services/cards']"),
  ).not.toBeNull();
});

it("starts a fresh chat from each page action and disables actions until reset finishes", async () => {
  vi.mocked(fetch).mockResolvedValue(
    new Response(
      JSON.stringify({
        enabled: true,
        base_url: "https://support.example.test",
        website_token: "public-token",
      }),
    ),
  );
  const toggle = vi.fn();
  const reset = vi.fn();
  const frame = document.createElement("iframe");
  frame.id = "chatwoot_live_chat_widget";
  document.body.appendChild(frame);
  window.chatwootSDK = { run: vi.fn() };
  window.$chatwoot = { toggle, reset, toggleBubbleVisibility: vi.fn() };
  await act(async () => root.render(<App />));
  expect(container.textContent).toContain("Connecting to chat");
  expect(
    container.querySelector<HTMLButtonElement>("button[data-chat-launch]")
      ?.disabled,
  ).toBe(true);
  await act(async () => {
    document.head
      .querySelector("script[data-verity-chat]")
      ?.dispatchEvent(new Event("load"));
    window.dispatchEvent(new Event("chatwoot:ready"));
  });
  expect(container.textContent).toContain("Chat is ready");
  const launchers = container.querySelectorAll<HTMLButtonElement>(
    "button[data-chat-launch]",
  );
  for (const button of launchers) {
    expect(button.disabled).toBe(false);
    await act(async () => button.click());
    expect(container.textContent).toContain("Starting a new chat");
    launchers.forEach((launcher) => expect(launcher.disabled).toBe(true));
    await act(async () => {
      window.dispatchEvent(
        new MessageEvent("message", {
          origin: "https://support.example.test",
          source: frame.contentWindow,
          data: `chatwoot-widget:${JSON.stringify({ event: "loaded", config: { authToken: `session-${reset.mock.calls.length}` } })}`,
        }),
      );
    });
    expect(container.textContent).toContain("Chat is ready");
  }
  expect(reset).toHaveBeenCalledTimes(launchers.length);
  expect(toggle).toHaveBeenCalledTimes(launchers.length);
  expect(toggle).toHaveBeenLastCalledWith("open");
});
