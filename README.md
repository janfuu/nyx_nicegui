# Nyx - AI Chat Interface

A modern AI chat interface built with NiceGUI, featuring memory management, world state tracking, and image generation capabilities.

## Features

- Real-time chat interface with AI
- Memory system for context retention
- World state and relationship tracking
- Image generation integration
- Modular architecture
- Beautiful UI with dark theme

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

