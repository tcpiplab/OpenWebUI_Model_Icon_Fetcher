#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auto‑populate OpenWebUI model‑icon mapping.

The script:
    1. Queries Ollama, OpenAI and an optional Ollama‑Turbo endpoint for model IDs.
    2. Normalises the IDs to short, filesystem‑safe names.
    3. Tries to locate a representative icon (Hugging‑Face card image, provider badge,
       or a user‑supplied fallback).
    4. Writes a JSON file that OpenWebUI consumes (public/icons/model-icons.json).
    5. Places the icon files under the static folder so the UI can serve them.

Usage (run from the repository root or from a mounted volume):
    $ python3 scripts/generate_model_icons.py \
        --openai-key "$OPENAI_API_KEY" \
        --ollama-turbo-url http://remote-ollama:8080/v1/models \
        --icon-dir ./public/icons \
        --static-json ./public/icons/model-icons.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set
import requests

# -------------------------------------------------------------------------
# Helper utilities
# -------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Return a filesystem‑safe, lower‑case identifier."""
    # Keep alphanumerics, dash and underscore; replace everything else with `-`
    clean = re.sub(r'[^a-zA-Z0-9_-]+', '-', text).strip('-').lower()
    return clean or 'unknown'


def safe_write_json(path: Path, data: Dict) -> None:
    """Write JSON with sorted keys and a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as fp:
        json.dump(data, fp, indent=2, sort_keys=True)
        fp.write('\n')


def download_file(url: str, dest: Path) -> bool:
    """Download a URL to `dest`. Returns True on success."""
    try:
        resp = requests.get(url, timeout=10, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as exc:  # pragma: no cover – network errors are environment‑specific
        print(f'⚠️  Failed to download {url}: {exc}', file=sys.stderr)
        return False

# -------------------------------------------------------------------------
# Model discovery functions
# -------------------------------------------------------------------------

def fetch_ollama_models(base_url: str = 'http://localhost:11434') -> Set[str]:
    """Return a set of model IDs from a local Ollama daemon."""
    try:
        resp = requests.get(f'{base_url}/api/tags', timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {model['name'] for model in data.get('models', [])}
    except Exception as exc:  # pragma: no cover
        print(f'⚠️  Ollama query failed: {exc}', file=sys.stderr)
        return set()


def fetch_openai_models(api_key: str) -> Set[str]:
    """Return a set of model IDs from the official OpenAI endpoint."""
    headers = {'Authorization': f'Bearer {api_key}'}
    try:
        resp = requests.get('https://api.openai.com/v1/models', headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {m['id'] for m in data.get('data', [])}
    except Exception as exc:  # pragma: no cover
        print(f'⚠️  OpenAI query failed: {exc}', file=sys.stderr)
        return set()


def fetch_ollama_turbo_models(url: str, api_key: str = '') -> Set[str]:
    """
    Query an Ollama‑Turbo compatible endpoint. The endpoint follows the OpenAI
    `/v1/models` contract, so we can reuse the same parsing logic.
    """
    headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {m['id'] for m in data.get('data', [])}
    except Exception as exc:  # pragma: no cover
        print(f'⚠️  Ollama‑Turbo query failed: {exc}', file=sys.stderr)
        return set()

# -------------------------------------------------------------------------
# Icon resolution logic
# -------------------------------------------------------------------------


def resolve_icon_path(model_id: str, icon_dir: Path) -> Path:
    """
    Return the final path where the icon file should live.
    The script will attempt to download a provider‑specific image; if none
    can be found it will fallback to `default.png` placed by the user.
    """
    filename = f'{slugify(model_id)}.png'
    return icon_dir / filename


def download_hf_card_image(model_id: str, dest: Path) -> bool:
    """
    Try to pull the model card image from Hugging‑Face. The convention is:
    https://huggingface.co/<repo>/raw/main/card.png
    Many community models follow that layout.
    """
    # Heuristic: split on '/' and take the first two components as repo path.
    parts = model_id.split('/')
    if len(parts) < 2:
        return False
    repo = '/'.join(parts[:2])
    url = f'https://huggingface.co/{repo}/raw/main/card.png'
    return download_file(url, dest)


def fallback_provider_badge(model_id: str, dest: Path) -> bool:
    """
    If the model name contains a known provider token, use a small badge.
    This is optional; you can extend the mapping with your own URLs.
    """
    provider_assets = {
        'gpt-': 'https://raw.githubusercontent.com/openai/openai-python/master/assets/openai.png',
        'claude-': 'https://cdn.clarifai.com/clarifai-logo.png',
        # Add more providers as you wish...
    }
    for token, badge_url in provider_assets.items():
        if token in model_id.lower():
            return download_file(badge_url, dest)
    return False


def ensure_default_icon(icon_dir: Path) -> None:
    """
    Place a single generic placeholder if the user has not provided one.
    The UI will render this when a specific file is missing.
    """
    default_path = icon_dir / 'default.png'
    if default_path.is_file():
        return
    # Use a tiny built‑in 1×1 transparent PNG (base64 decoded) to avoid external fetch.
    transparent_png = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00'
        b'\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    default_path.write_bytes(transparent_png)

# -------------------------------------------------------------------------
# Main orchestration
# -------------------------------------------------------------------------


def build_icon_map(models: Set[str], icon_dir: Path) -> Dict[str, str]:
    """
    For every model ID generate a JSON entry pointing to the static asset.
    The UI expects a relative URL like `/icons/<filename>`.
    """
    mapping = {}
    for model in models:
        target = resolve_icon_path(model, icon_dir)
        if not target.is_file():
            # Try to fetch a HF card image first
            if download_hf_card_image(model, target):
                pass
            elif fallback_provider_badge(model, target):
                pass
            else:
                # No specific image – point at the generic fallback
                target = icon_dir / 'default.png'
        # The URL that the front‑end will request (relative to /public)
        rel_url = f'/icons/{target.name}'
        mapping[model] = rel_url
    return mapping


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Generate OpenWebUI model‑icon mapping automatically.'
    )
    parser.add_argument('--openai-key', help='OpenAI API key (env: OPENAI_API_KEY)')
    parser.add_argument('--ollama-url', default='http://localhost:11434',
                        help='Base URL for local Ollama daemon')
    parser.add_argument('--ollama-turbo-url',
                        help='Full URL to an Ollama‑Turbo /v1/models endpoint')
    parser.add_argument('--ollama-turbo-key',
                        help='API key for Ollama‑Turbo if required')
    parser.add_argument('--icon-dir', default='./public/icons',
                        help='Directory where PNG icons will be stored')
    parser.add_argument('--static-json', default='./public/icons/model-icons.json',
                        help='Path of the generated JSON mapping')
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    # Gather model IDs from every source the UI can talk to
    all_models: Set[str] = set()
    all_models.update(fetch_ollama_models(args.ollama_url))

    if args.openai_key or os.getenv('OPENAI_API_KEY'):
        api_key = args.openai_key or os.getenv('OPENAI_API_KEY')
        all_models.update(fetch_openai_models(api_key))

    if args.ollama_turbo_url:
        api_key = args.ollama_turbo_key or ''
        all_models.update(fetch_ollama_turbo_models(args.ollama_turbo_url, api_key))

    if not all_models:
        print('⚠️  No models discovered – exiting.', file=sys.stderr)
        sys.exit(1)

    icon_dir = Path(args.icon_dir).resolve()
    ensure_default_icon(icon_dir)

    mapping = build_icon_map(all_models, icon_dir)
    json_path = Path(args.static_json).resolve()
    safe_write_json(json_path, mapping)

    print(f'✅  Generated mapping for {len(mapping)} models → {json_path}')
    print('🔄  Restart OpenWebUI (docker compose restart open-webui) to see the changes.')


if __name__ == '__main__':
    main()
