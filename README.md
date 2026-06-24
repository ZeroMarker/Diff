# Diff Viewer

A cross-platform diff viewer rebuilt with Tauri 2 and Vue 3. Inspired by Beyond Compare's core comparison features.

## Features

- **Side-by-side comparison** with synchronized scrolling
- **Inline character-level diff** highlighting for modified lines
- **Line numbers** with gutter change markers (`+`, `-`, `~`)
- **Change navigation** — jump between differences with F3/Shift+F3
- **Drag & drop** file loading
- **Unified patch** generation and copy
- **Search** with Ctrl+F
- **Dark/Light theme** toggle
- **Status bar** with diff statistics

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Toggle search bar |
| `F3` / `Ctrl+G` | Next change |
| `Shift+F3` / `Ctrl+Shift+G` | Previous change |
| `Escape` | Close search bar |

## Development

```sh
npm install
npm run dev
```

Run the Tauri shell locally:

```sh
npm run tauri -- dev
```

Build the web assets:

```sh
npm run build
```

Build the desktop app:

```sh
npm run tauri -- build
```

## CI

GitHub Actions builds these targets:

- Windows
- Linux
- macOS Intel
- macOS Apple Silicon
- Android
- iOS simulator

Tag releases with `v*`, for example:

```sh
git tag v1.3.0
git push origin v1.3.0
```
