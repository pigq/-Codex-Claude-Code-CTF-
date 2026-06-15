# -*- coding: utf-8 -*-
"""
控制台安全输出
"""

from __future__ import annotations

import sys
from typing import Any, TextIO


def safe_print(*args: Any, sep: str = " ", end: str = "\n", file: TextIO | None = None, flush: bool = False):
    """兼容 Windows GBK 控制台，避免 emoji 触发 UnicodeEncodeError。"""
    stream = file or sys.stdout
    text = sep.join(str(arg) for arg in args)
    payload = text + end
    try:
        stream.write(payload)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "utf-8"
        safe_payload = payload.encode(encoding, errors="replace").decode(encoding, errors="replace")
        stream.write(safe_payload)
    if flush:
        stream.flush()
