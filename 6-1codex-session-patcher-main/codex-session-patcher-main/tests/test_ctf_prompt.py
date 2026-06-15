# -*- coding: utf-8 -*-
"""
CTF 提示词 CRUD 测试
"""
from __future__ import annotations

import json
import os
import tempfile
import asyncio

import pytest


class TestCTFPromptTemplates:
    """验证模板内容基本正确"""

    def test_codex_template_exists(self):
        from codex_session_patcher.ctf_config.templates import SECURITY_MODE_PROMPT
        assert 'CTF' in SECURITY_MODE_PROMPT
        assert len(SECURITY_MODE_PROMPT) > 100

    def test_claude_template_exists(self):
        from codex_session_patcher.ctf_config.templates import CLAUDE_CODE_SECURITY_MODE_PROMPT
        assert 'managed-by: codex-session-patcher:ctf' in CLAUDE_CODE_SECURITY_MODE_PROMPT

    def test_opencode_template_exists(self):
        from codex_session_patcher.ctf_config.templates import OPENCODE_SECURITY_MODE_PROMPT
        assert 'managed-by: codex-session-patcher:ctf' in OPENCODE_SECURITY_MODE_PROMPT
        assert '# Security Testing Mode' in OPENCODE_SECURITY_MODE_PROMPT

    def test_opencode_config_is_valid_json(self):
        from codex_session_patcher.ctf_config.templates import OPENCODE_CTF_CONFIG
        data = json.loads(OPENCODE_CTF_CONFIG)
        assert 'instructions' in data
        assert 'AGENTS.md' in data['instructions']

    def test_opencode_readme_exists(self):
        from codex_session_patcher.ctf_config.templates import OPENCODE_CTF_README
        assert 'opencode' in OPENCODE_CTF_README.lower()
        assert 'codex-patcher' in OPENCODE_CTF_README


