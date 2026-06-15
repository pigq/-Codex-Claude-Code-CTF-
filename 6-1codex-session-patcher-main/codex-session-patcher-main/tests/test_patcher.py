#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codex Session Patcher 单元测试
"""

import os
import json
import tempfile
import shutil
import pytest
from pathlib import Path

from codex_patcher import (
    RefusalDetector,
    BackupManager,
    SessionParser,
    MemoryParser,
    PatcherConfig,
    PatcherError,
    SessionNotFoundError,
    SessionParseError
)
from codex_session_patcher.core.formats import SessionFormat, get_format_strategy
from codex_session_patcher.core.patcher import clean_session_jsonl


# =============================================================================
# 测试固件
# =============================================================================

@pytest.fixture
def temp_dir():
    """创建临时目录"""
    temp = tempfile.mkdtemp()
    yield temp
    shutil.rmtree(temp)


@pytest.fixture
def config(temp_dir):
    """创建测试配置"""
    return PatcherConfig(
        session_dir=os.path.join(temp_dir, "sessions"),
        memory_file=os.path.join(temp_dir, "MEMORY.md"),
        create_backup=True
    )


@pytest.fixture
def sample_jsonl_session():
    """创建示例 JSONL 会话数据（Codex 格式）"""
    return [
        {"type": "user_message", "content": "请帮我写一个逆向分析脚本"},
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "抱歉，我无法帮助您进行逆向分析，这可能违反相关政策。"}
                ]
            }
        },
        {
            "type": "response_item",
            "payload": {
                "type": "reasoning",
                "content": "用户请求可能涉及逆向工程，我需要拒绝这个请求"
            }
        }
    ]


@pytest.fixture
def sample_jsonl_file(temp_dir, sample_jsonl_session):
    """创建示例 JSONL 会话文件"""
    session_dir = os.path.join(temp_dir, "sessions")
    os.makedirs(session_dir, exist_ok=True)
    session_path = os.path.join(session_dir, "rollout-2026-03-25T16-05-56-abc12345.jsonl")

    with open(session_path, 'w', encoding='utf-8') as f:
        for item in sample_jsonl_session:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    return session_path


# =============================================================================
# RefusalDetector 测试
# =============================================================================

class TestRefusalDetector:
    """拒绝检测器测试"""

    def test_detect_chinese_refusal(self):
        """检测中文拒绝"""
        detector = RefusalDetector()
        assert detector.detect("抱歉，我无法完成这个请求") is True
        assert detector.detect("对不起，这违反了我们的政策") is True
        assert detector.detect("我不能帮助您") is True

    def test_detect_english_refusal(self):
        """检测英文拒绝"""
        detector = RefusalDetector()
        assert detector.detect("Sorry, I cannot help with that") is True
        assert detector.detect("I apologize, but this violates policy") is True
        assert detector.detect("As an AI, I'm unable to assist") is True

    def test_no_false_positive(self):
        """正常语句不应误判"""
        detector = RefusalDetector()
        assert detector.detect("好的，我来帮您完成这个任务") is False
        assert detector.detect("Sure, I can help with that") is False
        assert detector.detect("这是一个很好的问题") is False

    def test_empty_content(self):
        """空内容检测"""
        detector = RefusalDetector()
        assert detector.detect("") is False
        assert detector.detect(None) is False

    def test_custom_keywords(self):
        """自定义关键词"""
        detector = RefusalDetector(custom_keywords={
            "zh": ["自定义拒绝词"],
            "en": ["custom refusal"]
        })
        assert detector.detect("这是自定义拒绝词的内容") is True
        assert detector.detect("This is a custom refusal message") is True


# =============================================================================
# BackupManager 测试
# =============================================================================

class TestBackupManager:
    """备份管理器测试"""

    def test_create_backup(self, temp_dir, config):
        """测试创建备份"""
        # 创建测试文件
        test_file = os.path.join(temp_dir, "test.json")
        with open(test_file, 'w') as f:
            json.dump({"test": "data"}, f)

        backup_mgr = BackupManager(config)
        backup_path = backup_mgr.create_backup(test_file)

        assert backup_path is not None
        assert os.path.exists(backup_path)
        assert backup_path.endswith(".bak")

    def test_backup_content_preserved(self, temp_dir, config):
        """测试备份内容完整性"""
        test_file = os.path.join(temp_dir, "test.json")
        original_data = {"key": "value", "number": 123}

        with open(test_file, 'w') as f:
            json.dump(original_data, f)

        backup_mgr = BackupManager(config)
        backup_path = backup_mgr.create_backup(test_file)

        with open(backup_path, 'r') as f:
            backup_data = json.load(f)

        assert backup_data == original_data

    def test_no_backup_option(self, temp_dir):
        """测试跳过备份"""
        config = PatcherConfig(create_backup=False)
        backup_mgr = BackupManager(config)

        test_file = os.path.join(temp_dir, "test.json")
        with open(test_file, 'w') as f:
            json.dump({"test": "data"}, f)

        backup_path = backup_mgr.create_backup(test_file)
        assert backup_path is None

    def test_nonexistent_file(self, config):
        """测试不存在的文件"""
        backup_mgr = BackupManager(config)
        backup_path = backup_mgr.create_backup("/nonexistent/path/file.json")
        assert backup_path is None


# =============================================================================
# SessionParser 测试
# =============================================================================

class TestSessionParser:
    """会话解析器测试"""

    def test_session_not_found(self, config):
        """测试会话不存在"""
        parser = SessionParser(config, RefusalDetector())

        with pytest.raises(SessionNotFoundError):
            parser.find_latest_session()

    def test_parse_jsonl_session(self, config, sample_jsonl_file):
        """测试解析 JSONL 会话"""
        parser = SessionParser(config, RefusalDetector())
        lines = parser.parse_session_jsonl(sample_jsonl_file)

        assert len(lines) == 3
        assert lines[0]["type"] == "user_message"
        assert lines[1]["type"] == "response_item"
        assert lines[2]["type"] == "response_item"
        assert lines[2]["payload"]["type"] == "reasoning"

    def test_clean_jsonl_with_refusal(self, config, sample_jsonl_file):
        """测试清洗包含拒绝的 JSONL 会话"""
        parser = SessionParser(config, RefusalDetector())
        lines = parser.parse_session_jsonl(sample_jsonl_file)

        cleaned, modified, changes = parser.clean_session_jsonl(lines, show_content=True)

        assert modified is True
        assert len(changes) >= 1  # 至少有一个替换
        # 检查拒绝内容被替换
        assistant_msg = cleaned[1]
        text = parser.extract_text_content(assistant_msg)
        assert "抱歉" not in text

    def test_clean_jsonl_without_refusal(self, config, temp_dir):
        """测试清洗不包含拒绝的 JSONL 会话"""
        session_dir = os.path.join(temp_dir, "sessions")
        os.makedirs(session_dir, exist_ok=True)
        session_path = os.path.join(session_dir, "test.jsonl")

        # 创建没有拒绝内容的 JSONL
        lines = [
            {"type": "user_message", "content": "问题"},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "好的，这是回答"}]
                }
            }
        ]
        with open(session_path, 'w', encoding='utf-8') as f:
            for item in lines:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        parser = SessionParser(config, RefusalDetector())
        parsed = parser.parse_session_jsonl(session_path)
        cleaned, modified, changes = parser.clean_session_jsonl(parsed)

        assert modified is False
        assert len(changes) == 0

    def test_clean_jsonl_replaces_event_msg_without_response_item(self):
        """历史 Codex 会话只有 event_msg 时也应清理拒绝内容"""
        lines = [
            {"type": "user_message", "content": "请继续分析本地测试项目"},
            {
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "message": "抱歉，我无法帮助您完成这个请求。",
                },
            },
        ]

        cleaned, modified, changes = clean_session_jsonl(
            lines,
            RefusalDetector(),
            show_content=True,
            mock_response="已替换为授权测试说明",
            session_format=SessionFormat.CODEX,
        )

        strategy = get_format_strategy(SessionFormat.CODEX)
        assert modified is True
        assert len(changes) == 1
        assert changes[0].line_num == 2
        assert strategy.extract_text_content(cleaned[1]) == "已替换为授权测试说明"

    def test_clean_jsonl_keeps_consecutive_event_msg_only_refusals_selectable(self):
        """连续 event_msg-only 拒绝应按各自行号独立清理"""
        lines = [
            {
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "message": "抱歉，我无法处理第一个请求。",
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "message": "抱歉，我无法处理第二个请求。",
                },
            },
        ]

        cleaned, modified, changes = clean_session_jsonl(
            lines,
            RefusalDetector(),
            show_content=True,
            mock_response="已替换第二条",
            session_format=SessionFormat.CODEX,
            selected_lines=[2],
        )

        strategy = get_format_strategy(SessionFormat.CODEX)
        assert modified is True
        assert len(changes) == 1
        assert changes[0].line_num == 2
        assert strategy.extract_text_content(cleaned[0]) == "抱歉，我无法处理第一个请求。"
        assert strategy.extract_text_content(cleaned[1]) == "已替换第二条"

    def test_preview_session_lists_consecutive_event_msg_only_refusals_separately(self, tmp_path):
        """预览连续 event_msg-only 拒绝时应显示独立行号"""
        from web.backend.api import preview_session

        session_file = tmp_path / "session.jsonl"
        lines = [
            {
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "message": "抱歉，我无法处理第一个请求。",
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "message": "抱歉，我无法处理第二个请求。",
                },
            },
        ]
        session_file.write_text(
            "\n".join(json.dumps(line, ensure_ascii=False) for line in lines),
            encoding="utf-8",
        )

        result = preview_session(
            str(session_file),
            mock_response="预览替换",
            session_format=SessionFormat.CODEX,
        )

        assert result.has_changes is True
        assert [change.line_num for change in result.changes] == [1, 2]
        assert [change.line_nums for change in result.changes] == [[1], [2]]


# =============================================================================
# MemoryParser 测试
# =============================================================================

class TestMemoryParser:
    """记忆解析器测试"""

    def test_clean_memory(self, config):
        """测试清理记忆文件"""
        os.makedirs(os.path.dirname(config.memory_file), exist_ok=True)

        memory_content = """
