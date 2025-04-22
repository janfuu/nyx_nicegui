# Nyx - AI Chat Interface

A modern AI chat interface built with NiceGUI, featuring memory management, world state tracking, and image generation capabilities.

## Features

- Real-time chat interface with AI
- Memory system for context retention
- World state and relationship tracking
- Image generation integration
- Modular architecture
- Beautiful UI with dark theme

## Special Tags

The system recognizes the following special tags in messages:

| Tag | Example | Purpose |
|-----|---------|---------|
| `<desire>...</desire>` | `<desire>strong desire to explore</desire>` | Highlights desires with a pale pink background |
| `<internal>...</internal>` | `<internal>thinking to myself</internal>` | Indicates internal thoughts with a light blue background |
| `<fantasy>...</fantasy>` | `<fantasy>imagining flying</fantasy>` | Shows fantasy content with a light purple background |
| `<hidden>...</hidden>` | `<hidden>visible but styled differently</hidden>` | Content that's styled with a gray background |
| `<private>...</private>` | `<private>personal thoughts</private>` | Personal content with a light brown background |
| `<thought>...</thought>` | `<thought>analytical observation</thought>` | Hidden from chat, displayed in thoughts panel |
| `<mood>...</mood>` | `<mood>curious and excited</mood>` | Updates mood in sidebar, hidden from chat |
| `<appearance>...</appearance>` | `<appearance>wearing blue jacket</appearance>` | Updates appearance in sidebar, hidden from chat |
| `<location>...</location>` | `<location>in a high-tech lab</location>` | Updates location state, hidden from chat |
| `<image>...</image>` | `<image>cyberpunk cityscape</image>` | Generates an image based on description |
| `<secret>...</secret>` | `<secret>hidden content</secret>` | Completely hidden content, indicated with lock icon |

## Project Structure

```
nyx_nicegui/
├── app/
│   ├── assets/            # Static assets (CSS, images)
│   ├── components/        # UI components
│   ├── core/             # Core functionality
│   ├── models/           # Data models
│   ├── services/         # Business logic services
│   ├── utils/            # Utility functions
│   └── main.py           # Main app entry point
├── data/                 # Data storage
└── docker/              # Docker configuration
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure the application:
   - Copy `config.example.json` to `config.json`
   - Update the configuration as needed

3. Run the application:
   ```bash
   python -m app.main
   ```

## Development

- Python 3.10+
- NiceGUI framework
- SQLite database
- Docker support

## License

MIT License

## Qdrant Setup

### Using Docker (Recommended)
```bash
docker run -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_data:/qdrant/storage \
    qdrant/qdrant
```

### Without Docker
1. Download Qdrant from https://qdrant.tech/documentation/quick-start/
2. Configure it to run on port 6333
3. Start the server

### Configuration
Qdrant settings can be modified in `app/config.yaml` under the `qdrant` section.

