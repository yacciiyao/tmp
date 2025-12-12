// web/app/components/AppTopbar.js
import { store } from '../store.js';

export default {
    name: 'AppTopbar',
    setup() {
        const router = VueRouter.useRouter();
        const route = VueRouter.useRoute();

        function isActive(path) {
            return route.path === path;
        }

        function to(path) {
            if (route.path !== path) router.push(path);
        }

        function logout() {
            store.clearAuth();
            router.replace('/login');
        }

        return { store, isActive, to, logout };
    },
    template: `
  <div class="app-topbar">
    <div class="brand">Multi-Agent Hub</div>
    <div class="nav">
      <a href="javascript:;" :class="{active:isActive('/chat')}" @click="to('/chat')">Chat</a>
      <a v-if="store.isAdmin()" href="javascript:;" :class="{active:isActive('/admin')}" @click="to('/admin')">Admin</a>
    </div>
    <div>
      <el-dropdown>
        <span class="el-dropdown-link">
          {{ store.getUser()?.username || '未登录' }}
          <el-icon style="vertical-align: middle;"><arrow-down /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>角色：{{ store.getUser()?.role || '-' }}</el-dropdown-item>
            <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
  `,
};
