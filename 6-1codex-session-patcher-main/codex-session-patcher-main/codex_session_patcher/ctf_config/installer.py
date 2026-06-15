# -*- coding: utf-8 -*-
"""
CTF 配置安装器
"""
from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from typing import Optional

from .templates import (
    CTF_CONFIG_TEMPLATE, SECURITY_MODE_PROMPT,
    CLAUDE_CODE_SECURITY_MODE_PROMPT, CLAUDE_CODE_CTF_README,
    OPENCODE_SECURITY_MODE_PROMPT, OPENCODE_CTF_CONFIG, OPENCODE_CTF_README,
    BUILTIN_TEMPLATES,
)
from .status import (
    check_ctf_status, CTFStatus, GLOBAL_MARKER, CTF_MARKER,
    DEFAULT_CLAUDE_CTF_WORKSPACE, DEFAULT_OPENCODE_CTF_WORKSPACE,
)


class CTFConfigInstaller:
    """CTF 配置安装器"""

    DEFAULT_PROMPT_FILE = "ctf_optimized.md"
    INJECTION_MODE_APPEND = "append"
    INJECTION_MODE_REPLACE = "replace"

    def __init__(self):
        self.codex_dir = os.path.expanduser("~/.codex")
        self.config_path = os.path.join(self.codex_dir, "config.toml")
        self.profile_config_path = os.path.join(self.codex_dir, "ctf.config.toml")
        self.prompts_dir = os.path.join(self.codex_dir, "prompts")

    def _get_prompt_file(self) -> str:
        """从用户配置获取当前选中的模板文件名，没有则返回默认"""
        try:
            from ..config_manager import ConfigManager
            config = ConfigManager().load_config()
            return config.get('ctf_prompts', {}).get('codex', {}).get('file') or self.DEFAULT_PROMPT_FILE
        except Exception:
            return self.DEFAULT_PROMPT_FILE

    def _get_prompt_content(self) -> str:
        """从用户配置获取当前选中的模板内容，没有则使用默认"""
        try:
            from ..config_manager import ConfigManager
            config = ConfigManager().load_config()
            saved = config.get('ctf_prompts', {}).get('codex', {}).get('prompt')
            if saved:
                return saved
        except Exception:
            pass
        # 使用默认模板
        from .templates import BUILTIN_TEMPLATES
        for tpl in BUILTIN_TEMPLATES.get('codex', []):
            if tpl.get('default'):
                return tpl['prompt']
        return BUILTIN_TEMPLATES['codex'][0]['prompt']

    def _normalize_injection_mode(self, injection_mode: Optional[str]) -> str:
        """归一化 Codex 提示词注入模式。"""
        mode = injection_mode or self.INJECTION_MODE_APPEND
        if mode not in {self.INJECTION_MODE_APPEND, self.INJECTION_MODE_REPLACE}:
            raise ValueError("injection_mode 只支持 append 或 replace")
        return mode

    def install(self, custom_prompt: str = None, injection_mode: str = INJECTION_MODE_APPEND) -> tuple[bool, str]:
        """
        安装 Profile 模式（自动禁用 Global 模式）

        Args:
            custom_prompt: 自定义提示词内容，为 None 时从配置/默认模板读取
            injection_mode: append 表示追加 developer_instructions；replace 表示替换内置提示词

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            injection_mode = self._normalize_injection_mode(injection_mode)
            details = []

            # 1. 先禁用 Global 模式（如果已启用）
            status = check_ctf_status()
            if status.global_installed:
                success, msg = self.uninstall_global()
                if success:
                    details.append("✓ 已自动禁用全局模式")

            # 2. 确定 prompt 文件名和内容
            prompt_file = self._get_prompt_file()
            prompt_path = os.path.join(self.prompts_dir, prompt_file)
            prompt_content = custom_prompt or self._get_prompt_content()

            # 3. 确保 prompts 目录存在
            os.makedirs(self.prompts_dir, exist_ok=True)

            # 4. 备份现有配置（如果存在）
            backup_paths = []
            if os.path.exists(self.config_path):
                backup_path = self._backup_config(self.config_path)
                if backup_path:
                    backup_paths.append(backup_path)
            if os.path.exists(self.profile_config_path):
                backup_path = self._backup_config(self.profile_config_path)
                if backup_path:
                    backup_paths.append(backup_path)

            # 5. 写入 prompt 文件
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)

            # 6. 写入新版 profile 配置，并清理旧版 profile 配置
            profile_added = self._update_config(prompt_content, prompt_file, injection_mode)

            # 构建详细消息
            details.append(f"✓ 已创建安全测试提示词: {prompt_path}")
            for backup_path in backup_paths:
                details.append(f"✓ 已备份原配置到: {backup_path}")
            if profile_added:
                details.append(f"✓ 已创建 ctf profile 配置: {self.profile_config_path}")
            else:
                details.append(f"✓ 已更新 ctf profile 配置: {self.profile_config_path}")
            if injection_mode == self.INJECTION_MODE_APPEND:
                details.append("✓ 注入方式: 追加规则（developer_instructions）")
            else:
                details.append("✓ 注入方式: 替换内置提示词（model_instructions_file）")
            details.append("使用 'codex -p ctf' 启动安全测试会话")

            return True, "\n".join(details)

        except Exception as e:
            return False, f"安装失败: {str(e)}"

    def uninstall(self) -> tuple[bool, str]:
        """
        卸载 Profile 模式

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 删除 prompt 文件（仅当 Global 模式未启用时）
            status = check_ctf_status()
            if not status.global_installed:
                # 删除所有由本工具写入的 prompt 文件
                for f in os.listdir(self.prompts_dir) if os.path.exists(self.prompts_dir) else []:
                    if f.endswith('.md'):
                        fp = os.path.join(self.prompts_dir, f)
                        os.remove(fp)
                        details.append(f"✓ 已删除提示词文件: {fp}")

            # 2. 移除新版 profile 文件和旧版 profile 配置
            removed = self._remove_ctf_profile()
            if removed:
                details.append(f"✓ 已移除 ctf profile 配置: {self.profile_config_path}")

            if not details:
                return True, "Profile 模式未安装"

            details.append("Profile 模式已禁用")
            return True, "\n".join(details)

        except Exception as e:
            return False, f"卸载失败: {str(e)}"

    def _backup_config(self, path: Optional[str] = None) -> Optional[str]:
        """备份现有配置文件"""
        target_path = path or self.config_path
        if not os.path.exists(target_path):
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{target_path}.bak-{timestamp}"

        try:
            shutil.copy2(target_path, backup_path)
            return backup_path
        except Exception:
            return None

    def _update_config(
        self,
        prompt_content: str = None,
        prompt_file: str = None,
        injection_mode: str = INJECTION_MODE_APPEND,
    ) -> bool:
        """更新新版 CTF profile 配置，并清理旧版 profile 配置

        Args:
            prompt_content: 提示词内容
            prompt_file: prompt 文件名
            injection_mode: append 或 replace

        Returns:
            bool: 是否添加了新的 profile 文件（False 表示更新已有文件）
        """
        injection_mode = self._normalize_injection_mode(injection_mode)
        instructions = prompt_content or self._get_prompt_content()
        filename = prompt_file or self._get_prompt_file()
        profile_added = not os.path.exists(self.profile_config_path)

        os.makedirs(self.codex_dir, exist_ok=True)
        profile_content = self._read_profile_config_source(instructions)
        if injection_mode == self.INJECTION_MODE_APPEND:
            profile_content = self._upsert_developer_instructions(profile_content, instructions)
        else:
            profile_content = self._upsert_model_instructions_file(profile_content, filename)
        with open(self.profile_config_path, 'w', encoding='utf-8') as f:
            f.write(profile_content)

        self._remove_legacy_ctf_entries()

        return profile_added

    def _read_profile_config_source(self, prompt_content: str) -> str:
        """读取新版 profile 文件；若不存在，则从旧 [profiles.ctf] 迁移内容。"""
        if os.path.exists(self.profile_config_path):
            with open(self.profile_config_path, 'r', encoding='utf-8') as f:
                return f.read()

        legacy_lines = self._read_legacy_ctf_profile_body()
        if legacy_lines is not None:
            legacy_content = ''.join(legacy_lines).lstrip('\n')
            return '# Codex CTF profile managed by codex-session-patcher\n' + legacy_content

        return CTF_CONFIG_TEMPLATE.format(prompt=self._escape_multiline_basic_string(prompt_content))

    def _read_legacy_ctf_profile_body(self) -> Optional[list[str]]:
        """读取旧 profile 及其子表内容，迁移为新版 profile 文件结构。"""
        if not os.path.exists(self.config_path):
            return None

        with open(self.config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        body = []
        found = False
        index = 0

        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            match = re.match(r'^\[profiles\.ctf(?:\.([^\]]+))?\]$', stripped)
            if not match:
                index += 1
                continue

            found = True
            suffix = match.group(1)
            if suffix:
                if body and body[-1].strip():
                    body.append('\n')
                body.append(f'[{suffix}]\n')

            index += 1
            while index < len(lines) and not lines[index].strip().startswith('['):
                if suffix == 'features' and re.match(r'^\s*js_repl\s*=', lines[index]):
                    index += 1
                    continue
                body.append(lines[index])
                index += 1

        return body if found else None

    def _upsert_developer_instructions(self, content: str, prompt_content: str) -> str:
        """只更新 profile 顶层 developer_instructions，保留其他设置。"""
        escaped_prompt = self._escape_multiline_basic_string(prompt_content)
        target_lines = ['developer_instructions = """\n', escaped_prompt, '\n"""\n']
        lines = content.splitlines(keepends=True)
        if not lines:
            return CTF_CONFIG_TEMPLATE.format(prompt=escaped_prompt)

        section_start = len(lines)
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('[') and not stripped.startswith('#'):
                section_start = index
                break

        top_level = lines[:section_start]
        rest = lines[section_start:]
        new_top_level = []
        replaced = False
        index = 0

        while index < len(top_level):
            line = top_level[index]

            if re.match(r'^\s*model_instructions_file\s*=', line):
                index += 1
                continue

            if re.match(r'^\s*developer_instructions\s*=', line):
                if not replaced:
                    new_top_level.extend(target_lines)
                    replaced = True
                index += 1
                if '"""' in line:
                    quote_count = line.count('"""')
                    while quote_count < 2 and index < len(top_level):
                        quote_count += top_level[index].count('"""')
                        index += 1
                continue

            new_top_level.append(line)
            index += 1

        if rest and new_top_level and new_top_level[-1].strip():
            new_top_level.append('\n')

        new_rest = []
        for line in rest:
            if re.match(r'^\s*model_instructions_file\s*=', line):
                continue
            new_rest.append(line)

        if not replaced:
            if new_top_level and not new_top_level[-1].endswith('\n'):
                new_top_level[-1] += '\n'
            new_top_level.extend(target_lines)

        profile_content = ''.join(new_top_level + new_rest)
        if not profile_content.endswith('\n'):
            profile_content += '\n'

        return profile_content

    def _upsert_model_instructions_file(self, content: str, prompt_file: str) -> str:
        """只更新 profile 顶层 model_instructions_file，保留其他设置。"""
        target_line = f'model_instructions_file = "~/.codex/prompts/{prompt_file}"\n'
        lines = content.splitlines(keepends=True)
        if not lines:
            return '# Codex CTF profile managed by codex-session-patcher\n' + target_line

        section_start = len(lines)
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('[') and not stripped.startswith('#'):
                section_start = index
                break

        top_level = lines[:section_start]
        rest = lines[section_start:]
        new_top_level = []
        inserted = False
        index = 0

        while index < len(top_level):
            line = top_level[index]

            if re.match(r'^\s*model_instructions_file\s*=', line):
                if not inserted:
                    new_top_level.append(target_line)
                    inserted = True
                index += 1
                continue

            if re.match(r'^\s*developer_instructions\s*=', line):
                index += 1
                if '"""' in line:
                    quote_count = line.count('"""')
                    while quote_count < 2 and index < len(top_level):
                        quote_count += top_level[index].count('"""')
                        index += 1
                continue

            new_top_level.append(line)
            index += 1

        if not inserted:
            if new_top_level and not new_top_level[-1].endswith('\n'):
                new_top_level[-1] += '\n'
            new_top_level.append(target_line)

        if rest and new_top_level and new_top_level[-1].strip():
            new_top_level.append('\n')

        profile_content = ''.join(new_top_level + rest)
        if not profile_content.endswith('\n'):
            profile_content += '\n'

        return profile_content

    def _escape_multiline_basic_string(self, value: str) -> str:
        """转义 TOML 多行 basic string 不能直接承载的字符。"""
        return value.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')

    def _remove_ctf_profile(self) -> bool:
        """移除新版 CTF profile 文件和旧版 profile 配置

        Returns:
            bool: 是否移除了 profile
        """
        removed = False

        if os.path.exists(self.profile_config_path):
            os.remove(self.profile_config_path)
            removed = True

        return self._remove_legacy_ctf_entries() or removed

    def _remove_legacy_ctf_entries(self) -> bool:
        """从 base config.toml 移除 Codex 0.134.0+ 不再接受的旧 profile 写法。"""
        if not os.path.exists(self.config_path):
            return False

        with open(self.config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        removed = False
        current_section = None
        index = 0

        while index < len(lines):
            line = lines[index]
            stripped = line.strip()

            if re.match(r'^\[profiles\.ctf(?:\.[^\]]+)?\]$', stripped):
                removed = True
                while new_lines and not new_lines[-1].strip():
                    new_lines.pop()
                if new_lines and 'codex-session-patcher' in new_lines[-1]:
                    new_lines.pop()
                index += 1
                while index < len(lines) and not lines[index].strip().startswith('['):
                    index += 1
                continue

            if stripped.startswith('['):
                current_section = stripped

            if current_section is None and re.match(r'^profile\s*=\s*["\']ctf["\'](?:\s*#.*)?$', stripped):
                removed = True
                index += 1
                continue

            new_lines.append(line)
            index += 1

        if not removed:
            return False

        while new_lines and not new_lines[0].strip():
            new_lines.pop(0)

        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        return removed

    def install_global(self, injection_mode: str = INJECTION_MODE_APPEND) -> tuple[bool, str]:
        """
        全局模式安装：在 config.toml 顶层注入 Codex CTF 提示词配置
        自动禁用 Profile 模式

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            injection_mode = self._normalize_injection_mode(injection_mode)
            details = []

            # 1. 先检查用户手写的顶层提示词配置，避免生成重复 key。
            existing_content = ""
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            existing_lines = existing_content.split('\n') if existing_content else []
            unmanaged_key = self._find_unmanaged_top_level_instruction_key(existing_lines)
            if unmanaged_key:
                return False, (
                    f"全局模式安装失败: config.toml 顶层已有 {unmanaged_key}。"
                    "为避免覆盖你的配置或生成重复 key，请先手动迁移或删除该配置。"
                )

            # 2. 确定模板内容
            prompt_file = self._get_prompt_file()
            prompt_path = os.path.join(self.prompts_dir, prompt_file)

            # 3. 先卸载 Profile 模式，包括旧版 [profiles.ctf] 写法
            removed = self._remove_ctf_profile()
            if removed:
                details.append("✓ 已自动禁用 Profile 模式")

            # 4. 确保 prompts 目录存在，写入 prompt 文件
            os.makedirs(self.prompts_dir, exist_ok=True)
            prompt_content = self._get_prompt_content()
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            details.append(f"✓ 已写入安全测试提示词: {prompt_path}")

            # 5. 备份 config.toml
            backup_path = None
            if os.path.exists(self.config_path):
                backup_path = self._backup_config()
                if backup_path:
                    details.append(f"✓ 已备份原配置到: {backup_path}")

            # 6. 读取现有配置
            existing_content = ""
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()

            lines = existing_content.split('\n') if existing_content else []

            # 7. 更新或插入受管理的提示词配置
            lines = self._remove_global_managed_block(lines)
            lines = self._insert_global_managed_block(lines, prompt_content, prompt_file, injection_mode)
            details.append("✓ 已注入全局配置")
            if injection_mode == self.INJECTION_MODE_APPEND:
                details.append("✓ 注入方式: 追加规则（developer_instructions）")
            else:
                details.append("✓ 注入方式: 替换内置提示词（model_instructions_file）")

            # 8. 写入配置
            new_content = '\n'.join(lines)
            new_content = new_content.strip() + '\n'

            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            details.append(f"✓ 配置文件: {self.config_path}")
            details.append("⚠ 所有新 Codex 会话将自动启用安全测试上下文")
            details.append("使用完毕请及时禁用全局模式")

            return True, "\n".join(details)

        except Exception as e:
            return False, f"全局模式安装失败: {str(e)}"

    def _find_unmanaged_top_level_instruction_key(self, lines: list[str]) -> Optional[str]:
        """查找非本工具管理的顶层提示词配置。"""
        unmanaged_lines = self._remove_global_managed_block(lines)
        for line in unmanaged_lines:
            stripped = line.strip()
            if stripped.startswith('[') and not stripped.startswith('#'):
                return None
            if not stripped or stripped.startswith('#'):
                continue
            if re.match(r'^developer_instructions\s*=', stripped):
                return "developer_instructions"
            if re.match(r'^model_instructions_file\s*=', stripped):
                return "model_instructions_file"
        return None

    def uninstall_global(self) -> tuple[bool, str]:
        """
        全局模式卸载：从 config.toml 移除标记行和 developer_instructions 块

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            if not os.path.exists(self.config_path):
                return True, "全局模式未安装"

            with open(self.config_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            new_lines, found = self._remove_global_managed_block([line.rstrip('\n') for line in lines], return_found=True)

            if not found:
                return True, "全局模式未安装"

            # 清理首部多余空行
            while new_lines and not new_lines[0].strip():
                new_lines.pop(0)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines).strip() + '\n')

            details = []
            details.append(f"✓ 已从配置移除全局注入: {self.config_path}")
            details.append("新 Codex 会话将不再自动启用安全测试上下文")

            return True, "\n".join(details)

        except Exception as e:
            return False, f"全局模式卸载失败: {str(e)}"

    def _update_global_config(
        self,
        prompt_content: str,
        prompt_file: str = None,
        injection_mode: str = INJECTION_MODE_APPEND,
    ) -> bool:
        """更新已启用全局模式中的提示词配置。"""
        injection_mode = self._normalize_injection_mode(injection_mode)
        if not os.path.exists(self.config_path):
            return False

        with open(self.config_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()

        lines = existing_content.split('\n') if existing_content else []
        lines, found = self._remove_global_managed_block(lines, return_found=True)
        if not found:
            return False

        lines = self._insert_global_managed_block(
            lines,
            prompt_content,
            prompt_file or self._get_prompt_file(),
            injection_mode,
        )
        new_content = '\n'.join(lines).strip() + '\n'
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True

    def _insert_global_managed_block(
        self,
        lines: list[str],
        prompt_content: str,
        prompt_file: str,
        injection_mode: str,
    ) -> list[str]:
        """在第一个 section 前插入全局模式受管理配置块。"""
        if injection_mode == self.INJECTION_MODE_APPEND:
            target_lines = [
                f'{GLOBAL_MARKER} 安全测试模式（由 codex-session-patcher 管理）',
                'developer_instructions = """',
                self._escape_multiline_basic_string(prompt_content),
                '"""',
            ]
        else:
            target_lines = [
                f'{GLOBAL_MARKER} 安全测试模式（由 codex-session-patcher 管理）',
                f'model_instructions_file = "~/.codex/prompts/{prompt_file}"',
            ]

        insert_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('[') and not stripped.startswith('#'):
                insert_idx = i
                break
            insert_idx = i + 1

        while insert_idx > 0 and not lines[insert_idx - 1].strip():
            lines.pop(insert_idx - 1)
            insert_idx -= 1

        block = target_lines if insert_idx == 0 else [''] + target_lines
        for line in reversed(block):
            lines.insert(insert_idx, line)

        return lines

    def _remove_global_managed_block(self, lines: list[str], return_found: bool = False):
        """移除全局模式中由本工具标记管理的配置块。"""
        new_lines = []
        found = False
        index = 0

        while index < len(lines):
            line = lines[index]

            if GLOBAL_MARKER not in line:
                new_lines.append(line)
                index += 1
                continue

            found = True
            index += 1

            if index >= len(lines):
                continue

            next_line = lines[index].strip()

            if next_line.startswith('model_instructions_file'):
                index += 1
                continue

            if next_line.startswith('developer_instructions'):
                quote_count = lines[index].count('"""')
                index += 1
                while quote_count < 2 and index < len(lines):
                    quote_count += lines[index].count('"""')
                    index += 1
                continue

        if return_found:
            return new_lines, found
        return new_lines

    def get_status(self) -> CTFStatus:
        """获取当前配置状态"""
        return check_ctf_status()


class ClaudeCodeCTFInstaller:
    """Claude Code CTF 配置安装器"""

    def __init__(self):
        self.workspace_dir = DEFAULT_CLAUDE_CTF_WORKSPACE
        self.claude_dir = os.path.join(self.workspace_dir, ".claude")
        self.prompt_path = os.path.join(self.claude_dir, "CLAUDE.md")
        self.readme_path = os.path.join(self.workspace_dir, "README.md")
        self.settings_local = os.path.expanduser("~/.claude/settings.local.json")

    def install(self, custom_prompt: str = None, inject_permissions: bool = False) -> tuple[bool, str]:
        """
        安装 Claude Code CTF 配置

        Args:
            custom_prompt: 自定义提示词内容，为 None 时使用默认模板
            inject_permissions: 是否向 settings.local.json 注入宽松权限

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 创建工作空间目录
            os.makedirs(self.claude_dir, exist_ok=True)
            details.append(f"✓ 已创建工作空间: {self.workspace_dir}")

            # 2. 写入 .claude/CLAUDE.md
            prompt_content = custom_prompt or CLAUDE_CODE_SECURITY_MODE_PROMPT
            with open(self.prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            details.append(f"✓ 已创建 CLAUDE.md: {self.prompt_path}")

            # 3. 写入 README
            with open(self.readme_path, 'w', encoding='utf-8') as f:
                f.write(CLAUDE_CODE_CTF_README)
            details.append(f"✓ 已创建 README: {self.readme_path}")

            # 4. 可选：注入权限
            if inject_permissions:
                self._inject_permissions()
                details.append("✓ 已注入宽松权限到 settings.local.json")

            details.append("")
            details.append("使用方法: cd ~/.claude-ctf-workspace && claude")

            return True, "\n".join(details)

        except Exception as e:
            return False, f"安装失败: {str(e)}"

    def uninstall(self) -> tuple[bool, str]:
        """
        卸载 Claude Code CTF 配置

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 删除 .claude/CLAUDE.md（验证标记）
            if os.path.exists(self.prompt_path):
                try:
                    with open(self.prompt_path, 'r', encoding='utf-8') as f:
                        content = f.read(500)
                    if CTF_MARKER in content:
                        os.remove(self.prompt_path)
                        details.append(f"✓ 已删除 CLAUDE.md: {self.prompt_path}")
                    else:
                        return False, "CLAUDE.md 不是由本工具创建的，跳过删除"
                except Exception:
                    os.remove(self.prompt_path)
                    details.append(f"✓ 已删除 CLAUDE.md: {self.prompt_path}")

            # 2. 删除 README（如果存在）
            if os.path.exists(self.readme_path):
                os.remove(self.readme_path)
                details.append(f"✓ 已删除 README: {self.readme_path}")

            # 3. 尝试清理空目录（不删除用户自建的文件）
            try:
                if os.path.isdir(self.claude_dir) and not os.listdir(self.claude_dir):
                    os.rmdir(self.claude_dir)
                    details.append(f"✓ 已删除空目录: {self.claude_dir}")
                if os.path.isdir(self.workspace_dir) and not os.listdir(self.workspace_dir):
                    os.rmdir(self.workspace_dir)
                    details.append(f"✓ 已删除工作空间: {self.workspace_dir}")
            except OSError:
                pass  # 目录非空，保留

            # 4. 移除注入的权限
            self._remove_permissions()

            if not details:
                return True, "Claude Code CTF 配置未安装"

            return True, "\n".join(details)

        except Exception as e:
            return False, f"卸载失败: {str(e)}"

    def _inject_permissions(self):
        """向 settings.local.json 注入宽松的 Bash 权限"""
        import json

        data = {"permissions": {"allow": [], "deny": [], "ask": []}}
        if os.path.exists(self.settings_local):
            try:
                with open(self.settings_local, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass

        permissions = data.setdefault("permissions", {})
        allow = permissions.setdefault("allow", [])

        # 检查是否已注入
        marker = "__csp_ctf_marker__"
        if marker in allow:
            return

        # 备份
        self._backup_settings()

        # 注入权限
        allow.append(marker)
        allow.append("Bash(*)")

        with open(self.settings_local, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _remove_permissions(self):
        """从 settings.local.json 移除注入的权限"""
        import json

        if not os.path.exists(self.settings_local):
            return

        try:
            with open(self.settings_local, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return

        permissions = data.get("permissions", {})
        allow = permissions.get("allow", [])

        marker = "__csp_ctf_marker__"
        if marker not in allow:
            return

        # 移除标记和注入的权限
        allow.remove(marker)
        if "Bash(*)" in allow:
            allow.remove("Bash(*)")

        with open(self.settings_local, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _backup_settings(self) -> Optional[str]:
        """备份 settings.local.json"""
        if not os.path.exists(self.settings_local):
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.settings_local}.ctf-backup-{timestamp}"

        try:
            shutil.copy2(self.settings_local, backup_path)
            return backup_path
        except Exception:
            return None

    def get_status(self) -> CTFStatus:
        """获取当前配置状态"""
        return check_ctf_status()


class OpenCodeCTFInstaller:
    """OpenCode CTF 配置安装器"""

    def __init__(self):
        self.workspace_dir = DEFAULT_OPENCODE_CTF_WORKSPACE
        self.agents_md_path = os.path.join(self.workspace_dir, "AGENTS.md")
        self.config_path = os.path.join(self.workspace_dir, "opencode.json")
        self.readme_path = os.path.join(self.workspace_dir, "README.md")

    def install(self, custom_prompt: str = None) -> tuple[bool, str]:
        """
        安装 OpenCode CTF 配置

        Args:
            custom_prompt: 自定义提示词内容，为 None 时使用默认模板

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 创建工作空间目录
            os.makedirs(self.workspace_dir, exist_ok=True)
            details.append(f"✓ 已创建工作空间: {self.workspace_dir}")

            # 2. 写入 AGENTS.md
            prompt_content = custom_prompt or OPENCODE_SECURITY_MODE_PROMPT
            with open(self.agents_md_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            details.append(f"✓ 已创建 AGENTS.md: {self.agents_md_path}")

            # 3. 写入 opencode.json
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(OPENCODE_CTF_CONFIG)
            details.append(f"✓ 已创建 opencode.json: {self.config_path}")

            # 4. 写入 README
            with open(self.readme_path, 'w', encoding='utf-8') as f:
                f.write(OPENCODE_CTF_README)
            details.append(f"✓ 已创建 README: {self.readme_path}")

            details.append("")
            details.append("使用方法: cd ~/.opencode-ctf-workspace && opencode")

            return True, "\n".join(details)

        except Exception as e:
            return False, f"安装失败: {str(e)}"

    def uninstall(self) -> tuple[bool, str]:
        """
        卸载 OpenCode CTF 配置

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 删除 AGENTS.md（验证标记）
            if os.path.exists(self.agents_md_path):
                try:
                    with open(self.agents_md_path, 'r', encoding='utf-8') as f:
                        content = f.read(500)
                    if CTF_MARKER in content:
                        os.remove(self.agents_md_path)
                        details.append(f"✓ 已删除 AGENTS.md: {self.agents_md_path}")
                    else:
                        return False, "AGENTS.md 不是由本工具创建的，跳过删除"
                except Exception:
                    os.remove(self.agents_md_path)
                    details.append(f"✓ 已删除 AGENTS.md: {self.agents_md_path}")

            # 2. 删除 opencode.json
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
                details.append(f"✓ 已删除 opencode.json: {self.config_path}")

            # 3. 删除 README
            if os.path.exists(self.readme_path):
                os.remove(self.readme_path)
                details.append(f"✓ 已删除 README: {self.readme_path}")

            # 4. 尝试清理空目录
            try:
                if os.path.isdir(self.workspace_dir) and not os.listdir(self.workspace_dir):
                    os.rmdir(self.workspace_dir)
                    details.append(f"✓ 已删除工作空间: {self.workspace_dir}")
            except OSError:
                pass

            if not details:
                return True, "OpenCode CTF 配置未安装"

            return True, "\n".join(details)

        except Exception as e:
            return False, f"卸载失败: {str(e)}"

    def get_status(self) -> CTFStatus:
        """获取当前配置状态"""
        return check_ctf_status()
