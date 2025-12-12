export const routes = [
    { path: '/', redirect: '/chat' },
    { path: '/login', component: ()=>import('./pages/LoginPage.js') },
    { path: '/chat',  component: ()=>import('./pages/ChatPage.js')  },
];

export const router = VueRouter.createRouter({
    history: VueRouter.createWebHashHistory(),
    routes
});
