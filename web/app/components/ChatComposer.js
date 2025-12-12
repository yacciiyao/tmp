// web/app/components/ChatComposer.js
import { store } from '../store.js';

export const ChatComposer = {
    name: 'ChatComposer',
    template: `
    <div class="composer">
      <div class="composer-wrap">
        <textarea v-model="input"
          :placeholder="store.useStream ? '输入内容，Enter 发送（Shift+Enter 换行）' : '输入内容...'"
          @keydown.enter.exact.prevent="send"
          @keydown.enter.shift.exact.stop
        ></textarea>
        <button v-if="store.streaming" class="stop-btn" @click="stop">停止</button>
        <button v-else class="send-btn" @click="send">发送</button>
      </div>
    </div>
  `,
    setup() {
        const input = Vue.ref('');
        const send = async () => {
            const text = input.value.trim();
            if (!text) return;
            await store.send(text);
            input.value = '';
        };
        const stop = () => store.stopStream();
        return { store, input, send, stop };
    },
};
