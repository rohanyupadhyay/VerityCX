/** Present the synthetic banking support page around the actual native messaging connection. */
import { useEffect, useState, type ReactElement } from "react";
import { ChatConnection, type ChatState } from "./chat";

type IconName =
  "arrow" | "chat" | "shield" | "bank" | "card" | "leaf" | "transfer";

const iconPaths: Record<IconName, string> = {
  arrow: "M5 12h14m-5-5 5 5-5 5",
  chat: "M20 11.5a8 8 0 0 1-8 8H5l-3 2v-10a9 9 0 0 1 18 0ZM7 10h8M7 14h5",
  shield: "m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6l8-3Zm-4 9 3 3 5-6",
  bank: "m3 8 9-5 9 5H3Zm3 3v7m6-7v7m6-7v7M3 21h18M4 18h16",
  card: "M3 8h18M4 4h16a1 1 0 0 1 1 1v14H3V5a1 1 0 0 1 1-1Zm2 10h5m-5 3h3",
  leaf: "M19 4C8 2 3 7 5 14c2 7 15 6 14-10ZM5 21l9-12M9 14h6",
  transfer: "M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4",
};

/** Render decorative, locally defined line icons without remote assets. */
function Icon({
  name,
  className = "",
}: {
  name: IconName;
  className?: string;
}): ReactElement {
  return (
    <svg
      className={className}
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={iconPaths[name]} />
    </svg>
  );
}

const topics: {
  number: string;
  icon: IconName;
  title: string;
  description: string;
  tag: string;
}[] = [
  {
    number: "01",
    icon: "bank",
    title: "Everyday banking",
    description:
      "Make sense of Birch checking fees, account requirements and the everyday details.",
    tag: "Checking & accounts",
  },
  {
    number: "02",
    icon: "card",
    title: "Cards, without the confusion",
    description:
      "Explore Cedar card replacement policies and understand the next steps.",
    tag: "Cards & replacements",
  },
  {
    number: "03",
    icon: "leaf",
    title: "Room to grow",
    description:
      "Get clarity on Alder savings requirements and how the policies fit together.",
    tag: "Savings & eligibility",
  },
  {
    number: "04",
    icon: "transfer",
    title: "Know what comes next",
    description:
      "Ask about transfer rules, timing and the policy behind a banking question.",
    tag: "Payments & transfers",
  },
];

const questions = [
  {
    question: "What can I ask here?",
    answer:
      "Ask a question about the demonstration bank’s policies: Birch checking fees, Cedar card replacements, Alder savings requirements, or transfer rules. Be specific about the product so support can find the relevant policy.",
  },
  {
    question: "Can you access or change my account?",
    answer:
      "This is a synthetic banking demonstration. Support can explain policies, but it cannot access a real bank account, replace a real card, or move money. Use invented examples when trying it.",
  },
  {
    question: "How do I ask for a person?",
    answer:
      "Ask for a human in the chat. When the support inbox is connected, the conversation can be handed to an agent there. A ready chat connection does not mean a human agent is currently online.",
  },
  {
    question: "What should I keep out of the conversation?",
    answer:
      "Never share passwords, PINs, one-time security codes, full card numbers, account numbers, or identity documents. This demonstration only needs a policy question and synthetic details. File uploads are disabled.",
  },
];

const statusText: Record<ChatState, string> = {
  loading: "Connecting to chat",
  ready: "Chat is ready",
  unavailable: "Chat is currently unavailable",
};

interface LaunchProps {
  state: ChatState;
  onOpen: () => void;
  className?: string;
  children: React.ReactNode;
  label?: string;
}

/** Launch the native widget, keeping all entry points unavailable until real readiness. */
function ChatButton({
  state,
  onOpen,
  className = "",
  children,
  label,
}: LaunchProps): ReactElement {
  return (
    <button
      type="button"
      className={className}
      onClick={onOpen}
      disabled={state !== "ready"}
      data-chat-launch
      aria-describedby="chat-status"
      aria-label={label}
    >
      {children}
    </button>
  );
}

