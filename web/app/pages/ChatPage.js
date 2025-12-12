// web/app/pages/ChatPage.js
import { store } from '../store.js';
import { SidebarSessions } from '../components/SidebarSessions.js';
import { MessageList } from '../components/MessageList.js';
import { ChatComposer } from '../components/ChatComposer.js';
import { ChatToolbar } from '../components/ChatToolbar.js';

export const ChatPage = {
    name: 'ChatPage',
    components: { SidebarSessions, MessageList, ChatComposer, ChatToolbar },
    template: `
    <div class="page-chat">
      <SidebarSessions />
      <section class="chat">
        <ChatToolbar />
        <MessageList />
        <ChatComposer />
      </section>
    </div>
  `,
    setup() {
        // 确保已登录
        if (!store.token) { window.location.hash = '#/login'; }
        return { store };
    },
};
