# 🛠️ Patch Notes for `chat_pipeline.py` — Structured Output Alignment

These changes align the pipeline with the new JSON parser, tag-based `main_text`, and structured image data handling.

---

## 1. 🧼 Remove Obsolete `_extract_image_tags()` Method

This is no longer needed:
```python
@staticmethod
def _extract_image_tags(text: str) -> list[dict]:
```
- ❌ Based on raw `<image>` parsing, which has been replaced by LLM parser logic.
- ✅ All image text now comes from `parsed_content["images"]` as a **list of strings**.

---

## 2. ✅ Ensure `parsed_content["images"]` is Treated as a List of Strings

When creating `scene_contents`, wrap image strings like so:
```python
scene_contents = [{"prompt": content, "sequence": i+1} for i, content in enumerate(parsed_content["images"])]
```

✅ This is already being done correctly. No changes needed unless future updates break formatting.

---

## 3. ✍️ Rename `original_text` → `original_prompt` in Final Image Output

In this block:
```python
generated_images.append({
    "url": image_url,
    "description": ...,
    "id": image_uuid,
    "sequence": sequence,
    "original_text": ...
})
```

✅ Update to:
```python
"original_prompt": scene_contents[i].get("original_text", "")
```

This allows the frontend to use consistent naming for original image prose.

---

## 4. 🧪 Optional: Include `parsed_prompt` in Image Output (for debug or tagging)

If your image scene parser returns `prompt`, add:
```python
"parsed_prompt": scene_contents[i].get("prompt", "")
```

This helps show LLM-generated SD tags in the lightbox or tooltips.

---

## ✅ Return Format Consistency

Your final return is correct:
```python
return {
    "text": parsed_content["main_text"],
    "thoughts": [...],
    "mood": "...",
    "images": [...],
}
```

Just make sure:
- `text` contains `[[tag]]` markers from parser
- `images` is a list of structured image dicts matching frontend needs

---

Let me know if Qdrant-related tagging, world state integration, or memory pruning logic should be expanded next!