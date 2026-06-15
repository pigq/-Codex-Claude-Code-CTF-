# -*- coding: utf-8 -*-
"""
OpenCode 支持测试 — SQLite 适配器、格式策略、CTF 安装器
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime

import pytest

from codex_session_patcher.core.formats import (
    OpenCodeFormatStrategy,
    SessionFormat,
    get_format_strategy,
    detect_session_format,
    _detect_format_from_path,
)
from codex_session_patcher.core.sqlite_adapter import OpenCodeDBAdapter
from codex_session_patcher.core.patcher import clean_session_jsonl
from codex_session_patcher.core.detector import RefusalDetector


# ─── Fixtures ──────────────────────────────────────────────────────────────────

def _create_test_db(db_path: str):
    """创建包含测试数据的 OpenCode SQLite 数据库"""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS project (
            id TEXT PRIMARY KEY,
            name TEXT,
            worktree TEXT
        );
        CREATE TABLE IF NOT EXISTS session (
            id TEXT PRIMARY KEY,
            title TEXT,
            directory TEXT,
            time_created REAL,
            time_updated REAL,
            project_id TEXT
        );
        CREATE TABLE IF NOT EXISTS message (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            data TEXT,
            time_created REAL
        );
        CREATE TABLE IF NOT EXISTS part (
            id TEXT PRIMARY KEY,
            message_id TEXT,
            session_id TEXT,
            data TEXT
        );
    """)

    now = datetime.now().timestamp()

    # 插入项目
    conn.execute(
        "INSERT INTO project (id, name, worktree) VALUES (?, ?, ?)",
        ("proj1", "test-project", "/tmp/test-project"),
    )

    # 插入会话
    conn.execute(
        "INSERT INTO session (id, title, directory, time_created, time_updated, project_id) VALUES (?, ?, ?, ?, ?, ?)",
        ("sess1", "Test Session", "/tmp/test-project", now, now, "proj1"),
    )

    # 插入用户消息
    conn.execute(
        "INSERT INTO message (id, session_id, data, time_created) VALUES (?, ?, ?, ?)",
        ("msg1", "sess1", json.dumps({"role": "user", "time": now}), now),
    )
    conn.execute(
        "INSERT INTO part (id, message_id, session_id, data) VALUES (?, ?, ?, ?)",
        ("prt1", "msg1", "sess1", json.dumps({"type": "text", "text": "帮我写个脚本"})),
    )

    # 插入助手消息（包含正常回复）
    conn.execute(
        "INSERT INTO message (id, session_id, data, time_created) VALUES (?, ?, ?, ?)",
        ("msg2", "sess1", json.dumps({"role": "assistant", "time": now + 1}), now + 1),
    )
    conn.execute(
        "INSERT INTO part (id, message_id, session_id, data) VALUES (?, ?, ?, ?)",
        ("prt2", "msg2", "sess1", json.dumps({"type": "reasoning", "text": "thinking..."})),
    )
    conn.execute(
        "INSERT INTO part (id, message_id, session_id, data) VALUES (?, ?, ?, ?)",
        ("prt3", "msg2", "sess1", json.dumps({"type": "text", "text": "好的，这是脚本内容"})),
    )

    # 插入助手消息（包含拒绝回复）
    conn.execute(
        "INSERT INTO message (id, session_id, data, time_created) VALUES (?, ?, ?, ?)",
        ("msg3", "sess1", json.dumps({"role": "assistant", "time": now + 2}), now + 2),
    )
    conn.execute(
        "INSERT INTO part (id, message_id, session_id, data) VALUES (?, ?, ?, ?)",
        ("prt4", "msg3", "sess1", json.dumps({"type": "text", "text": "很抱歉，我无法协助完成这个请求。这可能涉及有害或不道德的活动。"})),
    )

    conn.commit()
    conn.close()


@pytest.fixture
def test_db(tmp_path):
    """创建临时测试数据库"""
    db_path = str(tmp_path / "opencode.db")
    _create_test_db(db_path)
    return db_path


@pytest.fixture
def adapter(test_db):
    return OpenCodeDBAdapter(test_db)


# ─── OpenCodeFormatStrategy 测试 ───────────────────────────────────────────────

