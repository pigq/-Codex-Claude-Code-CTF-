<template>
  <div class="help-panel">
    <n-space vertical size="large">
      <!-- 项目介绍 -->
      <n-card title="Codex Session Patcher" size="small">
        <n-space vertical>
          <p>一个帮助你在安全测试场景下更顺畅使用 Codex CLI 的工具集。</p>
          <n-ul>
            <n-li><strong>CTF/渗透模式</strong>：注入安全测试上下文，降低被拒绝概率</n-li>
            <n-li><strong>提示词改写</strong>：将敏感请求改写为更易接受的形式</n-li>
            <n-li><strong>会话清理</strong>：清理已产生的拒绝回复，恢复会话继续</n-li>
          </n-ul>
        </n-space>
      </n-card>

      <!-- 局限性 -->
      <n-card title="项目局限性" size="small">
        <n-collapse>
          <n-collapse-item title="配置注入的边界" name="config-limits">
            <n-ul>
              <n-li>无法覆盖平台最高层的安全策略</n-li>
              <n-li>对于明确的违规请求仍可能被拒绝</n-li>
              <n-li>效果因请求类型和模型版本而异</n-li>
            </n-ul>
          </n-collapse-item>

          <n-collapse-item title="提示词改写的局限" name="rewrite-limits">
            <n-ul>
              <n-li>不能改变用户的真实意图</n-li>
              <n-li>改写后仍可能被拒绝</n-li>
              <n-li>需要配合 CTF/渗透模式使用效果更好</n-li>
            </n-ul>
          </n-collapse-item>

          <n-collapse-item title="会话清理的局限" name="clean-limits">
            <n-ul>
              <n-li>只能清理已产生的拒绝回复</n-li>
              <n-li>无法保证后续对话不被拒绝</n-li>
              <n-li>清理后需要 resume 继续会话</n-li>
            </n-ul>
          </n-collapse-item>
        </n-collapse>
      </n-card>

      <!-- CTF 模式影响 -->
      <n-card title="CTF/渗透模式对普通任务的影响" size="small">
        <n-space vertical>
          <n-alert type="info" :bordered="false">
            提供两种模式：<strong>Profile 模式</strong>仅对指定会话生效，<strong>全局模式</strong>对所有新会话生效。
          </n-alert>

          <n-h4>两种模式对比</n-h4>
          <n-table :bordered="false" :single-line="false" size="small">
            <thead>
              <tr>
                <th>模式</th>
                <th>生效范围</th>
                <th>启用方式</th>
                <th>适用场景</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><n-tag type="info" size="small">Profile</n-tag></td>
                <td>仅当前会话</td>
                <td><code>codex -p ctf</code></td>
                <td>偶尔打 CTF</td>
              </tr>
              <tr>
                <td><n-tag type="warning" size="small">全局</n-tag></td>
                <td>所有新会话</td>
                <td>点击「全局启用」</td>
                <td>持续安全测试</td>
              </tr>
            </tbody>
          </n-table>

          <n-h4>启用后的变化</n-h4>
          <n-ul>
            <n-li><strong>执行风格</strong>：更直接、更简洁，偏向快速验证</n-li>
            <n-li><strong>安全视角</strong>：写正常代码时可能过度关注安全问题</n-li>
            <n-li><strong>环境假设</strong>：可能误判真实网站为靶场</n-li>
          </n-ul>

          <n-h4>建议</n-h4>
          <n-ul>
            <n-li>偶尔打 CTF：使用 <code>codex -p ctf</code></n-li>
            <n-li>持续安全测试：启用全局模式，结束后禁用</n-li>
            <n-li>日常开发：禁用全局模式即可</n-li>
          </n-ul>
        </n-space>
      </n-card>

      <!-- 推荐工作流 -->
      <n-card title="推荐工作流" size="small">
        <n-tabs type="line">
          <n-tab-pane name="ctf" tab="CTF/安全测试">
            <n-steps vertical :current="0">
              <n-step title="启用 CTF/渗透模式">
                在「提示词增强」页面点击启用
              </n-step>
              <n-step title="新开会话">
                使用命令 <code>codex -p ctf</code>
              </n-step>
              <n-step title="发送请求">
                如果被拒绝，使用提示词改写器
              </n-step>
              <n-step title="清理会话">
                如果仍被拒绝，使用会话清理功能
              </n-step>
              <n-step title="继续对话">
                使用 <code>codex resume</code> 继续
              </n-step>
            </n-steps>
          </n-tab-pane>

          <n-tab-pane name="normal" tab="日常开发">
            <n-steps vertical :current="0">
              <n-step title="不启用 CTF 模式">
                或使用后及时禁用
              </n-step>
              <n-step title="正常使用">
                直接运行 <code>codex</code>，不加 -p 参数
              </n-step>
            </n-steps>
          </n-tab-pane>
        </n-tabs>
      </n-card>

      <!-- 适用场景 -->
      <n-card title="适用场景" size="small">
        <n-space>
          <n-tag type="info" :bordered="false">CTF 比赛</n-tag>
          <n-tag type="info" :bordered="false">授权渗透测试</n-tag>
          <n-tag type="info" :bordered="false">Bug Bounty</n-tag>
          <n-tag type="info" :bordered="false">安全学习/研究</n-tag>
          <n-tag type="info" :bordered="false">漏洞分析</n-tag>
        </n-space>
      </n-card>
    </n-space>
  </div>
</template>

<script setup>
</script>

<style scoped>
.help-panel {
  max-width: 800px;
  margin: 0 auto;
}

.n-card {
  background: var(--color-bg-1);
}

code {
  background: #333;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

p {
  margin: 0 0 12px 0;
}

:deep(.n-ul) {
  margin: 8px 0;
  padding-left: 20px;
}

:deep(.n-li) {
  margin: 4px 0;
}
</style>