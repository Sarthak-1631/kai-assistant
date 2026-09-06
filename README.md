# KAI
Kai is an advanced AI Agent powered by the Gemini Flash Lite model, which serves as its core intelligence. Inspired by Jaredrhod's innovative work on AI Priming and the AI memory vault project, Kai is specifically designed to possess a genuine, persistent memory. To achieve this, the agent seamlessly integrates with Obsidian for long-term knowledge retention and utilizes ChromaDB to perform efficient, vector-based semantic searches across its stored information.

# CORE ARCHITECTURE

- **Intelligence Layer** Powered by Gemini Flash Lite, offering a balance of speed and capability for real-time interactions.

- **Memory Integration** Utilizes Obsidian as a localized, persistent memory vault, allowing the agent to retain context over time.

- **Semantic Retrieval** Employs ChromaDB to conduct vector searches, enabling the agent to recall relevant information based on conceptual similarity rather than exact keywords.

## Features

- **Vector Semantic Memory:** Uses a local ChromaDB vector database and Google's text-embedding-004 to search notes conceptually rather than by exact keywords.

- **Sleep Cycle Memory Consolidation:** Summarizes short-term conversation logs into core insights upon exit to save API costs and manage context limits.

- **Asynchronous Voice Output:** Utilizes macOS's built-in say command in background threads for non-blocking speech, while stripping out markdown syntax.

- **Obsidian Integration:** Automatically creates or updates daily notes with timestamped logs.

- **OS Control:** Integrates with the macOS clipboard and terminal.

- **Human-in-the-Loop Execution Layer:** Features a file writing tool that allows Kai to generate scripts and configs locally, secured by a strict terminal confirmation prompt

- **Task Queue System (`KAI-QUEUE.md`):** Reads to-do lists directly from the Obsidian vault, executing tasks sequentially and physically checking the markdown boxes upon completion.