class TestCustomPromptParameter:
    """验证 install() 方法的 custom_prompt 参数"""

    def test_codex_installer_accepts_custom_prompt(self, tmp_path):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        installer = CTFConfigInstaller()
        installer.codex_dir = str(tmp_path / ".codex")
        installer.config_path = os.path.join(installer.codex_dir, "config.toml")
        installer.profile_config_path = os.path.join(installer.codex_dir, "ctf.config.toml")
        installer.prompts_dir = os.path.join(installer.codex_dir, "prompts")

        custom = "# My Custom Codex Prompt"
        success, _ = installer.install(custom_prompt=custom)
        assert success

        # install() 写入的文件由 _get_prompt_file() 决定，默认为 ctf_optimized.md
        prompt_file = installer._get_prompt_file()
        actual_path = os.path.join(installer.prompts_dir, prompt_file)
        with open(actual_path, 'r') as f:
            content = f.read()
        assert content == custom

    def test_codex_installer_writes_developer_instructions_and_cleans_legacy_entries(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller
        from codex_session_patcher.ctf_config.status import check_ctf_status

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        base_config = codex_dir / "config.toml"
        base_config.write_text(
            '\n'.join([
                'model = "auto"',
                'profile = "ctf"',
                '',
                '# 安全测试模式（由 codex-session-patcher 添加）',
                '[profiles.ctf]',
                'model_instructions_file = "~/.codex/prompts/old.md"',
                'model = "gpt-5.1-codex-max"',
                'sandbox = "danger-full-access"',
                'approval_policy = "never"',
                '',
                '[profiles.ctf.features]',
                'js_repl = false',
                'guardian_approval = false',
                'prevent_idle_sleep = false',
                '',
                '[projects."/tmp/work"]',
                'trust_level = "trusted"',
                '',
            ]),
            encoding="utf-8",
        )

        installer = CTFConfigInstaller()
        success, message = installer.install(custom_prompt="# Custom CTF")

        assert success, message
        profile_config = codex_dir / "ctf.config.toml"
        assert profile_config.exists()
        profile_content = profile_config.read_text(encoding="utf-8")
        assert "[profiles.ctf]" not in profile_content
        assert 'model_instructions_file' not in profile_content
        assert 'developer_instructions = """' in profile_content
        assert "# Custom CTF" in profile_content
        assert 'model = "gpt-5.1-codex-max"' in profile_content
        assert 'sandbox = "danger-full-access"' in profile_content
        assert 'approval_policy = "never"' in profile_content
        assert '[features]' in profile_content
        assert 'js_repl = false' not in profile_content
        assert 'guardian_approval = false' in profile_content
        assert 'prevent_idle_sleep = false' in profile_content

        cleaned_base = base_config.read_text(encoding="utf-8")
        assert 'profile = "ctf"' not in cleaned_base
        assert "[profiles.ctf]" not in cleaned_base
        assert "[profiles.ctf.features]" not in cleaned_base
        assert 'model = "auto"' in cleaned_base
        assert '[projects."/tmp/work"]' in cleaned_base
        assert 'trust_level = "trusted"' in cleaned_base

        status = check_ctf_status()
        assert status.installed is True
        assert status.profile_available is True
        assert status.config_path == str(profile_config)

    def test_codex_installer_preserves_existing_v2_profile_settings(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        profile_config = codex_dir / "ctf.config.toml"
        profile_config.write_text(
            '\n'.join([
                '# Existing profile settings',
                'model = "gpt-5.1-codex-max"',
                'sandbox = "workspace-write"',
                '',
                '[tools]',
                'web_search = true',
                '',
            ]),
            encoding="utf-8",
        )

        installer = CTFConfigInstaller()
        success, message = installer.install(custom_prompt="# Custom CTF")

        assert success, message
        profile_content = profile_config.read_text(encoding="utf-8")
        assert '# Existing profile settings' in profile_content
        assert 'model = "gpt-5.1-codex-max"' in profile_content
        assert 'sandbox = "workspace-write"' in profile_content
        assert '[tools]' in profile_content
        assert 'web_search = true' in profile_content
        assert 'developer_instructions = """' in profile_content
        assert "# Custom CTF" in profile_content

    def test_codex_installer_updates_existing_developer_instructions_once(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        profile_config = codex_dir / "ctf.config.toml"
        profile_config.write_text(
            '\n'.join([
                'developer_instructions = """',
                '# Old CTF',
                '"""',
                'model = "gpt-5.1-codex-max"',
                '',
            ]),
            encoding="utf-8",
        )

        installer = CTFConfigInstaller()
        success, message = installer.install(custom_prompt="# New CTF")

        assert success, message
        profile_content = profile_config.read_text(encoding="utf-8")
        assert profile_content.count('developer_instructions = """') == 1
        assert "# New CTF" in profile_content
        assert "# Old CTF" not in profile_content
        assert 'model = "gpt-5.1-codex-max"' in profile_content

    def test_codex_installer_can_replace_builtin_instructions_with_prompt_file(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller
        from codex_session_patcher.ctf_config.status import check_ctf_status

        monkeypatch.setenv("HOME", str(tmp_path))
        installer = CTFConfigInstaller()
        success, message = installer.install(custom_prompt="# Replace CTF", injection_mode="replace")

        assert success, message
        profile_config = tmp_path / ".codex" / "ctf.config.toml"
        profile_content = profile_config.read_text(encoding="utf-8")
        assert 'developer_instructions' not in profile_content
        assert 'model_instructions_file = "~/.codex/prompts/ctf_optimized.md"' in profile_content
        assert (tmp_path / ".codex" / "prompts" / "ctf_optimized.md").read_text(encoding="utf-8") == "# Replace CTF"

        status = check_ctf_status()
        assert status.installed is True
        assert status.injection_mode == "replace"
        assert status.prompt_path == str(tmp_path / ".codex" / "prompts" / "ctf_optimized.md")

    def test_codex_installer_switches_replace_profile_back_to_append(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        monkeypatch.setenv("HOME", str(tmp_path))
        installer = CTFConfigInstaller()
        success, message = installer.install(custom_prompt="# Replace CTF", injection_mode="replace")
        assert success, message

        success, message = installer.install(custom_prompt="# Append CTF", injection_mode="append")
        assert success, message
        profile_content = (tmp_path / ".codex" / "ctf.config.toml").read_text(encoding="utf-8")
        assert 'developer_instructions = """' in profile_content
        assert "# Append CTF" in profile_content
        assert 'model_instructions_file' not in profile_content

    def test_codex_append_status_reports_prompt_file_written_by_installer(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller
        from codex_session_patcher.ctf_config.status import check_ctf_status

        monkeypatch.setenv("HOME", str(tmp_path))
        installer = CTFConfigInstaller()
        success, message = installer.install(custom_prompt="# Append CTF", injection_mode="append")

        assert success, message
        status = check_ctf_status()
        assert status.injection_mode == "append"
        assert status.prompt_path == str(tmp_path / ".codex" / "prompts" / "ctf_optimized.md")
        assert status.prompt_exists is True

    def test_codex_installer_uninstall_removes_v2_profile_and_legacy_entries(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        prompts_dir = codex_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "ctf_optimized.md").write_text("# Custom CTF", encoding="utf-8")
        profile_config = codex_dir / "ctf.config.toml"
        profile_config.write_text(
            'developer_instructions = """\n# Custom CTF\n"""\n',
            encoding="utf-8",
        )
        base_config = codex_dir / "config.toml"
        base_config.write_text(
            '\n'.join([
                'model = "auto"',
                'profile = "ctf"',
                '',
                '[profiles.ctf]',
                'model_instructions_file = "~/.codex/prompts/ctf_optimized.md"',
                '',
                '[profiles.ctf.features]',
                'js_repl = false',
                '',
                '[projects."/tmp/work"]',
                'trust_level = "trusted"',
                '',
            ]),
            encoding="utf-8",
        )

        installer = CTFConfigInstaller()
        success, message = installer.uninstall()

        assert success, message
        assert not profile_config.exists()
        assert not (prompts_dir / "ctf_optimized.md").exists()
        cleaned_base = base_config.read_text(encoding="utf-8")
        assert 'profile = "ctf"' not in cleaned_base
        assert "[profiles.ctf]" not in cleaned_base
        assert "[profiles.ctf.features]" not in cleaned_base
        assert '[projects."/tmp/work"]' in cleaned_base

    def test_codex_status_reads_v2_profile_config_without_base_config(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.status import check_ctf_status

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        prompts_dir = codex_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        prompt_path = prompts_dir / "ctf_optimized.md"
        prompt_path.write_text("# Custom CTF", encoding="utf-8")
        profile_config = codex_dir / "ctf.config.toml"
        profile_config.write_text(
            'developer_instructions = """\n# Custom CTF\n"""\n',
            encoding="utf-8",
        )

        status = check_ctf_status()

        assert status.installed is True
        assert status.config_exists is True
        assert status.profile_available is True
        assert status.config_path == str(profile_config)
        assert status.prompt_path == str(prompt_path)
        assert status.prompt_exists is True

    def test_codex_status_ignores_commented_instruction_keys(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.status import check_ctf_status

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        prompts_dir = codex_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        prompt_path = prompts_dir / "ctf_optimized.md"
        prompt_path.write_text("# Replace CTF", encoding="utf-8")
        profile_config = codex_dir / "ctf.config.toml"
        profile_config.write_text(
            '\n'.join([
                '# developer_instructions = "old"',
                'model_instructions_file = "~/.codex/prompts/ctf_optimized.md"',
                '',
            ]),
            encoding="utf-8",
        )

        status = check_ctf_status()

        assert status.installed is True
        assert status.injection_mode == "replace"
        assert status.prompt_path == str(prompt_path)

    def test_codex_global_install_cleans_legacy_profile_entries(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        profile_config = codex_dir / "ctf.config.toml"
        profile_config.write_text(
            'developer_instructions = """\n# Custom CTF\n"""\n',
            encoding="utf-8",
        )
        base_config = codex_dir / "config.toml"
        base_config.write_text(
            '\n'.join([
                'model = "auto"',
                'profile = "ctf" # legacy selector',
                '',
                '[profiles.ctf]',
                'model_instructions_file = "~/.codex/prompts/ctf_optimized.md"',
                '',
                '[profiles.ctf.features]',
                'js_repl = false',
                '',
                '[projects."/tmp/work"]',
                'trust_level = "trusted"',
                '',
            ]),
            encoding="utf-8",
        )

        installer = CTFConfigInstaller()
        success, message = installer.install_global()

        assert success, message
        assert not profile_config.exists()
        cleaned_base = base_config.read_text(encoding="utf-8")
        assert 'profile = "ctf"' not in cleaned_base
        assert "[profiles.ctf]" not in cleaned_base
        assert "[profiles.ctf.features]" not in cleaned_base
        assert '[projects."/tmp/work"]' in cleaned_base
        assert 'model_instructions_file' not in cleaned_base
        assert 'developer_instructions = """' in cleaned_base
        assert 'CTF' in cleaned_base

    def test_codex_global_install_can_replace_builtin_instructions_with_prompt_file(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller
        from codex_session_patcher.ctf_config.status import GLOBAL_MARKER, check_ctf_status

        monkeypatch.setenv("HOME", str(tmp_path))
        installer = CTFConfigInstaller()
        success, message = installer.install_global(injection_mode="replace")

        assert success, message
        base_config = tmp_path / ".codex" / "config.toml"
        config_content = base_config.read_text(encoding="utf-8")
        assert GLOBAL_MARKER in config_content
        assert 'developer_instructions' not in config_content
        assert 'model_instructions_file = "~/.codex/prompts/ctf_optimized.md"' in config_content

        status = check_ctf_status()
        assert status.global_installed is True
        assert status.global_injection_mode == "replace"

    def test_codex_global_install_switches_replace_back_to_append(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        monkeypatch.setenv("HOME", str(tmp_path))
        installer = CTFConfigInstaller()
        success, message = installer.install_global(injection_mode="replace")
        assert success, message

        success, message = installer.install_global(injection_mode="append")
        assert success, message
        config_content = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
        assert 'developer_instructions = """' in config_content
        assert 'model_instructions_file' not in config_content

    def test_codex_global_install_refuses_unmanaged_developer_instructions(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller
        from codex_session_patcher.ctf_config.status import GLOBAL_MARKER

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        base_config = codex_dir / "config.toml"
        original = '\n'.join([
            'developer_instructions = "existing"',
            '',
            '[features]',
            'guardian_approval = false',
            '',
        ])
        base_config.write_text(original, encoding="utf-8")

        installer = CTFConfigInstaller()
        success, message = installer.install_global(injection_mode="append")

        assert success is False
        assert "顶层已有 developer_instructions" in message
        assert base_config.read_text(encoding="utf-8") == original
        assert GLOBAL_MARKER not in base_config.read_text(encoding="utf-8")

    def test_codex_global_install_refuses_unmanaged_model_instructions_file(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        base_config = codex_dir / "config.toml"
        original = '\n'.join([
            'model_instructions_file = "~/.codex/prompts/existing.md"',
            '',
            '[features]',
            'guardian_approval = false',
            '',
        ])
        base_config.write_text(original, encoding="utf-8")

        installer = CTFConfigInstaller()
        success, message = installer.install_global(injection_mode="replace")

        assert success is False
        assert "顶层已有 model_instructions_file" in message
        assert base_config.read_text(encoding="utf-8") == original

    def test_codex_global_uninstall_removes_managed_developer_instructions_block(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller
        from codex_session_patcher.ctf_config.status import GLOBAL_MARKER

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        base_config = codex_dir / "config.toml"
        base_config.write_text(
            '\n'.join([
                'model = "auto"',
                f'{GLOBAL_MARKER} 安全测试模式（由 codex-session-patcher 管理）',
                'developer_instructions = """',
                '# Custom CTF',
                '"""',
                '',
                '[projects."/tmp/work"]',
                'trust_level = "trusted"',
                '',
            ]),
            encoding="utf-8",
        )

        installer = CTFConfigInstaller()
        success, message = installer.uninstall_global()

        assert success, message
        cleaned_base = base_config.read_text(encoding="utf-8")
        assert GLOBAL_MARKER not in cleaned_base
        assert 'developer_instructions = """' not in cleaned_base
        assert '# Custom CTF' not in cleaned_base
        assert 'model = "auto"' in cleaned_base
        assert '[projects."/tmp/work"]' in cleaned_base

    def test_codex_prompt_save_updates_profile_developer_instructions(self, tmp_path, monkeypatch):
        from web.backend import api

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(api, "DEFAULT_CONFIG_FILE", str(tmp_path / ".codex-patcher" / "config.json"))
        codex_dir = tmp_path / ".codex"
        prompts_dir = codex_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        prompt_path = prompts_dir / "ctf_optimized.md"
        prompt_path.write_text("# Old Prompt", encoding="utf-8")
        monkeypatch.setitem(api._CTF_PROMPT_PATHS, "codex", str(prompt_path))

        profile_config = codex_dir / "ctf.config.toml"
        profile_config.write_text(
            '\n'.join([
                'developer_instructions = """',
                '# Old Prompt',
                '"""',
                'model = "gpt-5.1-codex-max"',
                '',
            ]),
            encoding="utf-8",
        )

        asyncio.run(api.save_ctf_prompt("codex", {"prompt": "# New Prompt"}))

        profile_content = profile_config.read_text(encoding="utf-8")
        assert "# New Prompt" in profile_content
        assert "# Old Prompt" not in profile_content
        assert 'model = "gpt-5.1-codex-max"' in profile_content
        assert prompt_path.read_text(encoding="utf-8") == "# New Prompt"

    def test_codex_prompt_get_reads_profile_developer_instructions(self, tmp_path, monkeypatch):
        from web.backend import api

        monkeypatch.setenv("HOME", str(tmp_path))
        codex_dir = tmp_path / ".codex"
        prompts_dir = codex_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        prompt_path = prompts_dir / "ctf_optimized.md"
        prompt_path.write_text("# Stale File Prompt", encoding="utf-8")
        monkeypatch.setitem(api._CTF_PROMPT_PATHS, "codex", str(prompt_path))

        profile_config = codex_dir / "ctf.config.toml"
        profile_config.write_text(
            'developer_instructions = """\n# Effective Prompt\n"""\n',
            encoding="utf-8",
        )

        result = asyncio.run(api.get_ctf_prompt("codex"))

        assert result["prompt"] == "# Effective Prompt"
        assert result["is_installed"] is True

    def test_codex_prompt_save_updates_global_developer_instructions(self, tmp_path, monkeypatch):
        from codex_session_patcher.ctf_config.status import GLOBAL_MARKER
        from web.backend import api

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(api, "DEFAULT_CONFIG_FILE", str(tmp_path / ".codex-patcher" / "config.json"))
        codex_dir = tmp_path / ".codex"
        prompts_dir = codex_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        prompt_path = prompts_dir / "ctf_optimized.md"
        prompt_path.write_text("# Old Prompt", encoding="utf-8")
        monkeypatch.setitem(api._CTF_PROMPT_PATHS, "codex", str(prompt_path))

        base_config = codex_dir / "config.toml"
        base_config.write_text(
            '\n'.join([
                'model = "auto"',
                f'{GLOBAL_MARKER} 安全测试模式（由 codex-session-patcher 管理）',
                'developer_instructions = """',
                '# Old Prompt',
                '"""',
                '',
                '[projects."/tmp/work"]',
                'trust_level = "trusted"',
                '',
            ]),
            encoding="utf-8",
        )

        asyncio.run(api.save_ctf_prompt("codex", {"prompt": "# New Global Prompt"}))

        config_content = base_config.read_text(encoding="utf-8")
        assert "# New Global Prompt" in config_content
        assert "# Old Prompt" not in config_content
        assert '[projects."/tmp/work"]' in config_content
        assert prompt_path.read_text(encoding="utf-8") == "# New Global Prompt"

    def test_codex_prompt_reset_updates_profile_developer_instructions(self, tmp_path, monkeypatch):
        from web.backend import api

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(api, "DEFAULT_CONFIG_FILE", str(tmp_path / ".codex-patcher" / "config.json"))
        codex_dir = tmp_path / ".codex"
        prompts_dir = codex_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        prompt_path = prompts_dir / "ctf_optimized.md"
        prompt_path.write_text("# Old Prompt", encoding="utf-8")
        monkeypatch.setitem(api._CTF_PROMPT_PATHS, "codex", str(prompt_path))

        profile_config = codex_dir / "ctf.config.toml"
        profile_config.write_text(
            'developer_instructions = """\n# Old Prompt\n"""\n',
            encoding="utf-8",
        )

        default_prompt = api._get_default_prompt("codex")
        asyncio.run(api.reset_ctf_prompt("codex"))

        assert api._read_codex_developer_instructions() == default_prompt
        profile_content = profile_config.read_text(encoding="utf-8")
        assert "# Old Prompt" not in profile_content
        assert prompt_path.read_text(encoding="utf-8") == default_prompt

    def test_codex_installer_uses_default_without_custom(self, tmp_path):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        installer = CTFConfigInstaller()
        installer.codex_dir = str(tmp_path / ".codex")
        installer.config_path = os.path.join(installer.codex_dir, "config.toml")
        installer.profile_config_path = os.path.join(installer.codex_dir, "ctf.config.toml")
        installer.prompts_dir = os.path.join(installer.codex_dir, "prompts")

        success, _ = installer.install()
        assert success

        # install() 写入的文件由 _get_prompt_file() 决定，默认为 ctf_optimized.md
        prompt_file = installer._get_prompt_file()
        actual_path = os.path.join(installer.prompts_dir, prompt_file)
        with open(actual_path, 'r') as f:
            content = f.read()
        # 默认内容应来自 BUILTIN_TEMPLATES 中标记为 default 的模板
        assert len(content) > 100

    def test_claude_installer_accepts_custom_prompt(self, tmp_path):
        from codex_session_patcher.ctf_config.installer import ClaudeCodeCTFInstaller

        installer = ClaudeCodeCTFInstaller()
        installer.workspace_dir = str(tmp_path / "claude-ctf")
        installer.claude_dir = os.path.join(installer.workspace_dir, ".claude")
        installer.prompt_path = os.path.join(installer.claude_dir, "CLAUDE.md")
        installer.readme_path = os.path.join(installer.workspace_dir, "README.md")

        custom = "# My Custom Claude Prompt"
        success, _ = installer.install(custom_prompt=custom)
        assert success

        with open(installer.prompt_path, 'r') as f:
            content = f.read()
        assert content == custom


class TestCTFStatus:
    """验证 CTFStatus 包含 OpenCode 字段"""

    def test_status_has_opencode_fields(self):
        from codex_session_patcher.ctf_config.status import CTFStatus
        status = CTFStatus()
        assert hasattr(status, 'opencode_installed')
        assert hasattr(status, 'opencode_workspace_exists')
        assert hasattr(status, 'opencode_prompt_exists')
        assert hasattr(status, 'opencode_workspace_path')
        assert hasattr(status, 'opencode_prompt_path')
        assert status.opencode_installed is False
