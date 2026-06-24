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
} from "lucide-vue-next";
import { diffChars, diffLines } from "diff";

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

const leftEditor = ref<HTMLDivElement>();
const rightEditor = ref<HTMLDivElement>();
const leftGutter = ref<HTMLDivElement>();
const rightGutter = ref<HTMLDivElement>();

const isSyncScroll = ref(true);
const currentChangeIndex = ref(-1);
const searchQuery = ref("");
const showSearch = ref(false);

const leftLines = computed(() => leftText.value.split(/\r?\n/));
const rightLines = computed(() => rightText.value.split(/\r?\n/));

const diffResult = computed(() => diffLines(leftText.value, rightText.value));

const diffLines_ = computed<DiffLine[]>(() => {
  const result: DiffLine[] = [];
  let leftLineNum = 1;
  let rightLineNum = 1;

  for (const part of diffResult.value) {
    const lines = part.value.split(/\r?\n/);
    if (lines[lines.length - 1] === "") lines.pop();

    for (const line of lines) {
      if (part.added) {
        result.push({
          leftNum: null,
          rightNum: rightLineNum++,
          leftText: "",
          rightText: line,
          type: "added",
        });
      } else if (part.removed) {
        result.push({
          leftNum: leftLineNum++,
          rightNum: null,
          leftText: line,
          rightText: "",
          type: "removed",
        });
      } else {
        result.push({
          leftNum: leftLineNum++,
          rightNum: rightLineNum++,
          leftText: line,
          rightText: line,
          type: "equal",
        });
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

let isScrollingFromSync = false;

function handleScroll(source: "left" | "right") {
  if (!isSyncScroll.value || isScrollingFromSync) return;
  isScrollingFromSync = true;

  const sourceEl = source === "left" ? leftEditor.value : rightEditor.value;
  const targetEl = source === "left" ? rightEditor.value : leftEditor.value;
  const targetGutter = source === "left" ? rightGutter.value : leftGutter.value;

  if (sourceEl && targetEl) {
    targetEl.scrollTop = sourceEl.scrollTop;
    targetEl.scrollLeft = sourceEl.scrollLeft;
  }
  if (sourceEl && targetGutter) {
    targetGutter.scrollTop = sourceEl.scrollTop;
  }

  requestAnimationFrame(() => {
    isScrollingFromSync = false;
  });
}

function syncGutterScroll(source: "left" | "right") {
  const sourceEl = source === "left" ? leftEditor.value : rightEditor.value;
  const sourceGutter = source === "left" ? leftGutter.value : rightGutter.value;
  if (sourceEl && sourceGutter) {
    sourceGutter.scrollTop = sourceEl.scrollTop;
  }
}

function scrollToChange(index: number) {
  if (index < 0 || index >= changePositions.value.length) return;
  currentChangeIndex.value = index;
  const lineIdx = changePositions.value[index];
  const lineHeight = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--line-height")) || 20;
  const scrollTop = lineIdx * lineHeight - 100;

  if (leftEditor.value) {
    leftEditor.value.scrollTop = scrollTop;
    syncGutterScroll("left");
  }
  if (rightEditor.value) {
    rightEditor.value.scrollTop = scrollTop;
    syncGutterScroll("right");
  }
}

function nextChange() {
  const next = currentChangeIndex.value + 1;
  if (next < changePositions.value.length) {
    scrollToChange(next);
  }
}

function prevChange() {
  const prev = currentChangeIndex.value - 1;
  if (prev >= 0) {
    scrollToChange(prev);
  }
}

async function openFile(side: "left" | "right", event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  const text = await file.text();
  if (side === "left") {
    leftText.value = text;
    leftName.value = file.name;
  } else {
    rightText.value = text;
    rightName.value = file.name;
  }
  input.value = "";
}

function handleDrop(event: DragEvent, side: "left" | "right") {
  event.preventDefault();
  const file = event.dataTransfer?.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target?.result as string;
    if (side === "left") {
      leftText.value = text;
      leftName.value = file.name;
    } else {
      rightText.value = text;
      rightName.value = file.name;
    }
  };
  reader.readAsText(file);
}

function handleDragOver(event: DragEvent) {
  event.preventDefault();
}

async function pasteFromClipboard(side: "left" | "right") {
  try {
    const text = await navigator.clipboard.readText();
    if (side === "left") {
      leftText.value = text;
      leftName.value = "Clipboard";
    } else {
      rightText.value = text;
      rightName.value = "Clipboard";
    }
  } catch {
    // clipboard access denied
  }
}

async function copyPatch() {
  if (unifiedPatch.value) {
    await navigator.clipboard.writeText(unifiedPatch.value);
  }
}

function swapSides() {
  [leftText.value, rightText.value] = [rightText.value, leftText.value];
  [leftName.value, rightName.value] = [rightName.value, leftName.value];
}

function clearAll() {
  leftText.value = "";
  rightText.value = "";
  leftName.value = "Original";
  rightName.value = "Modified";
  currentChangeIndex.value = -1;
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === "f") {
    e.preventDefault();
    showSearch.value = !showSearch.value;
  }
  if (e.key === "F3" || ((e.ctrlKey || e.metaKey) && e.key === "g")) {
    e.preventDefault();
    nextChange();
  }
  if (e.key === "Shift+F3" || ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "G")) {
    e.preventDefault();
    prevChange();
  }
  if (e.key === "Escape") {
    showSearch.value = false;
  }
}

onMounted(() => {
  document.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener("keydown", handleKeydown);
});

watch(isDark, (v) => {
  document.documentElement.classList.toggle("dark", v);
});
</script>

<template>
  <div :class="{ dark: isDark }" class="app-shell">
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
        <button type="button" class="tb-btn" title="Search (Ctrl+F)" @click="showSearch = !showSearch">
          <Search :size="15" />
        </button>
      </div>
    </div>

    <div class="search-bar" v-if="showSearch">
      <input v-model="searchQuery" type="text" placeholder="Search..." class="search-input" />
      <button type="button" class="tb-btn" @click="nextChange">Next</button>
      <button type="button" class="tb-btn" @click="prevChange">Prev</button>
    </div>

    <div class="editors-container">
      <div class="editor-pane">
        <div class="pane-header">
          <div class="pane-title">
            <span class="file-indicator left"></span>
            <span class="file-name">{{ leftName }}</span>
          </div>
          <div class="pane-actions">
            <label class="pane-btn" title="Open file">
              <FolderOpen :size="14" />
              <input type="file" @change="openFile('left', $event)" />
            </label>
            <button type="button" class="pane-btn" title="Paste from clipboard" @click="pasteFromClipboard('left')">
              <Clipboard :size="14" />
            </button>
          </div>
        </div>
        <div
          class="editor-body"
          @drop="handleDrop($event, 'left')"
          @dragover="handleDragOver"
        >
          <div class="gutter" ref="leftGutter">
            <div v-for="(line, idx) in diffLines_" :key="'ln-' + idx" class="gutter-line">
              <span class="line-num" v-if="line.leftNum !== null">{{ line.leftNum }}</span>
              <span v-else class="line-num empty"></span>
              <span class="change-marker" :class="line.type">
                {{ line.type === "added" ? "+" : line.type === "removed" ? "-" : line.type === "modified" ? "~" : "" }}
              </span>
            </div>
          </div>
          <div class="diff-lines" ref="leftEditor" @scroll="handleScroll('left')">
            <div v-for="(line, idx) in diffLines_" :key="'ld-' + idx" class="diff-line" :class="line.type">
              <template v-if="line.type === 'modified' && line.charDiffs">
                <template v-for="(cd, ci) in line.charDiffs.left" :key="ci">
                  <span :class="cd.type">{{ cd.value }}</span>
                </template>
              </template>
              <template v-else>{{ line.leftText }}</template>
            </div>
          </div>
        </div>
      </div>

      <div class="editor-pane">
        <div class="pane-header">
          <div class="pane-title">
            <span class="file-indicator right"></span>
            <span class="file-name">{{ rightName }}</span>
          </div>
          <div class="pane-actions">
            <label class="pane-btn" title="Open file">
              <FolderOpen :size="14" />
              <input type="file" @change="openFile('right', $event)" />
            </label>
            <button type="button" class="pane-btn" title="Paste from clipboard" @click="pasteFromClipboard('right')">
              <Clipboard :size="14" />
            </button>
          </div>
        </div>
        <div
          class="editor-body"
          @drop="handleDrop($event, 'right')"
          @dragover="handleDragOver"
        >
          <div class="gutter" ref="rightGutter">
            <div v-for="(line, idx) in diffLines_" :key="'rn-' + idx" class="gutter-line">
              <span class="line-num" v-if="line.rightNum !== null">{{ line.rightNum }}</span>
              <span v-else class="line-num empty"></span>
              <span class="change-marker" :class="line.type">
                {{ line.type === "added" ? "+" : line.type === "removed" ? "-" : line.type === "modified" ? "~" : "" }}
              </span>
            </div>
          </div>
          <div class="diff-lines" ref="rightEditor" @scroll="handleScroll('right')">
            <div v-for="(line, idx) in diffLines_" :key="'rd-' + idx" class="diff-line" :class="line.type">
              <template v-if="line.type === 'modified' && line.charDiffs">
                <template v-for="(cd, ci) in line.charDiffs.right" :key="ci">
                  <span :class="cd.type">{{ cd.value }}</span>
                </template>
              </template>
              <template v-else>{{ line.rightText }}</template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="status-bar">
      <div class="status-left">
        <span class="status-item equal">{{ equalLines }} equal</span>
        <span class="status-item added">+{{ additions }} added</span>
        <span class="status-item removed">-{{ removals }} removed</span>
        <span class="status-item modified">~{{ modifications }} modified</span>
      </div>
      <div class="status-right">
        <span class="status-item">{{ diffLines_.length }} lines</span>
        <span class="status-item">{{ leftLines.length }} ↔ {{ rightLines.length }}</span>
      </div>
    </div>
  </div>
</template>
