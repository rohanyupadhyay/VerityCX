/** Mount the support page once; the native third-party SDK owns its own widget lifecycle. */
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

const container = document.getElementById("root");
if (!container) throw new Error("Customer support root is missing.");
// The SDK has no destroy API; a single mount avoids initializing its global listeners twice.
createRoot(container).render(<App />);
