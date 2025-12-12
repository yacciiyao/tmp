// web/app/router.js
import { LoginPage } from './pages/LoginPage.js';
import { ChatPage } from './pages/ChatPage.js';

const routes = [
    { path: '/', redirect: '/chat' },
    { name: 'login', path: '/login', component: LoginPage },
    { name: 'chat',  path: '/chat', component: ChatPage },
];

export const router = VueRouter.createRouter({
    history: VueRouter.createWebHashHistory(),
    routes,
});
