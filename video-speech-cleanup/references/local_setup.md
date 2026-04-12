# Local Setup

Always ask before installing packages or changing PATH.

## Required Commands

Check:
```bash
command -v ffmpeg
command -v ffprobe
command -v auto-editor
```

`ffprobe` is normally included with FFmpeg installs.

## macOS

Preferred Homebrew path:
```bash
brew install ffmpeg
brew install auto-editor
```

Verify:
```bash
ffmpeg -version
ffprobe -version
auto-editor --version
```

If `brew` is missing, ask whether to install Homebrew or use downloadable binaries instead.

## Linux

Use the system package manager for FFmpeg:
```bash
sudo apt update
sudo apt install ffmpeg
```

For auto-editor, prefer the official binary release or distro package when available. If using Python packaging, warn that auto-editor docs currently do not recommend pip as the primary install path because newer releases may not be published there.

## Windows

Prefer official binary releases for FFmpeg and auto-editor, then add the executable directory to PATH. After PATH changes, open a new terminal and rerun the command checks.

## Notes

- **Python 3.9+** is required. The scripts use `timezone.utc` and type-union syntax available from Python 3.9/3.10.
- FFmpeg publishes source and links to OS/package builds from its download page.
- auto-editor's docs recommend official binaries first, then platform installers such as Homebrew, with pip as a fallback.
- If `auto-editor` can run from `./auto-editor` but not `auto-editor`, it is not on PATH.

## Practical limits

- The labeling step sends the full word list to the OpenAI model in a single request. For very long videos (roughly over 2 hours), the serialized transcript may exceed the model's context window and cause an API error. If you hit this, split the source video into shorter segments before processing.
