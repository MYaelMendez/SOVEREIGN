# VSCODER://

VS Code-native autonomous engineering agent. Semantic operations via LSP, refactoring, build/test/debug, git, benchmarks, receipts with hash chain.

## Commands

| Command | Title |
|---------|-------|
| `vscoder.open` | VSCODER:// Open Agent |
| `vscoder.observe` | VSCODER:// Observe Workspace |
| `vscoder.plan` | VSCODER:// Plan Task |
| `vscoder.refactor` | VSCODER:// Refactor |
| `vscoder.build` | VSCODER:// Build |
| `vscoder.test` | VSCODER:// Test |
| `vscoder.debug` | VSCODER:// Debug |
| `vscoder.benchmark` | VSCODER:// Benchmark |
| `vscoder.gitDiff` | VSCODER:// Git Diff |
| `vscoder.receipt` | VSCODER:// Show Receipt |

## Requirements

- VS Code ^1.85.0
- Ollama (for local LLM features)
- Python path configured for CUDA/benchmark tasks

## Extension Settings

- `vscoder.webmcpPort` — Port for the VSCODER WebMCP HTTP server (default: 8123)
- `vscoder.ollamaUrl` — Ollama server URL (default: http://localhost:11434)
- `vscoder.pythonPath` — Python interpreter path (default: C:/gpu/Scripts/python.exe)

## Building

```bash
npm install
npm run compile
npm run package
```

## License

MIT
