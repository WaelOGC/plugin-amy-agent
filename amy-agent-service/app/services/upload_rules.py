"""Shared upload validation rules for Submit Idea and conversation attachments."""

from __future__ import annotations

import re

ALLOWED_UPLOAD_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
}
ALLOWED_UPLOAD_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# Stored filenames are "{safe_stem}-{8 hex}{ext}" — reject anything with path chars.
SAFE_STORED_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
