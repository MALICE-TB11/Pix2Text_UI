import io
import json
import locale
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from PIL import Image

HOST = "127.0.0.1"
PORT = int(os.environ.get("P2T_PORT", "8504"))


def _system_is_chinese() -> bool:
    try:
        locale.setlocale(locale.LC_ALL, "")
        loc = (locale.getlocale()[0] or "").lower()
    except Exception:
        loc = ""
    return loc.startswith(("zh", "chinese"))


ZH = _system_is_chinese()


def T(zh: str, en: str) -> str:
    return zh if ZH else en


print(T("正在加载 Pix2Text 模型（首次运行会下载模型，请稍等）...",
        "Loading Pix2Text models (first run downloads them, please wait)..."))
from pix2text import Pix2Text

try:
    P2T = Pix2Text.from_config()
except ValueError as e:
    print(T("GPU 加载失败，改用 CPU（单个公式几秒内即可识别）：",
            "GPU load failed, falling back to CPU (a formula takes a few seconds): ") + f"{str(e)[:80]}...")
    P2T = Pix2Text.from_config(device="cpu")
LOCK = threading.Lock()
print(T("模型加载完成。", "Models loaded."))


def recognize(img: Image.Image, mode: str) -> str:
    img = img.convert("RGB")
    with LOCK:
        if mode == "formula":
            out = P2T.recognize_formula(img)
        else:
            out = P2T.recognize(img, file_type="text_formula")
    if isinstance(out, str):
        return out

    if hasattr(out, "to_markdown"):
        try:
            return out.to_markdown(".")
        except TypeError:
            return out.to_markdown()
    return str(out)


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pix2Text</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<style>
  :root { --bg:#f6f7f9; --card:#fff; --text:#1d2330; --muted:#6b7280; --line:#d9dde5;
          --accent:#2563eb; --accent-d:#1d4ed8; --ok:#16a34a; --err:#dc2626; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14171c; --card:#1c2027; --text:#e6e8ec; --muted:#98a1b0; --line:#323945;
            --accent:#4f8cff; --accent-d:#6aa0ff; --ok:#4ade80; --err:#f87171; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font:15px/1.5 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif; }
  main { max-width:880px; margin:0 auto; padding:24px 16px 48px; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:var(--muted); margin:0 0 20px; font-size:13px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; margin-bottom:16px; }
  #drop { border:2px dashed var(--line); border-radius:12px; min-height:180px; display:flex;
          flex-direction:column; align-items:center; justify-content:center; text-align:center;
          cursor:pointer; padding:16px; transition:.15s; color:var(--muted); }
  #drop.over { border-color:var(--accent); background:color-mix(in srgb, var(--accent) 8%, transparent); }
  #drop strong { color:var(--text); }
  #preview { max-width:100%; max-height:260px; display:none; border-radius:6px; background:#fff; }
  .row { display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
  .grow { flex:1; }
  select, button { font:inherit; padding:7px 12px; border-radius:8px; border:1px solid var(--line);
                   background:var(--card); color:var(--text); cursor:pointer; }
  button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
  button.primary:hover { background:var(--accent-d); }
  button:disabled { opacity:.5; cursor:not-allowed; }
  label.chk { display:flex; gap:6px; align-items:center; color:var(--muted); font-size:13px; cursor:pointer; }
  textarea { width:100%; min-height:110px; resize:vertical; padding:10px; border-radius:8px;
             border:1px solid var(--line); background:var(--bg); color:var(--text);
             font:14px/1.5 Consolas,"Cascadia Mono",monospace; }
  #render { padding:12px; overflow-x:auto; min-height:48px; }
  #status { font-size:13px; color:var(--muted); min-height:20px; }
  #status.ok { color:var(--ok); } #status.err { color:var(--err); }
  h2 { font-size:14px; margin:0 0 10px; color:var(--muted); font-weight:600; }
</style>
</head>
<body>
<main>
  <div class="row">
    <h1 class="grow" data-i18n="h1">Pix2Text</h1>
    <select id="lang" title="Language / 语言" aria-label="Language">
      <option value="zh">中文</option>
      <option value="en">English</option>
    </select>
  </div>
  <p class="sub" data-i18n="sub"></p>

  <div class="card">
    <div id="drop" tabindex="0">
      <img id="preview" alt="preview">
      <div id="hint"><strong data-i18n="drop1"></strong><br><span data-i18n="drop2"></span></div>
    </div>
    <input type="file" id="file" accept="image/*" hidden>
    <div class="row" style="margin-top:12px">
      <select id="mode" data-i18n-title="modeTitle">
        <option value="formula" data-i18n="modeFormula"></option>
        <option value="text_formula" data-i18n="modeMixed"></option>
      </select>
      <label class="chk"><input type="checkbox" id="auto" checked> <span data-i18n="auto"></span></label>
      <span class="grow"></span>
      <button id="go" class="primary" disabled data-i18n="go"></button>
    </div>
    <div id="status"></div>
  </div>

  <div class="card">
    <h2 data-i18n="h2out"></h2>
    <textarea id="out" spellcheck="false" data-i18n-ph="ph"></textarea>
    <div class="row" style="margin-top:10px">
      <button data-copy="raw" data-i18n="cpRaw"></button>
      <button data-copy="inline" data-i18n="cpInline"></button>
      <button data-copy="block" data-i18n="cpBlock"></button>
    </div>
  </div>

  <div class="card">
    <h2 data-i18n="h2prev"></h2>
    <div id="render"></div>
  </div>
</main>

<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<script>
const $ = id => document.getElementById(id);
const drop = $("drop"), fileInput = $("file"), preview = $("preview"), hint = $("hint");
const go = $("go"), out = $("out"), render = $("render"), statusEl = $("status"), modeSel = $("mode");
let currentBlob = null;

const I18N = {
  zh: {
    title: "Pix2Text 公式识别", h1: "Pix2Text 公式识别",
    sub: "拖入图片、点击选择，或直接 Ctrl+V 粘贴截图（Win+Shift+S 截图后粘贴最方便）。",
    drop1: "把图片拖到这里", drop2: "或点击选择文件 / 按 Ctrl+V 粘贴",
    modeTitle: "识别模式", modeFormula: "仅公式（单个公式截图）", modeMixed: "文字 + 公式混合",
    auto: "识别后自动复制", go: "识别",
    h2out: "LaTeX 结果（可手动修改，预览会同步刷新）", ph: "识别结果会显示在这里",
    cpRaw: "复制 LaTeX", cpInline: "复制 $…$", cpBlock: "复制 $$…$$",
    h2prev: "渲染预览（用来对照原图检查）",
    notImg: "这不是图片文件", ready: "图片已就绪，正在识别…", busy: "识别中…（首次可能稍慢）",
    done: "识别完成", doneCopied: "识别完成，已复制到剪贴板 ✔",
    doneNoCopy: "识别完成（自动复制失败，请手动点复制）", fail: "识别失败：",
    copied: "已复制 ✔", copyFail: "复制失败，请手动选中文本复制",
    noKatex: "（KaTeX 未加载，无法预览，请检查网络）", latexErr: "LaTeX 语法错误："
  },
  en: {
    title: "Pix2Text Formula OCR", h1: "Pix2Text Formula OCR",
    sub: "Drop an image, click to choose one, or paste with Ctrl+V (Win+Shift+S to take a screenshot, then paste).",
    drop1: "Drop an image here", drop2: "or click to choose a file / press Ctrl+V to paste",
    modeTitle: "Recognition mode", modeFormula: "Formula only (single formula image)", modeMixed: "Text + formulas (mixed)",
    auto: "Copy automatically after recognition", go: "Recognize",
    h2out: "LaTeX result (editable, the preview updates as you type)", ph: "The recognized LaTeX will appear here",
    cpRaw: "Copy LaTeX", cpInline: "Copy $…$", cpBlock: "Copy $$…$$",
    h2prev: "Rendered preview (compare with the original image)",
    notImg: "This is not an image file", ready: "Image ready, recognizing…", busy: "Recognizing… (the first run may be slower)",
    done: "Done", doneCopied: "Done, copied to clipboard ✔",
    doneNoCopy: "Done (auto-copy failed, please use a copy button)", fail: "Recognition failed: ",
    copied: "Copied ✔", copyFail: "Copy failed, please select the text and copy manually",
    noKatex: "(KaTeX failed to load, preview unavailable. Check your network.)", latexErr: "LaTeX syntax error: "
  }
};
function detectLang() {
  try { const s = localStorage.getItem("p2t_lang"); if (s && I18N[s]) return s; } catch (_) {}
  const l = ((navigator.languages && navigator.languages[0]) || navigator.language || "en").toLowerCase();
  return l.startsWith("zh") ? "zh" : "en";
}
let LANG = detectLang();
const tr = k => I18N[LANG][k];
function applyLang() {
  document.documentElement.lang = LANG === "zh" ? "zh-CN" : "en";
  document.title = tr("title");
  document.querySelectorAll("[data-i18n]").forEach(e => { e.textContent = tr(e.dataset.i18n); });
  document.querySelectorAll("[data-i18n-ph]").forEach(e => { e.placeholder = tr(e.dataset.i18nPh); });
  document.querySelectorAll("[data-i18n-title]").forEach(e => { e.title = tr(e.dataset.i18nTitle); });
  $("lang").value = LANG;
}
$("lang").addEventListener("change", () => {
  LANG = $("lang").value;
  try { localStorage.setItem("p2t_lang", LANG); } catch (_) {}
  applyLang(); updateRender();
});
applyLang();

function setStatus(msg, cls = "") { statusEl.textContent = msg; statusEl.className = cls; }

function setImage(blob) {
  if (!blob || !blob.type.startsWith("image/")) { setStatus(tr("notImg"), "err"); return; }
  currentBlob = blob;
  preview.src = URL.createObjectURL(blob);
  preview.style.display = "block";
  hint.style.display = "none";
  go.disabled = false;
  setStatus(tr("ready"));
  recognize();
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; }
  catch (e) {
    out.select();
    try { return document.execCommand("copy"); } catch (_) { return false; }
  }
}

