# -*- coding: utf-8 -*-
"""
OpenCode SQLite 适配器

将 OpenCode 的 SQLite 数据库转换为管道可处理的 dict 格式。

OpenCode schema:
- session: id, project_id, title, directory, time_created, time_updated, ...
- message: id, session_id, data(JSON: {role, time, modelID, ...})
- part: id, message_id, session_id, data(JSON: {type, text, ...})
  Part types: text, reasoning, tool, step-start, step-finish, file
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认数据库路径
DEFAULT_OPENCODE_DB = os.path.expanduser("~/.local/share/opencode/opencode.db")
DEFAULT_OPENCODE_DIR = os.path.expanduser("~/.local/share/opencode/")


class OpenCodeDBAdapter:
    """OpenCode SQLite 数据库适配器"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_OPENCODE_DB

    def _connect(self, readonly: bool = True) -> sqlite3.Connection:
        """创建数据库连接"""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"OpenCode 数据库不存在: {self.db_path}")

        if readonly:
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")

        conn.row_factory = sqlite3.Row
        return conn

    def list_sessions(self) -> list[dict]:
        """列出所有会话，返回与 SessionInfo 兼容的信息列表"""
        conn = self._connect(readonly=True)
        try:
            cursor = conn.execute("""
                SELECT s.id, s.title, s.directory, s.time_created, s.time_updated,
                       s.project_id, p.name as project_name, p.worktree
                FROM session s
                LEFT JOIN project p ON s.project_id = p.id
                ORDER BY s.time_updated DESC
            """)
            sessions = []
            for row in cursor:
                time_updated = row['time_updated']
                # OpenCode 使用毫秒时间戳
                if time_updated > 1e12:
                    time_updated = time_updated / 1000.0
                time_created = row['time_created']
                if time_created > 1e12:
                    time_created = time_created / 1000.0

                dt = datetime.fromtimestamp(time_updated)
                sessions.append({
                    'session_id': row['id'],
                    'title': row['title'] or '',
                    'directory': row['directory'] or '',
                    'project_path': row['worktree'] or row['directory'] or '',
                    'mtime': time_updated,
                    'mtime_str': dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'date': dt.strftime('%Y-%m-%d'),
                    'project_name': row['project_name'] or '',
                })
            return sessions
        finally:
            conn.close()

    def load_session_messages(self, session_id: str) -> list[dict]:
        """加载会话的所有消息和 parts，转换为管道可处理的 dict 列表。

        返回格式与 JSONL 解析后类似:
        [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "..."},
                        {"type": "thinking", "text": "..."},  # reasoning → thinking
                    ]
                },
                "_oc_msg_id": "msg_xxx",
                "_oc_parts": [{"id": "prt_xxx", "type": "text", ...}, ...]
            },
            ...
        ]
        """
        conn = self._connect(readonly=True)
        try:
            # 获取消息
            msg_cursor = conn.execute("""
                SELECT id, data, time_created FROM message
                WHERE session_id = ?
                ORDER BY time_created ASC, id ASC
            """, (session_id,))
            messages = []
            for msg_row in msg_cursor:
                msg_data = json.loads(msg_row['data'])
                msg_id = msg_row['id']
                role = msg_data.get('role', 'unknown')

                # 获取该消息的所有 parts
                part_cursor = conn.execute("""
                    SELECT id, data FROM part
                    WHERE message_id = ?
                    ORDER BY id ASC
                """, (msg_id,))

                content = []
                parts_meta = []
                for part_row in part_cursor:
                    part_data = json.loads(part_row['data'])
                    part_type = part_data.get('type', '')
                    part_id = part_row['id']

                    parts_meta.append({
                        'id': part_id,
                        'type': part_type,
                    })

                    if part_type == 'text':
                        content.append({
                            'type': 'text',
                            'text': part_data.get('text', ''),
                        })
                    elif part_type == 'reasoning':
                        # 映射为 thinking 以与清洗管道兼容
                        content.append({
                            'type': 'thinking',
                            'text': part_data.get('text', ''),
                        })
                    # tool, step-start, step-finish, file 不参与拒绝检测，
                    # 但保留在 content 中以维护消息完整性
                    elif part_type in ('tool', 'step-start', 'step-finish', 'file'):
                        content.append({
                            'type': part_type,
                            '_data': part_data,
                        })

                line = {
                    'type': role,  # 'user' or 'assistant'
                    'message': {
                        'role': role,
                        'content': content,
                    },
                    '_oc_msg_id': msg_id,
                    '_oc_parts': parts_meta,
                    '_oc_session_id': session_id,
                }
                messages.append(line)

            return messages
        finally:
            conn.close()

    def save_session_messages(self, session_id: str, messages: list[dict]) -> int:
        """将修改后的消息写回 SQLite 数据库。

        只更新被标记为已修改的 part（text 内容替换或 reasoning 删除）。
        返回更新的 part 数量。
        """
        conn = self._connect(readonly=False)
        updated_count = 0
        try:
            for msg in messages:
                if msg.get('type') != 'assistant':
                    continue

                msg_id = msg.get('_oc_msg_id')
                if not msg_id:
                    continue

                content = msg.get('message', {}).get('content', [])
                parts_meta = msg.get('_oc_parts', [])

                # 获取当前 DB 中的 parts
                cursor = conn.execute(
                    "SELECT id, data FROM part WHERE message_id = ? ORDER BY id ASC",
                    (msg_id,)
                )
                db_parts = list(cursor)

                # 比对 content 中的文本 parts 与 DB parts
                text_idx = 0
                reasoning_ids_to_delete = set()

                for part_meta in parts_meta:
                    part_id = part_meta['id']
                    part_type = part_meta['type']

                    if part_type == 'text':
                        # 找到 content 中对应的 text 项
                        new_text = None
                        for item in content:
                            if item.get('type') == 'text':
                                if text_idx == 0:
                                    new_text = item.get('text', '')
                                    text_idx += 1
                                    break
                                text_idx -= 1

                        if new_text is not None:
                            # 检查是否与原始内容不同
                            for db_part in db_parts:
                                if db_part['id'] == part_id:
                                    old_data = json.loads(db_part['data'])
                                    if old_data.get('text') != new_text:
                                        old_data['text'] = new_text
                                        conn.execute(
                                            "UPDATE part SET data = ? WHERE id = ?",
                                            (json.dumps(old_data, ensure_ascii=False), part_id)
                                        )
                                        updated_count += 1
                                    break

                    elif part_type == 'reasoning':
                        # 检查 content 中是否还有对应的 thinking 项
                        has_thinking = any(
                            item.get('type') == 'thinking'
                            for item in content
                        )
                        if not has_thinking:
                            reasoning_ids_to_delete.add(part_id)

                # 删除被移除的 reasoning parts
                for part_id in reasoning_ids_to_delete:
                    conn.execute("DELETE FROM part WHERE id = ?", (part_id,))
                    updated_count += 1

            conn.commit()
            return updated_count
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def backup_database(self) -> str:
        """备份整个数据库文件。返回备份文件路径。"""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"数据库不存在: {self.db_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.db_path}.{timestamp}.bak"
        shutil.copy2(self.db_path, backup_path)
        logger.info("已创建数据库备份: %s", backup_path)
        return backup_path

    def restore_database(self, backup_path: str) -> None:
        """从备份恢复数据库"""
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")
        shutil.copy2(backup_path, self.db_path)
        logger.info("已从备份恢复数据库: %s", backup_path)

    def list_backups(self) -> list[dict]:
        """列出所有数据库备份"""
        backup_dir = os.path.dirname(self.db_path)
        db_name = os.path.basename(self.db_path)
        backups = []
        for f in os.listdir(backup_dir):
            if f.startswith(db_name + ".") and f.endswith(".bak"):
                full_path = os.path.join(backup_dir, f)
                stat = os.stat(full_path)
                backups.append({
                    'filename': f,
                    'path': full_path,
                    'size': stat.st_size,
                    'mtime': stat.st_mtime,
                    'mtime_str': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                })
        backups.sort(key=lambda x: x['mtime'], reverse=True)
        return backups

    def get_session_message_count(self, session_id: str) -> int:
        """获取会话的消息数量"""
        conn = self._connect(readonly=True)
        try:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM message WHERE session_id = ?",
                (session_id,)
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()
