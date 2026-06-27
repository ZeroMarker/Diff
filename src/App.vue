<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  ArrowLeftRight,
  ArrowUp,
  ArrowDown,
  Clipboard,
  Eraser,
  FolderOpen,
  Moon,
  Sun,
  Copy,
  Search,
  WrapText,
  Pencil,
  Check,
  Settings2,
  CaseSensitive,
  Space,
} from "lucide-vue-next";
import { diffChars, diffLines } from "diff";
import { readText, readImage } from "@tauri-apps/plugin-clipboard-manager";

interface DiffLine {
  leftNum: number | null;
  rightNum: number | null;
  leftText: string;
  rightText: string;
  type: "equal" | "added" | "removed" | "modified";
  charDiffs?: { left: CharDiff[]; right: CharDiff[] };
}

interface CharDiff {
  value: string;
  type: "equal" | "added" | "removed";
}

const leftText = ref("");
const rightText = ref("");
const leftName = ref("Original");
const rightName = ref("Modified");
const isDark = ref(window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false);

const leftImage = ref<string | null>(null);
const rightImage = ref<string | null>(null);

const leftEditor = ref<HTMLDivElement>();
const rightEditor = ref<HTMLDivElement>();
const leftGutter = ref<HTMLDivElement>();
const rightGutter = ref<HTMLDivElement>();
const editorsContainer = ref<HTMLDivElement>();

const isSyncScroll = ref(true);
const isWordWrap = ref(false);
const currentChangeIndex = ref(-1);
const showSearch = ref(false);
const splitRatio = ref(50);

const searchQuery = ref("");
const searchCaseSensitive = ref(false);
const searchRegex = ref(false);
const searchMatchIndex = ref(-1);
const searchMatches = ref<Array<{ line: number; col: number; length: number; side: "left" | "right" }>>([]);
const searchMatchMap = ref<Map<string, Array<{ col: number; length: number; isActive: boolean }>>>(new Map());

const leftEditing = ref(false);
const rightEditing = ref(false);
const leftEditText = ref("");
const rightEditText = ref("");

const showRules = ref(false);
const rules = ref({
  ignoreLeadingSpace: false,
  ignoreAllSpace: false,
  ignoreCase: false,
  ignoreBlankLines: false,
});

let highlighter: any = null;
const highlightCache = new Map<string, string>();

function debounce<T extends (...args: any[]) => any>(fn: T, ms: number): T {
  let timer: ReturnType<typeof setTimeout>;
  return ((...args: any[]) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  }) as T;
}

