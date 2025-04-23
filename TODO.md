# 🧠 Nyx System & UI Update Summary

This document summarizes all recent changes made to Nyx's tag structure, parsing, output format, and UI integration model.

---

## 🔧 Structural Changes to Response Format

### ✅ New JSON Response Format

Nyx’s responses are now parsed into the following strict format:

```json
{
  "mood": "string | null",
  "thoughts": ["array of strings"],
  "appearance": ["array of strings"],
  "clothing": ["array of strings"],
  "images": ["array of strings"],
  "main_text": "string with [[tag]] markers"
}
```

📄 Schema file: `response_schema.json`

---

## 🖼️ UI-Specific Changes

### 🆕 `main_text` Uses `[[tag]]` Placeholders

| Marker        | Meaning                         | Suggested UI Behavior         |
|---------------|----------------------------------|-------------------------------|
| `[[mood]]`     | Mood update                    | Mood icon or color pulse      |
| `[[thought]]`  | Internal voice                 | Italic bubble or side tag     |
| `[[appearance]]` | Physical state update        | Avatar refresh or fade        |
| `[[clothing]]` | Outfit description             | Outfit HUD update or preview  |
| `[[image]]`    | Visual moment prompt           | Scene thumbnail or toggle     |
| `[[fantasy]]`, `[[desire]]`, etc. | Advanced emotional/mental tags | Expandable thought UI         |

These markers are **injected by the parser**, not shown in Nyx’s raw reply.

---

## 💬 Tagging Guidelines for Nyx

- Tags can be closed with either `</tag>` or `</>`
- Tags should be visually descriptive, not narrative
- `<clothing>` and `<appearance>` should not include action
- Use one tag of each type per message, unless transitioning state
- Advanced tags supported:
  - `<fantasy>` — mental scenario
  - `<secret>` — hidden thought
  - `<memory>` — past recall
  - `<desire>` — inner yearning

📄 Updated LLM instruction: `instructions_updated_v4.yaml`

---

## 🧠 System + Parser Changes

### ✅ `response_parser.py`

- Supports malformed or incomplete tags
- Injects `[[tag]]` for UI icons
- Returns strict JSON conforming to `response_schema.json`
- Now uses `response_format: json_schema` with OpenRouter
- Supports universal closing tag: `</>`

📄 Parser config: `response_parser_strict_v2.yaml`

---

## 🎥 Image Scene Parser

- Supports splitting multi-action `<image>` blocks into multiple frames
- Frames have positional continuity and inferred orientation
- Used for dynamic image rendering via Stable Diffusion
- NOTE: This needs to be updated to use structured output, and return the original prompt together with the generator prompt

📄 Updated prompt: `image_scene_parser_updated.yaml`


---

## ✅ UI Integration To-Do

### Parsing & Display:
- Parse `main_text` → display with inline icons using `[[tag]]`
- Side panels → populated directly from JSON keys
- Only animate changes when value actually differs from last turn

### Optional Enhancements:
- Use `hover`, `expand`, or `fade` effects to reflect emotional depth
- Allow toggling between raw prose and structured UI mode (developer view?)

---

Let me know if you'd like this exported as a developer doc, or if we need a frontend mock to go with it.