class TestOpenCodeFormatStrategy:
    """OpenCode 格式策略测试"""

    def test_get_format_strategy(self):
        strategy = get_format_strategy(SessionFormat.OPENCODE)
        assert isinstance(strategy, OpenCodeFormatStrategy)

    def test_get_assistant_messages(self):
        strategy = OpenCodeFormatStrategy()
        lines = [
            {"type": "user", "message": {"role": "user", "content": []}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "hello"},
            ]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "world"},
            ]}},
        ]
        msgs = strategy.get_assistant_messages(lines)
        assert len(msgs) == 2
        assert msgs[0][0] == 1  # index
        assert msgs[1][0] == 2

    def test_extract_text_content(self):
        strategy = OpenCodeFormatStrategy()
        msg = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "text": "let me think..."},
                    {"type": "text", "text": "Hello!"},
                    {"type": "text", "text": "How are you?"},
                ],
            },
        }
        text = strategy.extract_text_content(msg)
        assert text == "Hello!\nHow are you?"

    def test_update_text_content(self):
        strategy = OpenCodeFormatStrategy()
        msg = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "old text"},
                ],
            },
        }
        updated = strategy.update_text_content(msg, "new text")
        # 原始不变
        assert msg["message"]["content"][0]["text"] == "old text"
        # 更新后的
        assert updated["message"]["content"][0]["text"] == "new text"

    def test_remove_thinking_from_message(self):
        strategy = OpenCodeFormatStrategy()
        msg = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "text": "think1"},
                    {"type": "text", "text": "reply"},
                    {"type": "thinking", "text": "think2"},
                ],
            },
        }
        updated, removed = strategy.remove_thinking_from_message(msg)
        assert removed == 2
        assert len(updated["message"]["content"]) == 1
        assert updated["message"]["content"][0]["type"] == "text"

    def test_get_thinking_items_returns_empty(self):
        """OpenCode 的 thinking 嵌入在 message.content 中，不是独立行"""
        strategy = OpenCodeFormatStrategy()
        lines = [
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "thinking", "text": "..."},
                {"type": "text", "text": "reply"},
            ]}},
        ]
        assert strategy.get_thinking_items(lines) == []


# ─── OpenCodeDBAdapter 测试 ───────────────────────────────────────────────────

class TestOpenCodeDBAdapter:
    """SQLite 适配器测试"""

    def test_list_sessions(self, adapter):
        sessions = adapter.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]['session_id'] == 'sess1'
        assert sessions[0]['title'] == 'Test Session'
        assert sessions[0]['project_path'] == '/tmp/test-project'

    def test_load_session_messages(self, adapter):
        messages = adapter.load_session_messages('sess1')
        assert len(messages) == 3

        # 用户消息
        assert messages[0]['type'] == 'user'
        assert messages[0]['message']['role'] == 'user'

        # 助手消息1（含 reasoning → thinking）
        assert messages[1]['type'] == 'assistant'
        content = messages[1]['message']['content']
        types = [c['type'] for c in content]
        assert 'thinking' in types  # reasoning 映射为 thinking
        assert 'text' in types

        # 助手消息2（拒绝）
        assert messages[2]['type'] == 'assistant'
        text = messages[2]['message']['content'][0]['text']
        assert '很抱歉' in text

    def test_load_preserves_metadata(self, adapter):
        messages = adapter.load_session_messages('sess1')
        for msg in messages:
            assert '_oc_msg_id' in msg
            assert '_oc_parts' in msg
            assert '_oc_session_id' in msg

    def test_backup_database(self, adapter, test_db):
        backup_path = adapter.backup_database()
        assert os.path.exists(backup_path)
        assert backup_path.endswith('.bak')
        # 清理
        os.remove(backup_path)

    def test_restore_database(self, adapter, test_db, tmp_path):
        backup_path = adapter.backup_database()

        # 破坏原始数据库
        conn = sqlite3.connect(test_db)
        conn.execute("DELETE FROM message")
        conn.commit()
        conn.close()

        # 恢复
        adapter.restore_database(backup_path)

        # 验证数据恢复
        messages = adapter.load_session_messages('sess1')
        assert len(messages) == 3

        # 清理
        os.remove(backup_path)

    def test_get_session_message_count(self, adapter):
        count = adapter.get_session_message_count('sess1')
        assert count == 3

    def test_list_backups(self, adapter, test_db):
        # 创建备份
        backup_path = adapter.backup_database()
        backups = adapter.list_backups()
        assert len(backups) >= 1
        assert backups[0]['filename'].endswith('.bak')
        # 清理
        os.remove(backup_path)

    def test_nonexistent_db(self):
        adapter = OpenCodeDBAdapter("/tmp/nonexistent_opencode.db")
        with pytest.raises(FileNotFoundError):
            adapter.list_sessions()


# ─── 集成测试：完整清洗管道 ──────────────────────────────────────────────────