function escapeRegex(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeLeading(s: string) {
  return s.replace(/^\s+/, "");
}

function normalizeAll(s: string) {
  return s.replace(/\s+/g, " ");
}

const leftProcessed = computed(() => {
  let t = leftText.value;
  if (rules.value.ignoreCase) t = t.toLowerCase();
  if (rules.value.ignoreAllSpace) t = normalizeAll(t);
  else if (rules.value.ignoreLeadingSpace) t = normalizeLeading(t);
  return t;
});

const rightProcessed = computed(() => {
  let t = rightText.value;
  if (rules.value.ignoreCase) t = t.toLowerCase();
  if (rules.value.ignoreAllSpace) t = normalizeAll(t);
  else if (rules.value.ignoreLeadingSpace) t = normalizeLeading(t);
  return t;
});

const leftLines = computed(() => leftText.value.split(/\r?\n/));
const rightLines = computed(() => rightText.value.split(/\r?\n/));

const diffResult = computed(() => {
  const opts: Record<string, boolean> = {};
  if (rules.value.ignoreBlankLines) opts.ignoreBlankLines = true;
  return diffLines(leftProcessed.value, rightProcessed.value, opts);
});

const diffLines_ = computed<DiffLine[]>(() => {
  const result: DiffLine[] = [];
  let leftLineNum = 1;
  let rightLineNum = 1;

  const origLeft = leftText.value.split(/\r?\n/);
  const origRight = rightText.value.split(/\r?\n/);
  let leftIdx = 0;
  let rightIdx = 0;

  for (const part of diffResult.value) {
    const lines = part.value.split(/\r?\n/);
    if (lines[lines.length - 1] === "") lines.pop();

    for (const _line of lines) {
      if (part.added) {
        result.push({
          leftNum: null,
          rightNum: rightLineNum++,
          leftText: "",
          rightText: origRight[rightIdx] ?? "",
          type: "added",
        });
        rightIdx++;
      } else if (part.removed) {
        result.push({
          leftNum: leftLineNum++,
          rightNum: null,
          leftText: origLeft[leftIdx] ?? "",
          rightText: "",
          type: "removed",
        });
        leftIdx++;
      } else {
        result.push({
          leftNum: leftLineNum++,
          rightNum: rightLineNum++,
          leftText: origLeft[leftIdx] ?? "",
          rightText: origRight[rightIdx] ?? "",
          type: "equal",
        });
        leftIdx++;
        rightIdx++;
      }
    }
  }

  const merged: DiffLine[] = [];
  let i = 0;
  while (i < result.length) {
    const curr = result[i];
    if (curr.type === "removed" && i + 1 < result.length && result[i + 1].type === "added") {
      const next = result[i + 1];
      const charDiffs = computeCharDiff(curr.leftText, next.rightText);
      merged.push({
        leftNum: curr.leftNum,
        rightNum: next.rightNum,
        leftText: curr.leftText,
        rightText: next.rightText,
        type: "modified",
        charDiffs,
      });
      i += 2;
    } else {
      merged.push(curr);
      i++;
    }
  }

  return merged;
});

function computeCharDiff(left: string, right: string): { left: CharDiff[]; right: CharDiff[] } {
  const diffs = diffChars(left, right);
  const leftDiffs: CharDiff[] = [];
  const rightDiffs: CharDiff[] = [];

  for (const d of diffs) {
    if (!d.added && !d.removed) {
      leftDiffs.push({ value: d.value, type: "equal" });
      rightDiffs.push({ value: d.value, type: "equal" });
    } else if (d.removed) {
      leftDiffs.push({ value: d.value, type: "removed" });
    } else if (d.added) {
      rightDiffs.push({ value: d.value, type: "added" });
    }
  }

  return { left: leftDiffs, right: rightDiffs };
}

const additions = computed(() => diffLines_.value.filter((l) => l.type === "added").length);
const removals = computed(() => diffLines_.value.filter((l) => l.type === "removed").length);
const modifications = computed(() => diffLines_.value.filter((l) => l.type === "modified").length);
const equalLines = computed(() => diffLines_.value.filter((l) => l.type === "equal").length);
const changePositions = computed(() =>
  diffLines_.value
    .map((line, idx) => (line.type !== "equal" ? idx : -1))
    .filter((idx) => idx !== -1),
);

const unifiedPatch = computed(() => {
  if (!leftText.value && !rightText.value) return "";
  let patch = `--- ${leftName.value}\n+++ ${rightName.value}\n`;
  let leftIdx = 0;
  let rightIdx = 0;

  for (const part of diffResult.value) {
    const lines = part.value.split(/\r?\n/);
    if (lines[lines.length - 1] === "") lines.pop();

    if (part.added) {
      patch += `@@ -${leftIdx},+${rightIdx + 1} @@\n`;
      for (const line of lines) {
        patch += `+${line}\n`;
        rightIdx++;
      }
    } else if (part.removed) {
      patch += `@@ -${leftIdx + 1},-${rightIdx} @@\n`;
      for (const line of lines) {
        patch += `-${line}\n`;
        leftIdx++;
      }
    } else {
      for (const line of lines) {
        patch += ` ${line}\n`;
        leftIdx++;
        rightIdx++;
      }
    }
  }
  return patch;
});

// Search
const totalSearchMatches = computed(() => searchMatches.value.length);

function findSearchMatches() {
  const matches: Array<{ line: number; col: number; length: number; side: "left" | "right" }> = [];
  if (!searchQuery.value) {
    searchMatches.value = matches;
    searchMatchIndex.value = -1;
    searchMatchMap.value = new Map();
    return;
  }

  const cs = searchCaseSensitive.value;
  let re: RegExp;
  try {
    const pattern = searchRegex.value ? searchQuery.value : escapeRegex(searchQuery.value);
    re = new RegExp(pattern, cs ? "g" : "gi");
  } catch {
    searchMatches.value = [];
    searchMatchIndex.value = -1;
    searchMatchMap.value = new Map();
    return;
  }

  for (let li = 0; li < diffLines_.value.length; li++) {
    const dl = diffLines_.value[li];
    if (dl.leftText) {
      re.lastIndex = 0;
      let m: RegExpExecArray | null;
      while ((m = re.exec(dl.leftText)) !== null) {
        matches.push({ line: li, col: m.index, length: m[0].length, side: "left" });
        if (m[0].length === 0) { re.lastIndex++; }
      }
    }
    if (dl.rightText) {
      re.lastIndex = 0;
      let m: RegExpExecArray | null;
      while ((m = re.exec(dl.rightText)) !== null) {
        matches.push({ line: li, col: m.index, length: m[0].length, side: "right" });
        if (m[0].length === 0) { re.lastIndex++; }
      }
    }
  }

  searchMatches.value = matches;
  searchMatchIndex.value = matches.length > 0 ? 0 : -1;

  const map = new Map<string, Array<{ col: number; length: number; isActive: boolean }>>();
  for (let mi = 0; mi < matches.length; mi++) {
    const m = matches[mi];
    const key = `${m.side}-${m.line}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push({ col: m.col, length: m.length, isActive: mi === searchMatchIndex.value });
  }
  searchMatchMap.value = map;
}

function updateSearchMatchMap() {
  const map = new Map<string, Array<{ col: number; length: number; isActive: boolean }>>();
  for (let mi = 0; mi < searchMatches.value.length; mi++) {
    const m = searchMatches.value[mi];
    const key = `${m.side}-${m.line}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push({ col: m.col, length: m.length, isActive: mi === searchMatchIndex.value });
  }
  searchMatchMap.value = map;
}

const activeSearchMatch = computed(() => {
  if (searchMatchIndex.value < 0 || searchMatchIndex.value >= searchMatches.value.length) return null;
  return searchMatches.value[searchMatchIndex.value];
});

function nextSearchMatch() {
  if (searchMatches.value.length === 0) return;
  searchMatchIndex.value = (searchMatchIndex.value + 1) % searchMatches.value.length;
  updateSearchMatchMap();
  scrollToActiveSearchMatch();
}

function prevSearchMatch() {
  if (searchMatches.value.length === 0) return;
  searchMatchIndex.value = (searchMatchIndex.value - 1 + searchMatches.value.length) % searchMatches.value.length;
  updateSearchMatchMap();
  scrollToActiveSearchMatch();
}

function scrollToActiveSearchMatch() {
  const m = activeSearchMatch.value;
  if (!m) return;
  const lineHeight = 20;
  const scrollTop = m.line * lineHeight - 100;
  if (leftEditor.value) {
    leftEditor.value.scrollTop = scrollTop;
    leftGutter.value && (leftGutter.value.scrollTop = scrollTop);
  }
  if (rightEditor.value) {
    rightEditor.value.scrollTop = scrollTop;
    rightGutter.value && (rightGutter.value.scrollTop = scrollTop);
  }
}

function highlightLine(lineIdx: number, spans: Array<{ value: string; type: string }>, side: "left" | "right"): string {
  const key = `${side}-${lineIdx}`;
  const matches = searchMatchMap.value.get(key);
  if (!matches || matches.length === 0) {
    return spans.map((s) => `<span class="${s.type}">${escapeHtml(s.value)}</span>`).join("");
  }

  const sorted = matches.slice().sort((a, b) => a.col - b.col);
  let result = "";
  let pos = 0;

  for (const span of spans) {
    const spanStart = pos;
    const spanEnd = pos + span.value.length;
    let spanPos = spanStart;

    for (const m of sorted) {
      const mStart = m.col;
      const mEnd = m.col + m.length;
      if (mEnd <= spanStart || mStart >= spanEnd) continue;

      const segStart = Math.max(mStart, spanStart);
      const segEnd = Math.min(mEnd, spanEnd);

      if (segStart > spanPos) {
        const before = span.value.slice(spanPos - spanStart, segStart - spanStart);
        result += `<span class="${span.type}">${escapeHtml(before)}</span>`;
      }

      const matchText = span.value.slice(segStart - spanStart, segEnd - spanStart);
      const cls = m.isActive ? `${span.type} search-active` : `${span.type} search-match`;
      result += `<span class="${cls}">${escapeHtml(matchText)}</span>`;
      spanPos = segEnd;
    }

    if (spanPos < spanEnd) {
      const after = span.value.slice(spanPos - spanStart);
      result += `<span class="${span.type}">${escapeHtml(after)}</span>`;
    }

    pos = spanEnd;
  }

  return result;
}

function escapeHtml(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderDiffLine(lineIdx: number, line: DiffLine, side: "left" | "right"): string {
  const text = side === "left" ? line.leftText : line.rightText;

  if (line.type === "modified" && line.charDiffs) {
    const spans = side === "left"
      ? line.charDiffs.left.map((cd) => ({ value: cd.value, type: cd.type }))
      : line.charDiffs.right.map((cd) => ({ value: cd.value, type: cd.type }));
    return highlightLine(lineIdx, spans, side);
  }

  if (line.type === "added" && side === "left") return "";
  if (line.type === "removed" && side === "right") return "";

  const spans = [{ value: text, type: line.type === "equal" ? "equal" : line.type }];
  return highlightLine(lineIdx, spans, side);
}

// Syntax highlighting
const langMap: Record<string, string> = {
  js: "javascript", jsx: "javascript", mjs: "javascript",
  ts: "typescript", tsx: "typescript", mts: "typescript",
  py: "python", pyw: "python",
  rs: "rust", java: "java",
  c: "c", h: "c",
  cpp: "cpp", cc: "cpp", cxx: "cpp", hpp: "cpp",
  go: "go",
  html: "html", htm: "html",
  css: "css", scss: "css", less: "css",
  json: "json", xml: "xml", svg: "xml",
  yaml: "yaml", yml: "yaml",
  md: "markdown", markdown: "markdown",
  sh: "shell", bash: "shell", zsh: "shell", bat: "shell", ps1: "shell",
  sql: "sql", toml: "toml",
  ini: "ini", cfg: "ini", conf: "ini",
};

function detectLanguage(): string {
  const name = (leftName.value !== "Original" ? leftName.value : rightName.value).toLowerCase();
  const ext = name.split(".").pop() || "";
  return langMap[ext] || "text";
}

async function ensureHighlighter() {
  if (highlighter) return;
  try {
    const { createHighlighterCore } = await import("@shikijs/core");
    const { createOnigurumaEngine } = await import("@shikijs/engine-oniguruma");
    const githubLight = await import("@shikijs/themes/github-light");
    const githubDark = await import("@shikijs/themes/github-dark");
    highlighter = await createHighlighterCore({
      themes: [githubLight.default, githubDark.default],
      langs: [],
      engine: createOnigurumaEngine(import("shiki/wasm")),
    });
  } catch (e) {
    console.warn("Failed to load syntax highlighter:", e);
  }
}

async function loadLangForCurrentFile() {
  if (!highlighter) return;
  const lang = detectLanguage();
  if (lang === "text") return;
  const loaded = highlighter.getLoadedLanguages();
  if (loaded.includes(lang)) return;
  try {
    const langModule = await import(`@shikijs/langs/${lang}`);
    await highlighter.loadLanguage(langModule.default);
    highlightCache.clear();
  } catch {
    // language not available
  }
}

function getHighlightedLine(text: string, lineIdx: number, side: "left" | "right"): string {
  if (!highlighter || !text) return escapeHtml(text);
  const theme = isDark.value ? "github-dark" : "github-light";
  const lang = detectLanguage();
  if (lang !== "text" && !highlighter.getLoadedLanguages().includes(lang)) {
    return escapeHtml(text);
  }
  const cacheKey = `${side}-${lineIdx}-${text}-${theme}-${lang}`;
  if (highlightCache.has(cacheKey)) return highlightCache.get(cacheKey)!;

  try {
    const html = highlighter.codeToHtml(text, { theme, lang });
    const inner = html.replace(/^<pre[^>]*><code[^>]*>/, "").replace(/<\/code><\/pre>$/, "");
    highlightCache.set(cacheKey, inner);
    return inner;
  } catch {
    return escapeHtml(text);
  }
}

// Scroll sync
let isScrollingFromSync = false;

function handleScroll(source: "left" | "right") {
  if (!isSyncScroll.value || isScrollingFromSync) return;
  isScrollingFromSync = true;

  const sourceEl = source === "left" ? leftEditor.value : rightEditor.value;
  const targetEl = source === "left" ? rightEditor.value : leftEditor.value;
  const targetGutter = source === "left" ? rightGutter.value : leftGutter.value;
  const sourceGutter = source === "left" ? leftGutter.value : rightGutter.value;

  if (sourceEl && targetEl) {
    targetEl.scrollTop = sourceEl.scrollTop;
    targetEl.scrollLeft = sourceEl.scrollLeft;
  }
  if (sourceEl && targetGutter) {
    targetGutter.scrollTop = sourceEl.scrollTop;
  }
  if (sourceEl && sourceGutter) {
    sourceGutter.scrollTop = sourceEl.scrollTop;
  }

  requestAnimationFrame(() => { isScrollingFromSync = false; });
}

// Divider drag
let isDragging = false;

function onDividerMouseDown(e: MouseEvent) {
  e.preventDefault();
  isDragging = true;
  document.addEventListener("mousemove", onDividerMouseMove);
  document.addEventListener("mouseup", onDividerMouseUp);
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
}

function onDividerMouseMove(e: MouseEvent) {
  if (!isDragging || !editorsContainer.value) return;
  const rect = editorsContainer.value.getBoundingClientRect();
  const ratio = ((e.clientX - rect.left) / rect.width) * 100;
  splitRatio.value = Math.max(15, Math.min(85, ratio));
}

function onDividerMouseUp() {
  isDragging = false;
  document.removeEventListener("mousemove", onDividerMouseMove);
  document.removeEventListener("mouseup", onDividerMouseUp);
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
}

function resetDivider() {
  splitRatio.value = 50;
}

// Navigation
function scrollToChange(index: number) {
  if (index < 0 || index >= changePositions.value.length) return;
  currentChangeIndex.value = index;
  const lineIdx = changePositions.value[index];
  const lineHeight = 20;
  const scrollTop = lineIdx * lineHeight - 100;

  if (leftEditor.value) {
    leftEditor.value.scrollTop = scrollTop;
    leftGutter.value && (leftGutter.value.scrollTop = scrollTop);
  }
  if (rightEditor.value) {
    rightEditor.value.scrollTop = scrollTop;
    rightGutter.value && (rightGutter.value.scrollTop = scrollTop);
  }
}

function nextChange() {
  const next = currentChangeIndex.value + 1;
  if (next < changePositions.value.length) scrollToChange(next);
}

function prevChange() {
  const prev = currentChangeIndex.value - 1;
  if (prev >= 0) scrollToChange(prev);
}

// File operations
async function openFile(side: "left" | "right", event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  if (file.type.startsWith("image/")) {
    const url = URL.createObjectURL(file);
    if (side === "left") {
      if (leftImage.value) URL.revokeObjectURL(leftImage.value);
      leftImage.value = url;
      leftText.value = "";
      leftName.value = file.name;
    } else {
      if (rightImage.value) URL.revokeObjectURL(rightImage.value);
      rightImage.value = url;
      rightText.value = "";
      rightName.value = file.name;
    }
  } else {
    const text = await file.text();
    if (side === "left") {
      if (leftImage.value) URL.revokeObjectURL(leftImage.value);
      leftImage.value = null;
      leftText.value = text;
      leftName.value = file.name;
    } else {
      if (rightImage.value) URL.revokeObjectURL(rightImage.value);
      rightImage.value = null;
      rightText.value = text;
      rightName.value = file.name;
    }
  }
  highlightCache.clear();
  input.value = "";
}

function handleDrop(event: DragEvent, side: "left" | "right") {
  event.preventDefault();
  const file = event.dataTransfer?.files[0];
  if (!file) return;

  if (file.type.startsWith("image/")) {
    const url = URL.createObjectURL(file);
    if (side === "left") {
      if (leftImage.value) URL.revokeObjectURL(leftImage.value);
      leftImage.value = url;
      leftText.value = "";
      leftName.value = file.name;
    } else {
      if (rightImage.value) URL.revokeObjectURL(rightImage.value);
      rightImage.value = url;
      rightText.value = "";
      rightName.value = file.name;
    }
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target?.result as string;
    if (side === "left") {
      if (leftImage.value) URL.revokeObjectURL(leftImage.value);
      leftImage.value = null;
      leftText.value = text;
      leftName.value = file.name;
    } else {
      if (rightImage.value) URL.revokeObjectURL(rightImage.value);
      rightImage.value = null;
      rightText.value = text;
      rightName.value = file.name;
    }
    highlightCache.clear();
  };
  reader.readAsText(file);
}

function handleDragOver(event: DragEvent) { event.preventDefault(); }

function setSide(side: "left" | "right", opts: { text?: string; image?: string; name: string }) {
  if (side === "left") {
    if (leftImage.value) URL.revokeObjectURL(leftImage.value);
    leftImage.value = opts.image ?? null;
    leftText.value = opts.text ?? "";
    leftName.value = opts.name;
  } else {
    if (rightImage.value) URL.revokeObjectURL(rightImage.value);
    rightImage.value = opts.image ?? null;
    rightText.value = opts.text ?? "";
    rightName.value = opts.name;
  }
  highlightCache.clear();
}

async function pasteFromClipboard(side: "left" | "right") {
  try {
    const img = await readImage();
    if (img) {
      const [rgba, size] = await Promise.all([img.rgba(), img.size()]);
      const canvas = document.createElement("canvas");
      canvas.width = size.width;
      canvas.height = size.height;
      const ctx = canvas.getContext("2d")!;
      const clamped = new Uint8ClampedArray(rgba.length);
      clamped.set(rgba);
      const imageData = new ImageData(clamped, size.width, size.height);
      ctx.putImageData(imageData, 0, 0);
      const url = canvas.toDataURL("image/png");
      setSide(side, { image: url, name: "Clipboard Image" });
      return;
    }
  } catch { /* no image */ }
  try {
    const text = await readText();
    setSide(side, { text, name: "Clipboard" });
  } catch { /* denied */ }
}

async function copyPatch() {
  if (unifiedPatch.value) await navigator.clipboard.writeText(unifiedPatch.value);
}

function swapSides() {
  [leftText.value, rightText.value] = [rightText.value, leftText.value];
  [leftImage.value, rightImage.value] = [rightImage.value, leftImage.value];
  [leftName.value, rightName.value] = [rightName.value, leftName.value];
  highlightCache.clear();
}

function clearAll() {
  leftText.value = "";
  rightText.value = "";
  if (leftImage.value) URL.revokeObjectURL(leftImage.value);
  if (rightImage.value) URL.revokeObjectURL(rightImage.value);
  leftImage.value = null;
  rightImage.value = null;
  leftName.value = "Original";
  rightName.value = "Modified";
  currentChangeIndex.value = -1;
  searchQuery.value = "";
  searchMatches.value = [];
  searchMatchIndex.value = -1;
  searchMatchMap.value = new Map();
  highlightCache.clear();
}

// Edit mode
function startEdit(side: "left" | "right") {
  if (side === "left") {
    leftEditText.value = leftText.value;
    leftEditing.value = true;
  } else {
    rightEditText.value = rightText.value;
    rightEditing.value = true;
  }
}

function finishEdit(side: "left" | "right") {
  if (side === "left") {
    leftText.value = leftEditText.value;
    leftEditing.value = false;
    leftEditText.value = "";
  } else {
    rightText.value = rightEditText.value;
    rightEditing.value = false;
    rightEditText.value = "";
  }
  highlightCache.clear();
}

// Rules
function toggleRules() {
  showRules.value = !showRules.value;
}

function closeRules() {
  showRules.value = false;
}

function handleRulesClickOutside(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (!target.closest(".rules-dropdown") && !target.closest('[title="Comparison rules"]')) {
    showRules.value = false;
  }
}

// Keyboard
function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === "f") {
    e.preventDefault();
    showSearch.value = !showSearch.value;
    if (showSearch.value) {
      setTimeout(() => {
        const input = document.querySelector(".search-input") as HTMLInputElement;
        input?.focus();
      }, 50);
    }
  }
  if (e.key === "F3" || ((e.ctrlKey || e.metaKey) && e.key === "g")) {
    e.preventDefault();
    if (showSearch.value && searchQuery.value) nextSearchMatch();
    else nextChange();
  }
  if (e.key === "Shift+F3" || ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "G")) {
    e.preventDefault();
    if (showSearch.value && searchQuery.value) prevSearchMatch();
    else prevChange();
  }
  if (e.key === "Escape") {
    if (showSearch.value) showSearch.value = false;
    if (showRules.value) showRules.value = false;
  }
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "S") {
    e.preventDefault();
    swapSides();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "e") {
    e.preventDefault();
    if (leftEditing.value) finishEdit("left");
    else startEdit("left");
  }
}

