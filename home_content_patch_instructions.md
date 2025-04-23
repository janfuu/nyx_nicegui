# 🛠️ Patch Instructions for `home_content.py` — Structured Tag & Image Support

## 1. 🏷 Update `clean_response_text()` to use LLM-inserted tag markers

Already functional — ensure this continues to process:

```python
[[mood]] -> <span class="mood-marker">...</span>
[[thought]] -> <span class="thought-marker">...</span>
```

✅ **No changes needed here** if `main_text` is parsed as-is.

---

## 2. 🎯 Update Image Display in `display_message()`

### ✅ Replace this:
```python
image_tags = re.findall(r'<image>(.*?)</image>', response['main_text'], re.DOTALL)
```

### 🔄 With this:
```python
original_prompt = current_image.get("original_prompt", "")
parsed_prompt = current_image.get("parsed_prompt", current_image.get("description", ""))
```

### ✅ Then, update `lightbox.add_image()` to:
```python
lightbox.add_image(
    thumb_url=current_image["url"],
    orig_url=current_image["url"],
    image_id=image_uuid,
    original_prompt=original_prompt,
    parsed_prompt=parsed_prompt
)
```

---

## 3. 🧠 Extract `orientation` and `frame`

In the card or hover label, show:
```python
orientation = current_image.get("orientation", "")
frame = current_image.get("frame", None)
ui.label(f"[Frame {frame} | {orientation}]").classes('text-caption text-grey-5')
```

---

## 4. 🔁 UI Tag Panel Updates

Instead of pulling tag content from `main_text`, now use:
```python
response["mood"]
response["thoughts"]
response["appearance"]
response["clothing"]
```

Ensure you do not query `main_text` for structured content anymore.

---

## 5. 🧪 Optional Enhancements

- Highlight `mood`, `appearance`, or `clothing` **only if values changed**
- Add a “developer toggle” to show full structured JSON from LLM

---

## 📦 End Result

These changes make your UI fully compatible with:

- `[[tag]]`-based inline prose markers
- Structured JSON from OpenRouter schema
- Multi-frame visual rendering with tagged image metadata

Happy merging!