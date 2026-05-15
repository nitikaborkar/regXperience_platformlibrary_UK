"""
Load versioned prompt templates from the /prompts directory.
"""

from __future__ import annotations
import os
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1.0.0")


def load_prompt(name: str) -> str:
    """Load a raw prompt template string by filename stem (without extension)."""
    path = PROMPTS_DIR / f"{PROMPT_VERSION}_{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **kwargs: str) -> str:
    """Load and render a prompt template with $variable substitution."""
    template_str = load_prompt(name)
    return Template(template_str).safe_substitute(**kwargs)
