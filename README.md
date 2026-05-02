# Diff Viewer

A cross-platform diff viewer rebuilt with Tauri 2 and Vue 3.

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