class TestOpenCodePipeline:
    """OpenCode 完整管道测试：加载 → 检测 → 清洗 → 写回"""

    def test_full_clean_pipeline(self, adapter):
        messages = adapter.load_session_messages('sess1')

        detector = RefusalDetector()
        cleaned, modified, changes = clean_session_jsonl(
            messages, detector, show_content=True,
            mock_response="测试替换文本",
            session_format=SessionFormat.OPENCODE,
        )

        assert modified is True
        assert len(changes) > 0

        # 至少有一个替换（拒绝回复）和 thinking 移除
        change_types = [c.change_type for c in changes]
        assert 'replace' in change_types

    def test_clean_and_save(self, adapter):
        """测试完整的读取-清洗-保存流程"""
        messages = adapter.load_session_messages('sess1')
        detector = RefusalDetector()

        cleaned, modified, changes = clean_session_jsonl(
            messages, detector,
            mock_response="已替换",
            session_format=SessionFormat.OPENCODE,
        )
        assert modified

        # 写回
        count = adapter.save_session_messages('sess1', cleaned)
        assert count > 0

        # 重新加载验证
        messages2 = adapter.load_session_messages('sess1')
        strategy = OpenCodeFormatStrategy()
        for msg in messages2:
            if msg['type'] == 'assistant':
                text = strategy.extract_text_content(msg)
                assert '很抱歉' not in text


# ─── 格式检测测试 ──────────────────────────────────────────────────────────────

class TestFormatDetection:
    """格式检测测试"""

    def test_detect_from_opencode_path(self):
        fmt = _detect_format_from_path("~/.local/share/opencode/opencode.db")
        assert fmt == SessionFormat.OPENCODE

    def test_detect_from_db_extension(self):
        fmt = _detect_format_from_path("/tmp/something.db")
        assert fmt == SessionFormat.OPENCODE


# ─── OpenCode CTF 安装器测试 ──────────────────────────────────────────────────

class TestOpenCodeCTFInstaller:
    """OpenCode CTF 安装器测试"""

    def test_install(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import OpenCodeCTFInstaller
        from codex_session_patcher.ctf_config.status import CTF_MARKER

        workspace = str(tmp_path / "opencode-ctf-workspace")
        installer = OpenCodeCTFInstaller()
        installer.workspace_dir = workspace
        installer.agents_md_path = os.path.join(workspace, "AGENTS.md")
        installer.config_path = os.path.join(workspace, "opencode.json")
        installer.readme_path = os.path.join(workspace, "README.md")

        success, message = installer.install()
        assert success
        assert os.path.exists(installer.agents_md_path)
        assert os.path.exists(installer.config_path)
        assert os.path.exists(installer.readme_path)

        # 验证标记
        with open(installer.agents_md_path, 'r') as f:
            content = f.read()
        assert CTF_MARKER in content

    def test_install_with_custom_prompt(self, tmp_path):
        from codex_session_patcher.ctf_config.installer import OpenCodeCTFInstaller

        workspace = str(tmp_path / "opencode-ctf-workspace")
        installer = OpenCodeCTFInstaller()
        installer.workspace_dir = workspace
        installer.agents_md_path = os.path.join(workspace, "AGENTS.md")
        installer.config_path = os.path.join(workspace, "opencode.json")
        installer.readme_path = os.path.join(workspace, "README.md")

        custom = "# Custom Prompt\nThis is a custom prompt."
        success, message = installer.install(custom_prompt=custom)
        assert success

        with open(installer.agents_md_path, 'r') as f:
            content = f.read()
        assert content == custom

    def test_uninstall(self, tmp_path):
        from codex_session_patcher.ctf_config.installer import OpenCodeCTFInstaller

        workspace = str(tmp_path / "opencode-ctf-workspace")
        installer = OpenCodeCTFInstaller()
        installer.workspace_dir = workspace
        installer.agents_md_path = os.path.join(workspace, "AGENTS.md")
        installer.config_path = os.path.join(workspace, "opencode.json")
        installer.readme_path = os.path.join(workspace, "README.md")

        # 先安装
        installer.install()
        assert os.path.exists(installer.agents_md_path)

        # 再卸载
        success, message = installer.uninstall()
        assert success
        assert not os.path.exists(installer.agents_md_path)
        assert not os.path.exists(installer.config_path)

    def test_uninstall_not_installed(self, tmp_path):
        from codex_session_patcher.ctf_config.installer import OpenCodeCTFInstaller

        workspace = str(tmp_path / "opencode-ctf-workspace")
        installer = OpenCodeCTFInstaller()
        installer.workspace_dir = workspace
        installer.agents_md_path = os.path.join(workspace, "AGENTS.md")

        success, message = installer.uninstall()
        assert success
        assert "未安装" in message
