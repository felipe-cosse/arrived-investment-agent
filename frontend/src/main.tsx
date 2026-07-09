/** Application entry: mount <App /> under React strict mode with Inter loaded
 * locally (offline-safe, R21) per the DESIGN.md typography tokens.
 */

import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./index.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

const container = document.getElementById("root");
if (container === null) throw new Error("missing #root container");

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
