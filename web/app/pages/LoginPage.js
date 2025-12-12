// web/app/pages/LoginPage.js
import { api } from '../api.js';
import { store } from '../store.js';

export const LoginPage = {
    name: 'LoginPage',
    template: `
    <div class="login-page">
      <div class="login-card">
        <h2>登录</h2>
        <div class="row">
          <label>用户名</label>
          <input v-model="username" placeholder="admin" />
        </div>
        <div class="row">
          <label>密码</label>
          <input type="password" v-model="password" placeholder="******" />
        </div>
        <div class="row" style="margin-top:14px;">
          <button class="btn btn-primary" @click="doLogin" :disabled="submitting">
            {{ submitting ? '登录中...' : '登录' }}
          </button>
        </div>
      </div>
    </div>
  `,
    setup() {
        const router = VueRouter.useRouter();
        const username = Vue.ref('');
        const password = Vue.ref('');
        const submitting = Vue.ref(false);

        const doLogin = async () => {
            if (submitting.value) return;
            submitting.value = true;
            try {
                const { access_token } = await api.login(username.value, password.value);
                store.setToken(access_token);
                store.user = await api.me();
                await store.boot();
                router.replace({ name: 'chat' });
            } catch (e) {
                alert('登录失败'); console.error(e);
            } finally {
                submitting.value = false;
            }
        };

        return { username, password, submitting, doLogin };
    },
};
