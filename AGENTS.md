# Repository Guidelines

## Project Structure & Module Organization
This repository currently stores a packaged Vosk speech model rather than application source code. The main content lives under `models/vosk-model-small-ru-0.22/`:

- `am/`: acoustic model binaries
- `conf/`: decoder and feature configuration
- `graph/`: decoding graph files and phone mappings
- `ivector/`: speaker adaptation data
- `README`: upstream model notes and accuracy metrics

Keep new assets under `models/` and preserve upstream directory names unless there is a strong reason to reorganize. If application code is added later, place it in a top-level `src/` directory and keep tests in `tests/`.

## Build, Test, and Development Commands
There is no local build system configured in this repository today. Useful verification commands are shell-based:

- `find models -maxdepth 2 -type f | sort`: inspect tracked model contents
- `du -sh models`: check asset size before committing large changes
- `file models/vosk-model-small-ru-0.22/am/final.mdl`: confirm binary assets were not corrupted

If you add scripts, prefer a documented entry point such as `Makefile` targets or `scripts/*.sh`.

## Coding Style & Naming Conventions
For documentation and scripts, use 4-space indentation and clear, descriptive names. Prefer lowercase, hyphenated directory names and avoid renaming upstream model folders. Keep shell scripts POSIX-friendly when practical, and add brief comments only where behavior is not obvious.

## Testing Guidelines
No automated test framework is present. For model updates, validate that required subdirectories (`am`, `conf`, `graph`, `ivector`) remain intact and that the bundled `README` still matches the shipped model version. If runtime code is introduced, add tests alongside it and document the command used to run them.

## Commit & Pull Request Guidelines
Git history is not available in this checkout, so use standard imperative commit messages such as `Add Vosk Russian model metadata` or `Update model packaging notes`. Keep commits focused on one change.

Pull requests should include:

- a short summary of what changed
- the source of any new model files or binaries
- size impact for added assets
- verification steps or commands run locally

## Security & Asset Handling
Do not commit secrets, API keys, or private audio samples. Large binary updates should note license/source provenance and whether the model can be redistributed.