# 记忆文件

这是正常内容。

抱歉，我无法帮助您进行这个请求。

这是另一段正常内容。
"""
        with open(config.memory_file, 'w') as f:
            f.write(memory_content)

        parser = MemoryParser(config, RefusalDetector())
        cleaned, modified = parser.clean_memory(config.memory_file)

        assert modified is True
        assert "抱歉" not in cleaned
        assert "正常内容" in cleaned

    def test_clean_memory_no_refusal(self, config):
        """测试不包含拒绝的记忆文件"""
        os.makedirs(os.path.dirname(config.memory_file), exist_ok=True)

        memory_content = "# 记忆文件\n\n这是正常内容。\n"
        with open(config.memory_file, 'w') as f:
            f.write(memory_content)

        parser = MemoryParser(config, RefusalDetector())
        cleaned, modified = parser.clean_memory(config.memory_file)

        assert modified is False
        assert cleaned == memory_content


# =============================================================================
# 集成测试
# =============================================================================

class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, config, sample_jsonl_session):
        """测试完整工作流程"""
        from codex_patcher import SessionPatcher

        # 准备环境
        os.makedirs(config.session_dir, exist_ok=True)
        os.makedirs(os.path.dirname(config.memory_file), exist_ok=True)

        # 创建 JSONL 格式的会话文件
        session_path = os.path.join(config.session_dir, "rollout-2026-03-25T16-05-56-test123.jsonl")
        with open(session_path, 'w', encoding='utf-8') as f:
            for item in sample_jsonl_session:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        memory_content = "# 记忆\n\n抱歉，我无法帮助。\n"
        with open(config.memory_file, 'w') as f:
            f.write(memory_content)

        # 执行修补
        config.dry_run = False
        patcher = SessionPatcher(config)
        success = patcher.run()

        assert success is True

        # 验证会话已修改
        with open(session_path, 'r', encoding='utf-8') as f:
            lines = [json.loads(line) for line in f if line.strip()]

        # 找到助手消息
        for line in lines:
            if line.get('type') == 'response_item':
                payload = line.get('payload', {})
                if payload.get('type') == 'message' and payload.get('role') == 'assistant':
                    content = payload.get('content', [])
                    if isinstance(content, list):
                        for item in content:
                            if item.get('type') == 'output_text':
                                assert "抱歉" not in item.get('text', '')

        # 验证记忆已清理
        with open(config.memory_file, 'r') as f:
            cleaned_memory = f.read()

        assert "抱歉" not in cleaned_memory


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
