// web/app/components/SidebarSessions.js
import { store } from '../store.js';

export const SidebarSessions = {
    name: 'SidebarSessions',
    template: `
    <aside class="sidebar">
      <div class="sidebar-head">
        <button class="btn btn-primary" @click="newChat">新建会话</button>
      </div>
      <div class="sidebar-list">
        <div
          v-for="s in store.sessions" :key="s.id"
          class="session-item" :class="{ active: s.id === store.activeSessionId }"
          @click="open(s.id)"
        >
          <div class="title">{{ s.title || '未命名会话' }}</div>
          <div class="session-actions">
            <button class="del" title="删除" @click.stop="remove(s.id)">✕</button>
          </div>
        </div>
      </div>
    </aside>
  `,
    setup() {
        const newChat = async () => {
            await store.ensureActiveSession({
                modelAlias: store.modelAlias,
                useRag: store.useRag,
                ragCorpusIds: store.ragCorpusIds,
                useStream: store.useStream,
            });
        };
        const open = async (id) => { await store.switchSession(id); };
        const remove = async (id) => { await store.deleteSession(id); };
        return { store, newChat, open, remove };
    },
};
