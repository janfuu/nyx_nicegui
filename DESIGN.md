# Nyx AI System Design

## Core Architecture

The system is built around a central state management system with specialized components for different functionalities. Here's the high-level architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                        State Manager                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Memory    │  │   World     │  │   Soul      │            │
│  │   System    │  │   State     │  │   State     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Core Services                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │    LLM      │  │   Image     │  │   Memory    │            │
│  │ Integration │  │  Generator  │  │   Store     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. State Management
- **State Manager**: Central hub for all state-related data
  - Manages memory, world state, and soul state
  - Provides single source of truth for system state
  - Handles state transitions and updates

### 2. Memory System

The memory system is responsible for storing and retrieving different types of memories:

1. **Conversation History (SQLite)**
   - Stores all conversation turns in chronological order
   - Used for immediate context and short-term memory
   - Temporary storage for the current session

2. **Semantic Memory (Qdrant)**
   - Stores significant mental states with vector embeddings:
     - `[[moment]]` tagged responses
     - All thoughts (with intensity)
     - All secrets (with intensity)
     - All fantasies (with intensity)
   - Each memory includes:
     - Text content
     - Vector embedding
     - Memory type (thought/secret/fantasy/moment)
     - Tags
     - Current mood
     - Intensity (float, 0-1)
     - Timestamp
   - Enables semantic search across all mental states
   - Memories are linked to current state context (mood, appearance, location)

3. **State Management (StateManager)**
   - Centralized state object for:
     - Current mood
     - Appearance
     - Location
     - Relationships
   - Provides context for memory storage and retrieval
   - Maintains consistency across the system

### 3. Embedder Service
- **Singleton Embedder**: Centralized embedding service
  - Text embeddings via SentenceTransformer
  - Image embeddings via CLIP
  - Consistent vector dimensions
  - Efficient resource usage through singleton pattern
  - Used by both memory and image systems

### 4. Image Management
- **Store Images Service**: Coordinates image storage
  - Primary file storage in MinIO
  - Metadata and embeddings in Qdrant
  - State context integration
  - URL management

- **Image Generator**: Manages image generation through Runware
  - Handles parallel image generation
  - Manages Runware API connections
  - Downloads and stores generated images
  - Integrates with MinIO for storage

### 5. Memory Storage
- **Qdrant Memory Store**: Vector database for semantic memory
  - Singleton service pattern for consistent state
  - Stores memories with embeddings
  - Handles similarity search
  - Manages image metadata
  - Links memories to state context

## Data Flow

### 1. Chat Processing
```
User Message → Chat Pipeline → LLM Integration → Response Parser → State Updates
     │              │              │                  │              │
     ▼              ▼              ▼                  ▼              ▼
Memory Search   Context Build   Response Gen   Structure Parse   State Manager
```

### 2. Image Generation
```
Scene Parser → Image Generator → Runware API → MinIO Storage → Qdrant Index
     │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼
Scene Parse   Parallel Gen    Image Gen     Store Image    Link to State
```

### 3. Memory Management
```
State Update → Memory System → Qdrant Store → Vector Search → Context Build
     │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼
State Change   Memory Update   Store Vector   Search Mem     Build Context
     │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼
SQLite Store   Check Type:     If Mental:     Search All     Use Both SQLite
All Convos     Moment/Thought/ Store Vector   Mental States  and Qdrant Results
               Secret/Fantasy
```

## Key Design Decisions

1. **State Centralization**
   - All state managed through State Manager
   - Components delegate state operations
   - Single source of truth for system state

2. **Singleton Services**
   - Core services use singleton pattern:
     - Embedder service
     - Qdrant stores (Memory and Image)
     - State Manager
   - Ensures consistent resource usage
   - Prevents duplicate initialization

3. **Memory Storage**
   - Memories stored in Qdrant with vectors
   - Images linked to state context
   - Semantic search enabled

4. **Configuration Management**
   - Hierarchical configuration system:
     1. Environment Variables (highest priority)
     2. YAML Configuration
     3. JSON Configuration
     4. Default Values (lowest priority)
   - Centralized Config class
   - Secure API key handling

5. **Logging System**
   - Centralized logging through root logger
   - Custom 'nyx' logger name
   - Consistent log levels:
     - DEBUG: Routine operations
     - INFO: Important state changes
     - ERROR: Critical issues
   - External service logs managed (httpx, etc.)

## Component Interactions

### Chat Pipeline
1. Receives user message
2. Retrieves context from State Manager
3. Generates response through LLM
4. Parses response for state updates
5. Updates State Manager
6. **Always** stores conversation in SQLite
7. Stores in Qdrant if:
   - Contains [[moment]] tag
   - Contains thoughts
   - Contains secrets
   - Contains other significant mental states

### Image Generation
1. Parses scene description
2. Generates images in parallel
3. Stores in MinIO
4. Updates Qdrant with metadata
5. Links to current state

### Memory Management
1. State changes trigger memory updates
2. Memories stored with state context
3. Vector search for relevant memories
4. Context built from memories
5. State updated with memory context

## Error Handling

1. **LLM Integration**
   - API error handling
   - Connection management
   - Response validation

2. **Image Generation**
   - Parallel request handling
   - Timeout management
   - Error recovery

3. **Memory System**
   - State consistency
   - Storage validation
   - Search fallbacks

## Future Considerations

1. **State Management**
   - Consider state versioning
   - Add state rollback capability
   - Implement state validation

2. **Memory System**
   - Add memory pruning
   - Implement memory weighting
   - Add memory clustering

3. **Image Generation**
   - Add image variation support
   - Implement style transfer
   - Add image editing capabilities 