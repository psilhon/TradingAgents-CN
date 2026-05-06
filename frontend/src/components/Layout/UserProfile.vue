<template>
  <div class="user-profile" :class="{ collapsed: appStore.sidebarCollapsed }">
    <el-dropdown trigger="click" @command="handleCommand">
      <div class="profile-info">
        <div class="avatar" :title="userDisplayName">
          <img v-if="userAvatar" :src="userAvatar" alt="" />
          <span v-else>{{ userInitials }}</span>
        </div>
        <div v-if="!appStore.sidebarCollapsed" class="user-info">
          <div class="username">{{ userDisplayName }}</div>
          <div class="user-role">
            <span class="role-dot"></span>
            {{ userRole }}
          </div>
        </div>
        <el-icon v-if="!appStore.sidebarCollapsed" class="caret"><CaretBottom /></el-icon>
      </div>

      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="settings">
            <el-icon><Setting /></el-icon>
            设置
          </el-dropdown-item>
          <el-dropdown-item divided command="logout">
            <el-icon><SwitchButton /></el-icon>
            退出登录
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { Setting, SwitchButton, CaretBottom } from '@element-plus/icons-vue'

const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()

// fork-local 用户名覆盖：把 backend 默认 admin 显示成 Psilhon
// 不影响 authStore / API 调用，仅前端展示层
const DISPLAY_NAME_OVERRIDES: Record<string, string> = {
  admin: 'Psilhon',
}

const userAvatar = computed(() => authStore.user?.avatar || undefined)
const userDisplayName = computed(() => {
  const raw = authStore.user?.username
  if (!raw) return '未登录'
  return DISPLAY_NAME_OVERRIDES[raw] ?? raw
})
const userRole = computed(() => {
  if (!authStore.user) return '未登录'
  return '在线'
})

// 用户名首字母（最多 2 个字符，大写）—— 用于 avatar 占位
const userInitials = computed(() => {
  const name = userDisplayName.value
  if (!name || name === '未登录') return '?'
  // 中文取前 1 个字；英文取首字母（最多 2 个）
  const isChinese = /[一-龥]/.test(name)
  if (isChinese) return name.slice(0, 1)
  const parts = name.split(/\s+/).filter(Boolean)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
})

const handleCommand = async (command: string) => {
  switch (command) {
    case 'settings':
      router.push('/settings')
      break
    case 'logout':
      await authStore.logout()
      ElMessage.success('已退出登录')
      router.push('/login')
      break
  }
}
</script>

<style lang="scss" scoped>
.user-profile {
  padding: 8px;

  &.collapsed {
    padding: 8px 4px;
  }

  .profile-info {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    padding: 6px 8px;
    border-radius: var(--radius-sm);
    transition: background 0.15s;

    &:hover {
      background: var(--bg-hover);

      .caret { color: var(--fg-secondary); }
    }
  }
}

.avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--accent), #b8861e);
  color: var(--accent-fg);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  overflow: hidden;
  position: relative;

  // 细微高光环
  &::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 50%;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.12);
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.user-info {
  flex: 1;
  min-width: 0;
  line-height: 1.2;
}

.username {
  font-size: 13px;
  font-weight: 600;
  color: var(--fg-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: 0.01em;
}

.user-role {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--fg-muted);
  margin-top: 3px;
}

.role-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--down);
  box-shadow: 0 0 4px rgba(var(--down-rgb), 0.6);
  flex-shrink: 0;
}

.caret {
  color: var(--fg-disabled);
  font-size: 12px;
  flex-shrink: 0;
  transition: color 0.15s;
}
</style>
