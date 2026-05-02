<script setup lang="ts">
import { computed, ref } from "vue";
import { ArrowLeftRight, Clipboard, Eraser, FolderOpen, GitCompare, Moon, Sun } from "lucide-vue-next";
import { createPatch, diffLines } from "diff";

const leftText = ref("");
const rightText = ref("");
const leftName = ref("Original");
const rightName = ref("Modified");
const isDark = ref(window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false);

const leftLines = computed(() => leftText.value.split(/\r?\n/));
const rightLines = computed(() => rightText.value.split(/\r?\n/));

const changes = computed(() => diffLines(leftText.value, rightText.value));
const additions = computed(() => changes.value.filter((part) => part.added).reduce((sum, part) => sum + (part.count ?? 0), 0));
const removals = computed(() => changes.value.filter((part) => part.removed).reduce((sum, part) => sum + (part.count ?? 0), 0));
const patch = computed(() =>
  leftText.value || rightText.value
    ? createPatch(`${leftName.value} -> ${rightName.value}`, leftText.value, rightText.value, leftName.value, rightName.value)
    : "",
);

function lineNumbers(lines: string[]) {
  return lines.map((_, index) => index + 1).join("\n") || "1";
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

async function pasteFromClipboard(side: "left" | "right") {
  const text = await navigator.clipboard.readText();
  if (side === "left") {
    leftText.value = text;
    leftName.value = "Clipboard";
  } else {
    rightText.value = text;
    rightName.value = "Clipboard";
  }
}

async function copyPatch() {
  if (patch.value) await navigator.clipboard.writeText(patch.value);
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
}
</script>

<template>
  <main :class="{ dark: isDark }" class="shell">
    <header class="toolbar">
      <div>
        <h1>Diff Viewer</h1>
        <p>{{ additions }} additions, {{ removals }} removals, {{ changes.length }} hunks</p>
      </div>
      <div class="actions">
        <button type="button" class="icon-button" title="Swap files" @click="swapSides">
          <ArrowLeftRight :size="18" />
        </button>
        <button type="button" class="icon-button" title="Copy patch" @click="copyPatch">
          <Clipboard :size="18" />
        </button>
        <button type="button" class="icon-button danger" title="Clear all" @click="clearAll">
          <Eraser :size="18" />
        </button>
        <button type="button" class="icon-button" title="Toggle theme" @click="isDark = !isDark">
          <Moon v-if="!isDark" :size="18" />
          <Sun v-else :size="18" />
        </button>
      </div>
    </header>

    <section class="editors">
      <article class="pane">
        <div class="pane-head">
          <strong>{{ leftName }}</strong>
          <label class="tool-button" title="Open original file">
            <FolderOpen :size="17" />
            <input type="file" @change="openFile('left', $event)" />
          </label>
          <button type="button" class="tool-button" title="Paste original" @click="pasteFromClipboard('left')">
            <Clipboard :size="17" />
          </button>
        </div>
        <div class="editor-wrap">
          <pre aria-hidden="true">{{ lineNumbers(leftLines) }}</pre>
          <textarea v-model="leftText" spellcheck="false" aria-label="Original text"></textarea>
        </div>
      </article>

      <article class="pane">
        <div class="pane-head">
          <strong>{{ rightName }}</strong>
          <label class="tool-button" title="Open modified file">
            <FolderOpen :size="17" />
            <input type="file" @change="openFile('right', $event)" />
          </label>
          <button type="button" class="tool-button" title="Paste modified" @click="pasteFromClipboard('right')">
            <Clipboard :size="17" />
          </button>
        </div>
        <div class="editor-wrap">
          <pre aria-hidden="true">{{ lineNumbers(rightLines) }}</pre>
          <textarea v-model="rightText" spellcheck="false" aria-label="Modified text"></textarea>
        </div>
      </article>
    </section>

    <section class="diff-output" aria-label="Unified diff">
      <div class="diff-head">
        <GitCompare :size="17" />
        <span>Unified diff</span>
      </div>
      <pre v-if="patch">{{ patch }}</pre>
      <div v-else class="empty-state">Load or paste text on both sides to compare.</div>
    </section>
  </main>
</template>