function wrap(kind) {
  const t = out.value.trim();
  if (kind === "inline") return "$" + t + "$";
  if (kind === "block") return "$$\n" + t + "\n$$";
  return t;
}

function updateRender() {
  const t = out.value.trim();
  render.textContent = "";
  if (!t || !window.katex) { if (t && !window.katex) render.textContent = tr("noKatex"); return; }
  if (modeSel.value === "formula") {
    try { katex.render(t, render, { displayMode: true, throwOnError: true }); }
    catch (e) { render.textContent = tr("latexErr") + e.message; render.style.color = "var(--err)"; return; }
    render.style.color = "";
  } else {
    render.style.color = "";
    render.textContent = t;
    if (window.renderMathInElement) {
      renderMathInElement(render, { delimiters: [
        { left: "$$", right: "$$", display: true }, { left: "$", right: "$", display: false },
        { left: "\\[", right: "\\]", display: true }, { left: "\\(", right: "\\)", display: false } ],
        throwOnError: false });
    }
  }
}

async function recognize() {
  if (!currentBlob) return;
  go.disabled = true;
  setStatus(tr("busy"));
  try {
    const r = await fetch("/api/recognize?mode=" + modeSel.value, { method: "POST", body: currentBlob });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || r.statusText);
    out.value = j.result;
    updateRender();
    if ($("auto").checked) {
      const ok = await copyText(wrap("raw"));
      setStatus(ok ? tr("doneCopied") : tr("doneNoCopy"), ok ? "ok" : "");
    } else setStatus(tr("done"), "ok");
  } catch (e) { setStatus(tr("fail") + e.message, "err"); }
  finally { go.disabled = false; }
}

