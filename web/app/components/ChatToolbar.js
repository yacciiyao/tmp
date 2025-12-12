// web/app/components/ChatToolbar.js
import { store } from '../store.js';

export const ChatToolbar = {
    name: 'ChatToolbar',
    template: `
    <div class="chat-toolbar">
      <!-- 模型选择（会话级，不提示，默认第一项） -->
      <select class="select" v-model="modelAlias" @change="onModelChange">
        <option v-for="m in store.models" :key="m.alias" :value="m.alias">{{ m.name }} ({{ m.alias }})</option>
      </select>

      <!-- RAG 开关（绿色） -->
      <button class="toggle" :class="{ 'is-active': store.useRag }" @click="toggleRag">
        <span class="dot"></span> RAG
      </button>

      <!-- 流式开关（绿色） -->
      <button class="toggle" :class="{ 'is-active': store.useStream }" @click="toggleStream">
        <span class="dot"></span> 流式
      </button>
    </div>
  `,
    setup() {
        const modelAlias = Vue.ref(store.modelAlias);

        Vue.watch(() => store.modelAlias, (v)=>{ modelAlias.value = v; });

        const onModelChange = async () => {
            await store.ensureActiveSession({
                modelAlias: modelAlias.value,
                useRag: store.useRag,
                ragCorpusIds: store.ragCorpusIds,
                useStream: store.useStream,
            });
        };

        const toggleRag = async () => {
            await store.ensureActiveSession({
                modelAlias: store.modelAlias,
                useRag: !store.useRag,
                ragCorpusIds: store.ragCorpusIds,
                useStream: store.useStream,
            });
        };

        const toggleStream = async () => {
            await store.ensureActiveSession({
                modelAlias: store.modelAlias,
                useRag: store.useRag,
                ragCorpusIds: store.ragCorpusIds,
                useStream: !store.useStream,
            });
        };

        return { store, modelAlias, onModelChange, toggleRag, toggleStream };
    },
};
