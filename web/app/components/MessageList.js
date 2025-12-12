// web/app/components/MessageList.js
import { store } from '../store.js';

const md = (raw) => {
    // 极简 Markdown（行内 code + 换行）
    if (!raw) return '';
    const esc = raw.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const inline = esc.replace(/`([^`]+)`/g, '<code>$1</code>');
    return inline.replace(/\n/g, '<br/>');
};

export const MessageList = {
    name: 'MessageList',
    template: `
    <div class="chat-scroll" ref="scrollWrap">
      <div v-for="m in list" :key="m.id" class="msg" :class="{ me: m.role==='user' }">
        <div class="avatar" v-if="m.role!=='user'">
          <img src="/web/assets/ai.jpg" alt="ai"/>
        </div>
        <div class="bubble">
          <div class="content" v-html="render(m.content_text)"></div>
        </div>
        <div class="avatar" v-if="m.role==='user'">
          <img src="/web/assets/user.jpg" alt="user"/>
        </div>
      </div>
    </div>
  `,
    setup() {
        const list = Vue.computed(() => store.currentMessages());
        const scrollWrap = Vue.ref(null);
        Vue.watch(list, () => {
            // 滚动到底
            requestAnimationFrame(() => {
                if (scrollWrap.value) scrollWrap.value.scrollTop = scrollWrap.value.scrollHeight;
            });
        }, { deep: true });
        const render = (t) => md(t || '');
        return { store, list, render, scrollWrap };
    },
};