drop.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => fileInput.files[0] && setImage(fileInput.files[0]));
["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", e => { const f = e.dataTransfer.files[0]; if (f) setImage(f); });
window.addEventListener("dragover", e => e.preventDefault());
window.addEventListener("drop", e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) setImage(f); });
window.addEventListener("paste", e => {
  for (const it of e.clipboardData.items) if (it.type.startsWith("image/")) { setImage(it.getAsFile()); e.preventDefault(); return; }
});
go.addEventListener("click", recognize);
modeSel.addEventListener("change", () => currentBlob && recognize());
out.addEventListener("input", updateRender);
document.querySelectorAll("[data-copy]").forEach(b => b.addEventListener("click", async () => {
  const ok = await copyText(wrap(b.dataset.copy));
  setStatus(ok ? tr("copied") : tr("copyFail"), ok ? "ok" : "err");
}));
window.addEventListener("load", () => setTimeout(updateRender, 300));
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if urlparse(self.path).path in ("/", "/index.html"):
            self._send(200, HTML, "text/html; charset=utf-8")
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/api/recognize":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n)
            mode = parse_qs(url.query).get("mode", ["formula"])[0]
            img = Image.open(io.BytesIO(raw))
            result = recognize(img, mode)
            self._send(200, json.dumps({"result": result}, ensure_ascii=False))
        except Exception as e:
            self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    srv = None
    for p in range(PORT, PORT + 10):
        try:
            srv = ThreadingHTTPServer((HOST, p), Handler)
            break
        except OSError:
            continue
    if srv is None:
        raise SystemExit(T(f"端口 {PORT}-{PORT + 9} 都被占用，请关闭占用程序后重试",
                           f"Ports {PORT}-{PORT + 9} are all in use. Close the program using them and retry."))
    url = f"http://{HOST}:{srv.server_address[1]}"
    print(T(f"界面已启动：{url}  （Ctrl+C 退出）", f"UI running at {url}  (Ctrl+C to quit)"))
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(T("\n已退出", "\nStopped."))
