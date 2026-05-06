<template>
  <div class="basic-layout">
    <!-- 侧边栏 -->
    <aside
      class="sidebar"
      :class="{ collapsed: appStore.sidebarCollapsed }"
      :style="{ width: appStore.actualSidebarWidth + 'px' }"
    >
      <div class="sidebar-header">
        <div class="logo">
          <div class="logo-icon">TA</div>
          <div v-show="!appStore.sidebarCollapsed" class="logo-text">
            <div class="logo-name">TradingAgents</div>
          </div>
        </div>
      </div>
      
      <nav class="sidebar-nav">
        <SidebarMenu />
      </nav>
      
      <div class="sidebar-footer">
        <UserProfile />
      </div>
    </aside>

    <!-- 点击蒙层：移动端展开时，点击空白处收起侧边栏 -->
    <div
      v-if="isMobile && !appStore.sidebarCollapsed"
      class="sidebar-overlay"
      @click="appStore.setSidebarCollapsed(true)"
    ></div>

    <!-- 主内容区 -->
    <div class="main-container" :style="{ marginLeft: appStore.actualSidebarWidth + 'px' }" @click="handleMainClick">
      <!-- 顶部导航栏 -->
      <header class="header">
        <div class="header-left">
          <el-button
            type="text"
            @click.stop="appStore.toggleSidebar()"
            class="sidebar-toggle"
          >
            <el-icon><Expand v-if="appStore.sidebarCollapsed" /><Fold v-else /></el-icon>
          </el-button>
          
          <Breadcrumb />
        </div>

        <div class="header-center">
          <MarketTicker />
        </div>

        <div class="header-right">
          <HeaderActions />
        </div>
      </header>

      <!-- 页面内容 -->
      <main class="main-content">
        <div class="content-wrapper">
          <router-view v-slot="{ Component, route }">
            <transition
              :name="route.meta.transition || 'fade'"
              mode="out-in"
              appear
            >
              <keep-alive :include="keepAliveComponents">
                <component :is="Component" :key="route.fullPath" />
              </keep-alive>
            </transition>
          </router-view>
        </div>
      </main>

      <!-- 页脚 -->
      <footer class="footer">
        <AppFooter />
      </footer>
    </div>

    <!-- 回到顶部 -->
    <el-backtop :right="40" :bottom="40" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '@/stores/app'
import SidebarMenu from '@/components/Layout/SidebarMenu.vue'
import UserProfile from '@/components/Layout/UserProfile.vue'
import Breadcrumb from '@/components/Layout/Breadcrumb.vue'
import HeaderActions from '@/components/Layout/HeaderActions.vue'
import MarketTicker from '@/components/Layout/MarketTicker.vue'
import AppFooter from '@/components/Layout/AppFooter.vue'
import { Expand, Fold } from '@element-plus/icons-vue'

const appStore = useAppStore()
const route = useRoute()
const { width } = useWindowSize()

// 需要缓存的组件
const keepAliveComponents = computed(() => [
  'Dashboard',
  'StockScreening',
  'AnalysisHistory',
  'QueueManagement'
])

// 移动端判断
const isMobile = computed(() => width.value < 768)

// 点击主内容时，若移动端且侧边栏已展开，则收起
const handleMainClick = () => {
  if (isMobile.value && !appStore.sidebarCollapsed) {
    appStore.setSidebarCollapsed(true)
  }
}

// 监听窗口大小变化：在小屏幕上自动折叠侧边栏
watch(width, (newWidth) => {
  if (newWidth < 768 && !appStore.sidebarCollapsed) {
    appStore.setSidebarCollapsed(true)
  }
})

// 路由变化时，移动端收起侧边栏
watch(() => route.fullPath, () => {
  if (isMobile.value) {
    appStore.setSidebarCollapsed(true)
  }
})
</script>

<style lang="scss" scoped>
.basic-layout {
  min-height: 100vh;
  background-color: var(--bg-canvas);
}

.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 950; // 低于侧边栏(1000)，高于内容区
}

.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  background-color: var(--bg-sidebar);
  border-right: 1px solid var(--border-default);
  transition: width 0.3s ease;
  z-index: 1000;
  display: flex;
  flex-direction: column;

  // 参考稿：右边缘 accent glow（仅 dark 模式可见）
  &::after {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    width: 1px;
    height: 100%;
    background: linear-gradient(to bottom, transparent, var(--accent-glow) 40%, transparent);
    pointer-events: none;
  }

  &.collapsed {
    width: 64px !important;
  }

  .sidebar-header {
    height: 64px;
    display: flex;
    align-items: center;
    padding: 0 16px;
    border-bottom: 1px solid var(--border-default);

    .logo {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }

    .logo-icon {
      flex-shrink: 0;
      width: 34px;
      height: 34px;
      border-radius: var(--radius-sm);
      background: linear-gradient(135deg, var(--accent), #b8861e);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: var(--font-mono);
      font-size: 13px;
      font-weight: 700;
      color: var(--accent-fg);
      letter-spacing: -0.5px;
    }

    .logo-text {
      line-height: 1.2;
      min-width: 0;
    }

    .logo-name {
      font-size: 14px;
      font-weight: 600;
      color: var(--fg-primary);
      letter-spacing: 0.02em;
      white-space: nowrap;
    }
  }

  .sidebar-nav {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
  }

  .sidebar-footer {
    border-top: 1px solid var(--border-default);
    padding: 8px;
  }
}

.main-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  transition: margin-left 0.3s ease;
}

.header {
  height: 56px;
  background-color: var(--bg-sidebar);
  border-bottom: 1px solid var(--border-default);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 999;
  gap: 16px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-shrink: 0;

    .sidebar-toggle {
      padding: 6px;

      .el-icon {
        font-size: 16px;
      }
    }
  }

  .header-center {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 0;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
}

.main-content {
  flex: 1;
  padding: 24px;
  min-height: calc(100vh - 60px - 60px); // 减去header和footer高度

  .content-wrapper {
    max-width: 1400px;
    margin: 0 auto;
  }
}

.footer {
  height: 60px;
  background-color: var(--el-bg-color);
  border-top: 1px solid var(--el-border-color-light);
  display: flex;
  align-items: center;
  justify-content: center;
}

// 响应式设计
@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    
    &:not(.collapsed) {
      transform: translateX(0);
    }
  }

  .main-container {
    margin-left: 0 !important;
  }

  .main-content {
    padding: 16px;
  }

  .header {
    padding: 0 16px;
  }
}

// 路由过渡动画
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-left-enter-active,
.slide-left-leave-active {
  transition: all 0.3s ease;
}

.slide-left-enter-from {
  transform: translateX(30px);
  opacity: 0;
}

.slide-left-leave-to {
  transform: translateX(-30px);
  opacity: 0;
}
</style>
