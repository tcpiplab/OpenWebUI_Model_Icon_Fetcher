
# README – Auto‑populate OpenWebUI Model Icons  


This document explains how to install the helper script, discover the models that OpenWebUI can reach (local Ollama, OpenAI, and optional Ollama‑Turbo endpoints), download a representative icon for each model, build the JSON map that the UI consumes, and make the icons available to an **OpenWebUI installation performed with `pip` on macOS**.

---

## 1. What the script does  

OpenWebUI shows a generic placeholder (a circle with “01”/“OI”) when it cannot find an entry for a model in `model-icons.json`.  
`OpenWebUI_Model_Icon_Fetcher.py` automates the three steps that would otherwise be manual:

1. **Collect model IDs** from the back‑ends you have configured.  
2. **Resolve an image** – it first tries to pull the model‑card picture from HuggingFace, then falls back to a small provider badge (OpenAI, Claude, …). If neither is available it points to a single `default.png` you provide once.  
3. **Write the mapping** (`model-icons.json`) and copy the PNG files into the static folder (`public/icons/`).  

When OpenWebUI restarts, the UI reads the new JSON file and displays the custom icons automatically.

---

## 2. Prerequisites  

| Requirement                                                                                                       | Why it’s needed |
|-------------------------------------------------------------------------------------------------------------------|-----------------|
| Python 3.9+ (the same interpreter you used for `pip install open-webui`)                                         | The script is pure Python and uses the standard library plus `requests`. |
| `requests` library (`pip install requests`)                                                                       | HTTP calls to Ollama, OpenAI and optional remote endpoints. |
| Network access to the Ollama daemon (`http://localhost:11434` by default) and any remote API you intend to query. |
| Write permission to OpenWebUI’s **public static directory** (see §3).                                            |

> **Tip:** If you use a virtual environment, activate it first so the script installs `requests` into the same environment as OpenWebUI.

```bash
# Example – activate a venv created for OpenWebUI
source ~/openwebui-venv/bin/activate
pip install requests
```

---

## 3. Locate OpenWebUI’s static folder  

When OpenWebUI is installed via `pip`, the static assets live under the package directory:

```
$(python -c "import importlib.util, pathlib; \
spec = importlib.util.find_spec('open_webui'); \
print(pathlib.Path(spec.origin).parent / 'public')")
```

The command prints a path similar to:

```
/Users/you/Library/Python/3.11/lib/python/site-packages/open_webui/public
```

Inside that directory you will find (or create) an `icons/` sub‑folder:

```
…/open_webui/public/icons/
```

All PNG files and the `model-icons.json` file that the script generates must be placed there.

> **If you prefer a custom location** you can set the environment variable `OPENWEBUI_STATIC_DIR` to point to a different directory before starting OpenWebUI. The script respects the same variable when determining where to write the assets.

---

## 4. Install the helper script  

1. **Create a folder** (e.g., `scripts/`) inside your OpenWebUI project root or any location you like.  
2. **Copy the script** `OpenWebUI_Model_Icon_Fetcher.py` (the full source is in the previous assistant message) into that folder.  
3. Make it executable (optional but convenient):

```bash
chmod +x scripts/OpenWebUI_Model_Icon_Fetcher.py
```

---

## 5. Running the script  

The script is deliberately minimal in its CLI. The most common invocation on macOS looks like:

```bash
# Activate the same venv that runs OpenWebUI
source ~/openwebui-venv/bin/activate

# Export Ollama Turbo API key if needed
export OLLAMA_TURBO_API_KEY="your-turbo-api-key"

# Run the script – replace the placeholders with real values where needed
python3 scripts/OpenWebUI_Model_Icon_Fetcher.py \
    --openai-key "$OPENAI_API_KEY" \
    --ollama-turbo-url "https://remote-ollama.example.com/v1/models"
```

### Command‑line flags  

