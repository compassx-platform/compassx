import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./styles.css";

const stored = localStorage.getItem("cx-arch-theme");
const theme = stored === "dark" || stored === "light"
  ? stored
  : window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
document.documentElement.dataset.theme = theme;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