// Lifecycle
onMounted(async () => {
  document.addEventListener("keydown", handleKeydown);
  document.addEventListener("click", handleRulesClickOutside);
  const saved = localStorage.getItem("diff-rules");
  if (saved) {
    try { Object.assign(rules.value, JSON.parse(saved)); } catch { /* ignore */ }
  }
  ensureHighlighter();
});

onUnmounted(() => {
  document.removeEventListener("keydown", handleKeydown);
  document.removeEventListener("click", handleRulesClickOutside);
});

watch(isDark, (v) => { document.documentElement.classList.toggle("dark", v); });
watch(searchQuery, debounce(findSearchMatches, 200));
watch(searchCaseSensitive, findSearchMatches);
watch(searchRegex, findSearchMatches);
watch([leftName, rightName], debounce(loadLangForCurrentFile, 150));
watch(rules, (v) => {
  localStorage.setItem("diff-rules", JSON.stringify(v));
  highlightCache.clear();
}, { deep: true });
</script>

<template>
  <div :class="{ dark: isDark }" class="app-shell">
    <!-- Menu bar -->
    <div class="menu-bar">
      <div class="menu-items">
        <span class="menu-label">File</span>
        <span class="menu-label">Edit</span>
        <span class="menu-label">View</span>
        <span class="menu-label">Tools</span>
        <span class="menu-label">Help</span>
      </div>
      <div class="menu-actions">
        <button type="button" class="menu-btn" title="Toggle theme" @click="isDark = !isDark">
          <Moon v-if="!isDark" :size="14" />
          <Sun v-else :size="14" />
        </button>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-group">
        <button type="button" class="tb-btn" title="Swap sides (Ctrl+Shift+S)" @click="swapSides">
          <ArrowLeftRight :size="15" />
          <span>Swap</span>
        </button>
        <button type="button" class="tb-btn" title="Copy unified patch" @click="copyPatch">
          <Copy :size="15" />
          <span>Copy Patch</span>
        </button>
        <button type="button" class="tb-btn danger" title="Clear all" @click="clearAll">
          <Eraser :size="15" />
          <span>Clear</span>
        </button>
        <div class="tb-separator"></div>
        <button type="button" class="tb-btn" :class="{ active: isSyncScroll }" title="Toggle synchronized scrolling" @click="isSyncScroll = !isSyncScroll">
          <span>Sync Scroll</span>
        </button>
        <button type="button" class="tb-btn" :class="{ active: isWordWrap }" title="Toggle word wrap" @click="isWordWrap = !isWordWrap">
          <WrapText :size="15" />
          <span>Wrap</span>
        </button>
        <div class="tb-separator"></div>
        <button type="button" class="tb-btn" title="Previous change (Shift+F3)" @click="prevChange" :disabled="changePositions.length === 0">
          <ArrowUp :size="15" />
        </button>
        <button type="button" class="tb-btn" title="Next change (F3)" @click="nextChange" :disabled="changePositions.length === 0">
          <ArrowDown :size="15" />
        </button>
        <span class="change-counter" v-if="changePositions.length > 0">
          {{ currentChangeIndex + 1 }}/{{ changePositions.length }}
        </span>
        <div class="tb-separator"></div>
        <button type="button" class="tb-btn" title="Search (Ctrl+F)" @click="showSearch = !showSearch">
          <Search :size="15" />
        </button>
        <div class="rules-wrapper">
          <button type="button" class="tb-btn" :class="{ active: showRules }" title="Comparison rules" @click.stop="toggleRules">
            <Settings2 :size="15" />
          </button>
          <div class="rules-dropdown" v-if="showRules" @click.stop>
            <label class="rule-item">
              <input type="checkbox" v-model="rules.ignoreLeadingSpace" />
              <Space :size="14" />
              <span>Ignore leading whitespace</span>
            </label>
            <label class="rule-item">
              <input type="checkbox" v-model="rules.ignoreAllSpace" />
              <Space :size="14" />
              <span>Ignore all whitespace</span>
            </label>
            <label class="rule-item">
              <input type="checkbox" v-model="rules.ignoreCase" />
              <CaseSensitive :size="14" />
              <span>Ignore case</span>
            </label>
            <label class="rule-item">
              <input type="checkbox" v-model="rules.ignoreBlankLines" />
              <span style="width:14px;display:inline-block"></span>
              <span>Ignore blank lines</span>
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- Search bar -->
    <div class="search-bar" v-if="showSearch">
      <input v-model="searchQuery" type="text" placeholder="Search..." class="search-input" autofocus />
      <label class="search-opt" title="Case sensitive">
        <input type="checkbox" v-model="searchCaseSensitive" />
        <CaseSensitive :size="14" />
      </label>
      <label class="search-opt" title="Regular expression">
        <input type="checkbox" v-model="searchRegex" />
        <span style="font-size:11px;font-weight:700">.*</span>
      </label>
      <span class="search-counter" v-if="searchQuery">
        {{ searchMatchIndex >= 0 ? searchMatchIndex + 1 : 0 }}/{{ totalSearchMatches }}
      </span>
      <button type="button" class="tb-btn" @click="prevSearchMatch" :disabled="totalSearchMatches === 0">Prev</button>
      <button type="button" class="tb-btn" @click="nextSearchMatch" :disabled="totalSearchMatches === 0">Next</button>
    </div>

    <!-- Editors -->
    <div class="editors-container" ref="editorsContainer" :style="{ gridTemplateColumns: splitRatio + '% ' + (100 - splitRatio) + '%' }">
      <!-- Left pane -->
      <div class="editor-pane">
        <div class="pane-header">
          <div class="pane-title">
            <span class="file-indicator left"></span>
            <span class="file-name">{{ leftName }}</span>
          </div>
          <div class="pane-actions">
            <button type="button" class="pane-btn" :class="{ active: leftEditing }" title="Edit mode (Ctrl+E)" @click="leftEditing ? finishEdit('left') : startEdit('left')">
              <Pencil v-if="!leftEditing" :size="14" />
              <Check v-else :size="14" />
            </button>
            <label class="pane-btn" title="Open file">
              <FolderOpen :size="14" />
              <input type="file" accept="image/*,.txt,.json,.xml,.csv,.log,.md,.html,.css,.js,.ts,.py,.java,.c,.cpp,.h,.hpp,.rs,.go,.rb,.php,.sh,.bat,.ps1,.yaml,.yml,.toml,.ini,.cfg,.conf,.env,.gitignore,.dockerfile" @change="openFile('left', $event)" />
            </label>
            <button type="button" class="pane-btn" title="Paste from clipboard" @click="pasteFromClipboard('left')">
              <Clipboard :size="14" />
            </button>
          </div>
        </div>
        <div class="editor-body" @drop="handleDrop($event, 'left')" @dragover="handleDragOver">
          <template v-if="leftImage">
            <div class="image-preview">
              <img :src="leftImage" alt="Clipboard image" />
            </div>
          </template>
          <template v-else-if="leftEditing">
            <textarea class="edit-textarea" :class="{ wrap: isWordWrap }" v-model="leftEditText" spellcheck="false"></textarea>
          </template>
          <template v-else>
            <div class="gutter" ref="leftGutter">
              <div v-for="(line, idx) in diffLines_" :key="'ln-' + idx" class="gutter-line">
                <span class="line-num" v-if="line.leftNum !== null">{{ line.leftNum }}</span>
                <span v-else class="line-num empty"></span>
                <span class="change-marker" :class="line.type">
                  {{ line.type === "added" ? "+" : line.type === "removed" ? "-" : line.type === "modified" ? "~" : "" }}
                </span>
              </div>
            </div>
            <div class="diff-lines" :class="{ wrap: isWordWrap }" ref="leftEditor" @scroll="handleScroll('left')">
              <div v-for="(line, idx) in diffLines_" :key="'ld-' + idx" class="diff-line" :class="line.type" v-html="renderDiffLine(idx, line, 'left')"></div>
            </div>
          </template>
        </div>
      </div>

      <!-- Divider -->
      <div class="pane-divider" @dblclick="resetDivider" @mousedown="onDividerMouseDown">
        <div class="divider-line"></div>
      </div>

      <!-- Right pane -->
      <div class="editor-pane">
        <div class="pane-header">
          <div class="pane-title">
            <span class="file-indicator right"></span>
            <span class="file-name">{{ rightName }}</span>
          </div>
          <div class="pane-actions">
            <button type="button" class="pane-btn" :class="{ active: rightEditing }" title="Edit mode" @click="rightEditing ? finishEdit('right') : startEdit('right')">
              <Pencil v-if="!rightEditing" :size="14" />
              <Check v-else :size="14" />
            </button>
            <label class="pane-btn" title="Open file">
              <FolderOpen :size="14" />
              <input type="file" accept="image/*,.txt,.json,.xml,.csv,.log,.md,.html,.css,.js,.ts,.py,.java,.c,.cpp,.h,.hpp,.rs,.go,.rb,.php,.sh,.bat,.ps1,.yaml,.yml,.toml,.ini,.cfg,.conf,.env,.gitignore,.dockerfile" @change="openFile('right', $event)" />
            </label>
            <button type="button" class="pane-btn" title="Paste from clipboard" @click="pasteFromClipboard('right')">
              <Clipboard :size="14" />
            </button>
          </div>
        </div>
        <div class="editor-body" @drop="handleDrop($event, 'right')" @dragover="handleDragOver">
          <template v-if="rightImage">
            <div class="image-preview">
              <img :src="rightImage" alt="Clipboard image" />
            </div>
          </template>
          <template v-else-if="rightEditing">
            <textarea class="edit-textarea" :class="{ wrap: isWordWrap }" v-model="rightEditText" spellcheck="false"></textarea>
          </template>
          <template v-else>
            <div class="gutter" ref="rightGutter">
              <div v-for="(line, idx) in diffLines_" :key="'rn-' + idx" class="gutter-line">
                <span class="line-num" v-if="line.rightNum !== null">{{ line.rightNum }}</span>
                <span v-else class="line-num empty"></span>
                <span class="change-marker" :class="line.type">
                  {{ line.type === "added" ? "+" : line.type === "removed" ? "-" : line.type === "modified" ? "~" : "" }}
                </span>
              </div>
            </div>
            <div class="diff-lines" :class="{ wrap: isWordWrap }" ref="rightEditor" @scroll="handleScroll('right')">
              <div v-for="(line, idx) in diffLines_" :key="'rd-' + idx" class="diff-line" :class="line.type" v-html="renderDiffLine(idx, line, 'right')"></div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Status bar -->
    <div class="status-bar">
      <div class="status-left">
        <span class="status-item equal">{{ equalLines }} equal</span>
        <span class="status-item added">+{{ additions }} added</span>
        <span class="status-item removed">-{{ removals }} removed</span>
        <span class="status-item modified">~{{ modifications }} modified</span>
      </div>
      <div class="status-right">
        <span class="status-item" v-if="rules.ignoreCase || rules.ignoreLeadingSpace || rules.ignoreAllSpace || rules.ignoreBlankLines">Rules active</span>
        <span class="status-item">{{ diffLines_.length }} lines</span>
        <span class="status-item">{{ leftLines.length }} ↔ {{ rightLines.length }}</span>
      </div>
    </div>
  </div>
</template>