/** Render the public customer experience without account access or private credentials. */
export function App(): ReactElement {
  const [connection] = useState(() => new ChatConnection());
  const [state, setState] = useState<ChatState>(connection.state);

  /** Subscribe before initialization so even fast config responses update the page. */
  useEffect(() => {
    const unsubscribe = connection.subscribe(() => setState(connection.state));
    void connection.start();
    return () => {
      unsubscribe();
      connection.dispose();
    };
  }, [connection]);

  /** Delegate every conversation action to the verified native SDK. */
  function openChat(): void {
    connection.open();
  }

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header shell">
        <a className="wordmark" href="#main" aria-label="Verity support home">
          <svg
            width="34"
            height="36"
            viewBox="0 0 34 36"
            fill="none"
            aria-hidden="true"
          >
            <path d="M3 7h8l6 17L23 7h8L17 34 3 7Z" fill="currentColor" />
            <path d="m17 2 3 5h-6l3-5Z" fill="currentColor" />
          </svg>
          <span>
            verity<span className="wordmark-dot">.</span>
          </span>
        </a>
        <span className="header-divider" aria-hidden="true" />
        <span className="header-label">Support center</span>
        <nav aria-label="Main navigation">
          <a href="#topics">Help topics</a>
          <a href="#good-to-know">Good to know</a>
          <ChatButton state={state} onOpen={openChat} className="header-chat">
            Let’s talk <Icon name="arrow" />
          </ChatButton>
        </nav>
      </header>

      <main id="main">
        <section className="hero shell" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="small-line" /> A LITTLE CLARITY GOES A LONG WAY
            </p>
            <h1 id="hero-title">
              Good questions.
              <br />
              <em>Clear answers.</em>
            </h1>
            <p className="hero-description">
              Banking has enough fine print.
              <br className="desktop-break" /> Getting help shouldn’t add to it.
            </p>
            <p className="hero-detail">
              Find your way through our policies, ask what’s on your mind, and
              get a little guidance for your next step.
            </p>
            <div className="hero-actions">
              <ChatButton
                state={state}
                onOpen={openChat}
                className="button button-primary"
              >
                <Icon name="chat" /> Start a conversation <Icon name="arrow" />
              </ChatButton>
              <a className="text-link" href="#topics">
                Explore help topics <span aria-hidden="true">↗</span>
              </a>
            </div>
            <p className="privacy-note">
              <Icon name="shield" /> Policy help. No personal banking details
              needed.
            </p>
          </div>

          <div className="hero-visual">
            <div className="orbit orbit-one" aria-hidden="true" />
            <div className="orbit orbit-two" aria-hidden="true" />
            <div className="visual-caption">
              <span className="four-point-star" aria-hidden="true">
                ✳
              </span>{" "}
              A FRESH PERSPECTIVE
            </div>
            <div className="question-card">
              <span className="eyebrow">LET’S START WITH YOU</span>
              <h2>
                A question is
                <br />a good beginning.
              </h2>
              <p>Here are a few places to start.</p>
              {[
                "What are the Birch checking fees?",
                "How do Cedar card replacements work?",
                "What does Alder savings require?",
              ].map((question, index) => (
                <ChatButton
                  key={question}
                  state={state}
                  onOpen={openChat}
                  className="suggested-question"
                  label={`Open chat to ask: ${question}`}
                >
                  <span className="question-number">0{index + 1}</span>
                  <span>{question}</span>
                  <Icon name="arrow" />
                </ChatButton>
              ))}
              <span className="card-footnote">
                Your question. A clearer next step.
              </span>
            </div>
            <div className="visual-bottom">
              <span className="mini-mark" aria-hidden="true">
                v.
              </span>
              <span>
                A LITTLE HELP.
                <br />A LOT MORE CLARITY.
              </span>
              <Icon name="shield" />
            </div>
          </div>
        </section>

        <div className={`connection-strip connection-${state}`}>
          <div className="shell connection-content">
            <p id="chat-status" role="status">
              <span className="status-dot" />
              {statusText[state]}
            </p>
            <p>
              {state === "ready"
                ? "Ask a policy question in our support chat. Human availability depends on the connected inbox."
                : state === "loading"
                  ? "We’re checking the support connection. You can explore the guidance below while you wait."
                  : "The support connection isn’t available. You can still explore the guidance below."}
            </p>
            {state === "unavailable" && (
              <button
                className="retry-button"
                type="button"
                onClick={() => window.location.reload()}
              >
                Try again <span aria-hidden="true">↻</span>
              </button>
            )}
          </div>
        </div>

        <section
          className="topics-section shell"
          id="topics"
          aria-labelledby="topics-title"
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">A GOOD PLACE TO START</p>
              <h2 id="topics-title">
                Let’s make it <em>simple.</em>
              </h2>
            </div>
            <p>
              Big question or small detail.
              <br />
              There’s a conversation for that.
            </p>
          </div>
          <div className="topic-grid">
            {topics.map((topic) => (
              <ChatButton
                key={topic.number}
                state={state}
                onOpen={openChat}
                className="topic-card"
                label={`Open chat about ${topic.tag.toLowerCase()}`}
              >
                <span className="topic-card-top">
                  <span className="topic-icon">
                    <Icon name={topic.icon} />
                  </span>
                  <span className="topic-number">{topic.number}</span>
                </span>
                <span className="topic-title">{topic.title}</span>
                <span className="topic-description">{topic.description}</span>
                <span className="topic-bottom">
                  <span>{topic.tag}</span>
                  <Icon name="arrow" />
                </span>
              </ChatButton>
            ))}
          </div>
          <p className="topics-note">
            Topic cards open the support conversation when chat is connected.
          </p>
        </section>

        <section
          className="good-to-know shell"
          id="good-to-know"
          aria-labelledby="guidance-title"
        >
          <div className="guidance-intro">
            <p className="eyebrow">BEFORE WE TALK</p>
            <h2 id="guidance-title">
              A few things
              <br />
              <em>good to know.</em>
            </h2>
            <p>A little context for a better conversation.</p>
            <div className="guidance-seal">
              <Icon name="shield" />
              <span>
                Keep it curious.
                <br />
                Keep your details private.
              </span>
            </div>
          </div>
          <div className="faq-list">
            {questions.map(({ question, answer }) => (
              <details key={question}>
                <summary>
                  {question}
                  <span className="faq-plus" aria-hidden="true" />
                </summary>
                <p>{answer}</p>
              </details>
            ))}
          </div>
        </section>

        <section
          className="closing-section shell"
          aria-labelledby="closing-title"
        >
          <span className="closing-mark" aria-hidden="true">
            ✳
          </span>
          <div>
            <p className="eyebrow">THAT’S WHAT WE’RE HERE FOR</p>
            <h2 id="closing-title">
              Less wondering. <em>More understanding.</em>
            </h2>
            <p>
              You don’t need to know the right words. Just start with a
              question.
            </p>
          </div>
          <ChatButton
            state={state}
            onOpen={openChat}
            className="button button-primary"
          >
            Let’s talk <Icon name="arrow" />
          </ChatButton>
        </section>
      </main>

      <footer className="site-footer shell">
        <div className="footer-top">
          <span className="footer-wordmark">verity.</span>
          <span>A little clarity changes everything.</span>
          <a href="#main">
            Back to top <span aria-hidden="true">↑</span>
          </a>
        </div>
        <div className="footer-bottom">
          <p>
            <strong>Synthetic banking demonstration</strong>
            <br />
            Powered by VerityCX. This is a demonstration, not a real bank or
            financial service.
          </p>
          <p>
            Use invented examples only. Never share real account details,
            <br className="desktop-break" /> passwords, security codes, or
            financial documents.
          </p>
        </div>
      </footer>
    </>
  );
}