| Flag | Description | Default |
|------|-------------|---------|
| `--openai-key` | OpenAI secret key; if omitted the script will also read the environment variable `OPENAI_API_KEY`. | – |
| `--ollama-url` | Base URL of the local Ollama daemon (e.g., `http://localhost:11434`). | `http://localhost:11434` |
| `--ollama-turbo-url` | Full URL to a remote Ollama‑Turbo `/v1/models` endpoint. If omitted, no Turbo query is performed. API key read from `OLLAMA_TURBO_API_KEY` environment variable. | – |
| `--icon-dir` | Filesystem directory where PNG icons will be stored. Must be a sub‑folder of OpenWebUI’s static folder (`public/icons`). | `./public/icons` (relative to the script’s cwd) |
| `--static-json` | Path of the generated JSON mapping. | `./public/icons/model-icons.json` |

The script will:

* Discover all models from the configured back‑ends.  
* Download a representative picture (HF card → provider badge).  
* Write a single `default.png` if you have not placed one yourself (a transparent 1×1 PNG).  
* Produce `model-icons.json` with entries like `"gpt-4o": "/icons/gpt-4o.png"`.

At the end you’ll see a concise summary:

```
✅  Generated mapping for 27 models → /Users/you/.../open_webui/public/icons/model-icons.json
🔄  Restart OpenWebUI (e.g., `pkill -f open_webui; open_webui`) to see the changes.
```

---

## 6. Restart OpenWebUI  

Because the static assets are read at start‑up, you must restart the server for new icons to appear. With a pip‑installed setup you usually launch the application via the entry point `open-webui` (or `python -m open_webui`). Restart it in the same terminal:

```bash
# If you launched it in the current shell
pkill -f open_webui   # or Ctrl‑C if it’s running in the foreground
open_webui            # start again
```

If you run it as a background service (e.g., using `launchd` or a systemd‑like manager), restart that service instead.

---

## 7. Verifying the result  

Open a browser pointed at your OpenWebUI instance (default `http://127.0.0.1:8080`). In the **model selector** you should now see the custom icons next to each model name, as well as in the chat header when a model is active.

If a particular model still shows the generic placeholder:

1. Open the generated `model-icons.json` and confirm that the model’s exact identifier (case‑sensitive) is present as a key.  
2. Verify that the referenced PNG file exists in `public/icons/`.  
3. Check the browser console for 404 errors on the icon URL—this indicates a path mismatch (the script always uses `/icons/<filename>`).

Adjust the slugification logic in the script if your model IDs contain characters that collapse to the same filename after sanitization.

---

## 8. Extending / Customising  

* **Add more provider badges** – edit the `provider_assets` dictionary in the script and provide a URL to a small logo (SVG/PNG).  
* **Prefer SVG** – change `resolve_icon_path()` to return `f'{slugify(model_id)}.svg'` and place SVG files in the icons folder. The UI will render them without further changes.  
* **Cache avoidance** – the script already skips downloading if the target file already exists. If you want a stricter cache‑invalidation (e.g., when a remote card image changes), delete the PNG file before re‑running.  
* **Run in CI** – add the script to your repository, have your CI pipeline call it, and then commit the generated `public/icons/` directory. Subsequent deployments will ship the icons out‑of‑the‑box.

---

## 9. Troubleshooting  

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Script aborts with `ConnectionError` to Ollama | Ollama daemon not running or listening on a different port | Start Ollama (`ollama serve`) or supply `--ollama-url http://host:port`). |
| No OpenAI models appear | `OPENAI_API_KEY` missing or invalid | Export a valid key (`export OPENAI_API_KEY=sk‑…`) or pass `--openai-key`. |
| Generated PNG files are empty / 0KB | Remote URL returned 404 (e.g., HF repo does not have `card.png`) | Provide a custom image manually or add a fallback badge for that model. |
| Icons still not shown after restart | `model-icons.json` not located where OpenWebUI expects it | Ensure the file lives under `…/open_webui/public/icons/` or set `OPENWEBUI_STATIC_DIR` accordingly. |
| UI shows a broken image icon | PNG filename contains characters the browser cannot resolve (e.g., spaces) | The script sanitises names with `slugify`; if you renamed files manually, rename them back to the slugified form. |

---

## 10. License  

The helper script is released under the **MIT License** (see the header comment in `OpenWebUI_Model_Icon_Fetcher.py`). Feel free to adapt it to your workflow.
