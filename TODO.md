# ⚔️ Nyx Refactor Battle Plan  
**Codename:** *Reflective Streaming + Structured Psyche*

## 🧠 Goals
Build a modular, emotionally reactive, psychologically layered character loop for Nyx.  
Enable real-time streaming with delayed reflection, memory surfacing, and relationship modeling.

---

## 🥇 Objective 1: **Streaming Mode**
> Let Nyx speak instantly — then think.

### ✅ Goals
- Stream LLM tokens as they arrive (for real-time UI)
- Buffer full response for post-processing
- Replace/enhance response in UI once parsed

### ✅ Tasks
- [ ] Introduce `ResponseSession` object to buffer tokens
- [ ] Refactor `chat_pipeline.process_message()` to stream output
- [ ] Run `response_parser` + `soul_processor` after stream ends
- [ ] UI: display parsed result (e.g. `main_text`) and tags after stream

---

## 🥈 Objective 2: **Parallel Image Scene Parser**
> Let her dream in pictures — on her own time.

### ✅ Goals
- Decouple image generation from `ResponseParser`
- Feed **raw Nyx response** to `image_scene_parser`
- Let it extract `<image>` tags directly
- Run in parallel to soul processing

### ✅ Tasks
- [ ] On LLM response completion, pass raw text to `image_scene_parser`
- [ ] Trigger image generation asynchronously (`asyncio.create_task`)
- [ ] Link generated image metadata to memory store + UI
- [ ] Show placeholders if image is delayed

---

## 🥉 Objective 3: **Expand ResponseParser to Soul Mediator**
> Turn parsing into memory generation and psychological inference.

### ✅ Goals
- Add new fields to `ResponseParser`:
  - `relationships`: e.g. `"VIOLATES", "EXPRESSES", "REINFORCES"`
  - `generated_memories`: insight fragments
- Store new memories and inferred structure via:
  - Qdrant (semantic memory)
  - Neo4j (concept graph)
  - WorkingMemoryBuffer (for next-turn injection)

### ✅ Tasks
- [ ] Expand system prompt for `ResponseParser`
- [ ] Support new schema fields in JSON output
- [ ] Store new memories into Qdrant
- [ ] Update graph using relationship info

---

## 🧩 Objective 4: **Neo4j Integration (Graph Store)**
> Memories don’t float — they relate.

### ✅ Goals
- Insert structured relationships between:
  - `Memory` ↔ `Value`, `Emotion`, `Pattern`
  - `Value` ↔ `Value` (conflicts)
- Enable soul traversal queries

### ✅ Tasks
- [ ] Add `graph_store.py` or `neo4j_handler.py`
- [ ] Create `add_node`, `add_relationship` helpers
- [ ] Wire into post-response step
- [ ] Optional: visualize relationship graph per memory

---

## 🔄 Pipeline Overview (Post-Refactor)

```text
[ User Message ]
       ↓
[ Context Injection ]
       ↓
[ Nyx (streamed LLM output) ]
       ↓
[ ResponseSession: buffers full output ]
       ↓
→ [ stream tokens to UI ]
→ [ parse tags, mood, thoughts ]
→ [ soul_processor: adds insights, triggers memories ]
→ [ graph_store: creates or updates nodes/edges ]
→ [ image_scene_parser (async): extracts and generates ]
→ [ update UI with parsed + reflected content ]
```

---

## 💡 Implementation Strategy

| Phase | Objectives |
|-------|------------|
| Phase 1 | ✅ Streaming Mode + `ResponseSession` |
| Phase 2 | ✅ Parallel Image Scene Parser |
| Phase 3 | ✅ Expanded ResponseParser |
| Phase 4 | ✅ Neo4j Integration |

