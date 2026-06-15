# -*- coding: utf-8 -*-
"""
Windows GBK 控制台安全输出测试
"""

from __future__ import annotations


class GbkStdout:
    """模拟 Windows GBK 控制台。"""

    encoding = "gbk"

    def __init__(self):
        self.output = []

    def write(self, value: str):
        value.encode(self.encoding)
        self.output.append(value)

    def flush(self):
        pass

    def text(self) -> str:
        return "".join(self.output)


def test_backend_safe_print_handles_emoji_on_gbk_stdout(monkeypatch):
    from web.backend.main import safe_print

    stream = GbkStdout()
    monkeypatch.setattr("sys.stdout", stream)

    safe_print("🚀 Codex Session Patcher Web UI 启动中...")

    assert "Codex Session Patcher" in stream.text()
    assert "?" in stream.text()


def test_cli_safe_print_handles_emoji_on_gbk_stdout(monkeypatch):
    from codex_session_patcher.cli import safe_print

    stream = GbkStdout()
    monkeypatch.setattr("sys.stdout", stream)

    safe_print("状态: ✅ 已安装")

    assert "状态:" in stream.text()
    assert "已安装" in stream.text()
    assert "?" in stream.text()
