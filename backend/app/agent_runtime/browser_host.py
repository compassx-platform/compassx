"""Host-owned browser for Agent Runtime.

The page is a headless Chromium tab controlled from this process, not an iframe.
Screenshots and element hits go through that browser, so a page on another origin
can still be captured.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any
from urllib.parse import urlparse


_INSPECT_JS = """
({x, y}) => {
  const el = document.elementFromPoint(x, y);
  if (!el || el === document.body || el === document.documentElement) return null;
  const rect = el.getBoundingClientRect();
  const style = getComputedStyle(el);
  const tag = el.tagName.toLowerCase();
  const selector = (() => {
    const parts = [];
    let current = el;
    while (current && current.tagName !== "BODY" && parts.length < 6) {
      const partTag = current.tagName.toLowerCase();
      const id = current.id ? "#" + current.id : "";
      const className = typeof current.className === "string"
        ? current.className.trim().split(/\\s+/).filter(Boolean).slice(0, 2).join(".")
        : "";
      parts.unshift(partTag + id + (className ? "." + className : ""));
      current = current.parentElement;
    }
    return parts.join(" > ");
  })();
  const names = [];
  const fiberKey = Object.keys(el).find((name) => name.startsWith("__reactFiber"));
  let node = fiberKey ? el[fiberKey] : null;
  while (node && names.length < 6) {
    const type = node.type;
    const name = type && (type.displayName || (typeof type === "function" ? type.name : ""));
    if (name && name[0] !== "_" && names[0] !== name) names.unshift(name);
    node = node.return;
  }
  const text = (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 200);
  return {
    label: names.length ? names[names.length - 1] + " · " + tag : tag,
    selector,
    text,
    stack: names.join(" > "),
    styles: [
      "color " + style.color,
      "background " + style.backgroundColor,
      "font " + style.fontSize + " " + style.fontFamily,
      "display " + style.display,
      "position " + style.position,
    ].join("; "),
    box: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
  };
}
"""


def clean_page_url(value: str) -> str:
    raw = (value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter an http or https URL.")
    return raw


def _viewport(width: int, height: int) -> tuple[int, int]:
    return max(320, min(1600, int(width))), max(240, min(1400, int(height)))


def format_target(url: str, info: dict | None, box: dict) -> dict:
    label = str((info or {}).get("label") or "Area")
    lines = [f"Page: {url}", f"Element: {label}"]
    if info:
        if info.get("selector"):
            lines.append(f"Selector: {info['selector']}")
        if info.get("stack"):
            lines.append(f"Components: {info['stack']}")
        if info.get("text"):
            lines.append(f"Text: {info['text']}")
        if info.get("styles"):
            lines.append(f"Styles: {info['styles']}")
    lines.append(
        f"Box: {round(float(box['width']))}×{round(float(box['height']))} at {round(float(box['left']))}, {round(float(box['top']))}"
    )
    return {
        "label": label,
        "detail": "\n".join(lines),
        "box": {
            "left": float(box["left"]),
            "top": float(box["top"]),
            "width": float(box["width"]),
            "height": float(box["height"]),
        },
    }


class BrowserHost:
    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="agent-browser-host", daemon=True)
        self._started = False
        self._start_lock = threading.Lock()
        self._playwright: Any = None
        self._browser: Any = None
        self._launch_error = ""
        self._pages: dict[str, Any] = {}
        self._order: list[str] = []
        self._requested: dict[str, str] = {}
        self._sizes: dict[str, tuple[int, int]] = {}
        self._frames: dict[str, tuple[float, bytes]] = {}

    def open(self, key: str, url: str, width: int, height: int) -> dict:
        clean = clean_page_url(url)
        width, height = _viewport(width, height)

        def run() -> dict:
            return self._open(key, clean, width, height)

        return self._call(run, timeout=60)

    def frame(self, key: str) -> tuple[bytes, int, int]:
        def run() -> tuple[bytes, int, int]:
            return self._frame(key)

        return self._call(run, timeout=20)

    def inspect(self, key: str, x: float, y: float) -> dict:
        def run() -> dict:
            return self._inspect(key, x, y)

        return self._call(run, timeout=15)

    def input(self, key: str, kind: str, x: float, y: float, delta_y: float, key_name: str, text: str) -> None:
        def run() -> None:
            self._input(key, kind, x, y, delta_y, key_name, text)

        self._call(run, timeout=15)

    def capture(self, key: str, x: float, y: float, width: float, height: float) -> tuple[bytes, dict]:
        def run() -> tuple[bytes, dict]:
            return self._capture(key, x, y, width, height)

        return self._call(run, timeout=20)

    def _call(self, fn, timeout: int):
        self._ensure_started()
        done: queue.Queue = queue.Queue(1)
        self._queue.put((fn, done))
        try:
            value, error = done.get(timeout=timeout)
        except queue.Empty as exc:
            raise RuntimeError("The browser host timed out.") from exc
        if error:
            raise error
        return value

    def _ensure_started(self) -> None:
        with self._start_lock:
            if not self._started:
                self._thread.start()
                self._started = True

    def _run(self) -> None:
        try:
            self._launch()
        except Exception as exc:
            self._launch_error = str(exc)
        while True:
            try:
                fn, done = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if self._browser is None:
                done.put((None, RuntimeError(self._launch_error or "The browser host is not available.")))
                continue
            try:
                done.put((fn(), None))
            except Exception as exc:
                done.put((None, exc))

    def _launch(self) -> None:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        errors: list[str] = []
        for channel in ("chrome", "msedge"):
            try:
                self._browser = self._playwright.chromium.launch(channel=channel, headless=True)
                return
            except Exception as exc:
                errors.append(f"{channel}: {exc}")
        try:
            self._browser = self._playwright.chromium.launch(headless=True)
        except Exception as exc:
            errors.append(f"chromium: {exc}")
            raise RuntimeError("Could not start a browser. " + " | ".join(errors)[:500]) from exc

    def _open(self, key: str, url: str, width: int, height: int) -> dict:
        page = self._pages.get(key)
        previous = self._requested.get(key)
        self._requested[key] = url
        if page is None:
            while len(self._order) >= 4:
                old = self._order.pop(0)
                stale = self._pages.pop(old, None)
                self._sizes.pop(old, None)
                self._frames.pop(old, None)
                self._requested.pop(old, None)
                if stale is not None:
                    try:
                        stale.context.close()
                    except Exception:
                        pass
            context = self._browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
            page = context.new_page()
            self._pages[key] = page
            self._order.append(key)
            nav_error = self._goto(page, url)
        elif previous != url:
            page.set_viewport_size({"width": width, "height": height})
            nav_error = self._goto(page, url)
        else:
            page.set_viewport_size({"width": width, "height": height})
            nav_error = ""
        self._sizes[key] = (width, height)
        self._frames.pop(key, None)
        return {"url": page.url, "width": width, "height": height, "error": nav_error}

    def _goto(self, page, url: str) -> str:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            return ""
        except Exception as exc:
            message = str(exc).split("\n", 1)[0]
            return message[:300]

    def _page(self, key: str):
        page = self._pages.get(key)
        if page is None:
            raise ValueError("Open the page in the browser first.")
        return page

    def _frame(self, key: str) -> tuple[bytes, int, int]:
        page = self._page(key)
        width, height = self._sizes.get(key, (800, 600))
        cached = self._frames.get(key)
        now = time.time()
        if cached and now - cached[0] < 0.08:
            return cached[1], width, height
        data = page.screenshot(type="jpeg", quality=45)
        self._frames[key] = (now, data)
        return data, width, height

    def _inspect(self, key: str, x: float, y: float) -> dict:
        page = self._page(key)
        width, height = self._sizes.get(key, (800, 600))
        point_x = min(max(float(x), 0), max(width - 1, 0))
        point_y = min(max(float(y), 0), max(height - 1, 0))
        info = page.evaluate(_INSPECT_JS, {"x": point_x, "y": point_y})
        box = (info or {}).get("box") or {"left": point_x - 8, "top": point_y - 8, "width": 16, "height": 16}
        return format_target(page.url, info, box)

    def _input(self, key: str, kind: str, x: float, y: float, delta_y: float, key_name: str, text: str) -> None:
        page = self._page(key)
        if kind == "click":
            page.mouse.click(float(x), float(y))
        elif kind == "double":
            page.mouse.dblclick(float(x), float(y))
        elif kind == "move":
            page.mouse.move(float(x), float(y))
        elif kind == "wheel":
            page.mouse.move(float(x), float(y))
            page.mouse.wheel(0, float(delta_y or 0))
        elif kind == "key":
            if text:
                page.keyboard.type(text[:20])
            elif key_name in {"Enter", "Backspace", "Tab", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Delete"}:
                page.keyboard.press(key_name)
        else:
            raise ValueError("Unknown browser input.")

    def _capture(self, key: str, x: float, y: float, width: float, height: float) -> tuple[bytes, dict]:
        page = self._page(key)
        view_w, view_h = self._sizes.get(key, (800, 600))
        left = min(max(float(x), 0), max(view_w - 2, 0))
        top = min(max(float(y), 0), max(view_h - 2, 0))
        clip_w = min(max(float(width), 2), view_w - left)
        clip_h = min(max(float(height), 2), view_h - top)
        info = page.evaluate(_INSPECT_JS, {"x": left + clip_w / 2, "y": top + clip_h / 2})
        shot = page.screenshot(
            type="jpeg",
            quality=70,
            clip={"x": left, "y": top, "width": clip_w, "height": clip_h},
        )
        target = format_target(page.url, info, {"left": left, "top": top, "width": clip_w, "height": clip_h})
        return shot, target


browser_host = BrowserHost()
