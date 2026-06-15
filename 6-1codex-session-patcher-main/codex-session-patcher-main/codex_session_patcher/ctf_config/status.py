# -*- coding: utf-8 -*-
"""
CTF 配置状态检查
"""

import os
import re
from dataclasses import dataclass
from typing import List, Optional

CTF_MARKER = 'managed-by: codex-session-patcher:ctf'
DEFAULT_CLAUDE_CTF_WORKSPACE = os.path.expanduser("~/.claude-ctf-workspace")
DEFAULT_OPENCODE_CTF_WORKSPACE = os.path.expanduser("~/.opencode-ctf-workspace")


GLOBAL_MARKER = '# __csp_ctf_global__'
DEFAULT_CODEX_PROMPT_FILE = "ctf_optimized.md"


@dataclass
class CTFStatus:
    """CTF 配置状态"""
    # Codex
    installed: bool = False
    config_exists: bool = False
    prompt_exists: bool = False
    profile_available: bool = False
    global_installed: bool = False
    injection_mode: str = "none"
    global_injection_mode: str = "none"
    config_path: Optional[str] = None
    prompt_path: Optional[str] = None
    # Claude Code
    claude_installed: bool = False
    claude_workspace_exists: bool = False
    claude_prompt_exists: bool = False
    claude_workspace_path: Optional[str] = None
    claude_prompt_path: Optional[str] = None
    # OpenCode
    opencode_installed: bool = False
    opencode_workspace_exists: bool = False
    opencode_prompt_exists: bool = False
    opencode_workspace_path: Optional[str] = None
    opencode_prompt_path: Optional[str] = None


def _top_level_lines(content: str) -> List[str]:
    """返回第一个 TOML section 前的顶层行。"""
    lines = content.splitlines()
    section_start = len(lines)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('[') and not stripped.startswith('#'):
            section_start = index
            break
    return lines[:section_start]


def _has_top_level_key(content: str, key: str) -> bool:
    """检查未注释的顶层 key。"""
    pattern = re.compile(rf'^\s*{re.escape(key)}\s*=')
    return any(pattern.match(line) for line in _top_level_lines(content))


def _get_top_level_string_value(content: str, key: str) -> Optional[str]:
    """读取未注释的顶层字符串值。"""
    pattern = re.compile(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"')
    for line in _top_level_lines(content):
        match = pattern.match(line)
        if match:
            return match.group(1)
    return None


def _default_codex_prompt_path(codex_dir: str) -> str:
    return os.path.join(codex_dir, "prompts", DEFAULT_CODEX_PROMPT_FILE)


def _managed_global_block(content: str) -> str:
    """返回全局模式标记后的受管理顶层配置块。"""
    marker_index = content.find(GLOBAL_MARKER)
    if marker_index < 0:
        return ""

    block_lines = []
    for line in content[marker_index:].splitlines():
        stripped = line.strip()
        if block_lines and stripped.startswith('[') and not stripped.startswith('#'):
            break
        block_lines.append(line)
    return "\n".join(block_lines)


def check_ctf_status() -> CTFStatus:
    """
    检查 CTF 配置的安装状态（Codex + Claude Code）

    Returns:
        CTFStatus: 配置状态信息
    """
    # ── Codex 检查 ──
    codex_dir = os.path.expanduser("~/.codex")
    base_config_path = os.path.join(codex_dir, "config.toml")
    profile_config_path = os.path.join(codex_dir, "ctf.config.toml")

    status = CTFStatus(
        config_path=profile_config_path,
        prompt_path=None,
    )

    if os.path.exists(profile_config_path):
        try:
            with open(profile_config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            status.config_exists = True
            if _has_top_level_key(content, "developer_instructions"):
                status.profile_available = True
                status.prompt_exists = True
                status.injection_mode = "append"
                default_prompt_path = _default_codex_prompt_path(codex_dir)
                if os.path.exists(default_prompt_path):
                    status.prompt_path = default_prompt_path
            else:
                prompt_path = _get_top_level_string_value(content, "model_instructions_file")
                if prompt_path:
                    status.profile_available = True
                    status.injection_mode = "replace"
                    status.prompt_path = os.path.expanduser(prompt_path)
        except Exception:
            pass

    if os.path.exists(base_config_path):
        try:
            with open(base_config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if GLOBAL_MARKER in content:
                    status.global_installed = True
                    managed_content = _managed_global_block(content)
                    if _has_top_level_key(managed_content, "developer_instructions"):
                        status.global_injection_mode = "append"
                    elif _has_top_level_key(managed_content, "model_instructions_file"):
                        status.global_injection_mode = "replace"
        except Exception:
            pass

    if status.prompt_path and os.path.exists(status.prompt_path):
        status.prompt_exists = True

    status.installed = status.config_exists and status.prompt_exists and status.profile_available

    # ── Claude Code 检查 ──
    workspace_path = DEFAULT_CLAUDE_CTF_WORKSPACE
    claude_prompt_path = os.path.join(workspace_path, ".claude", "CLAUDE.md")

    status.claude_workspace_path = workspace_path
    status.claude_prompt_path = claude_prompt_path
    status.claude_workspace_exists = os.path.isdir(workspace_path)

    if os.path.exists(claude_prompt_path):
        try:
            with open(claude_prompt_path, 'r', encoding='utf-8') as f:
                content = f.read(500)  # 只需读开头
                if CTF_MARKER in content:
                    status.claude_prompt_exists = True
        except Exception:
            pass

    status.claude_installed = status.claude_workspace_exists and status.claude_prompt_exists

    # ── OpenCode 检查 ──
    opencode_workspace = DEFAULT_OPENCODE_CTF_WORKSPACE
    opencode_agents_path = os.path.join(opencode_workspace, "AGENTS.md")

    status.opencode_workspace_path = opencode_workspace
    status.opencode_prompt_path = opencode_agents_path
    status.opencode_workspace_exists = os.path.isdir(opencode_workspace)

    if os.path.exists(opencode_agents_path):
        try:
            with open(opencode_agents_path, 'r', encoding='utf-8') as f:
                content = f.read(500)
                if CTF_MARKER in content:
                    status.opencode_prompt_exists = True
        except Exception:
            pass

    status.opencode_installed = status.opencode_workspace_exists and status.opencode_prompt_exists

    return status
