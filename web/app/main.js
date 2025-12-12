// web/app/main.js
import { router } from './router.js';
import { store } from './store.js';

const app = Vue.createApp({
    setup() {
        const logout = () => store.logout();
        return { store, logout };
    },
});
app.use(router);
app.mount('#app');

// 引导：已登录则拉取数据
if (store.token) {
    store.boot();
} else {
    window.location.hash = '#/login';
}
