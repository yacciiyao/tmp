// web/app/store.js
import { api, QUOTA } from './api.js';

const { reactive } = Vue;

export const store = reactive({
    token: localStorage.getItem('token') || '',
    user: null,

    models: [],
    modelAlias: '',          // 当前会话要绑定的模型（新会话默认用它；空则取 models[0].alias）
    useRag: false,           // 当前会话配置（会被会话覆盖）
    useStream: true,         // 当前会话配置（会被会话覆盖）
    ragCorpusIds: [],

    sessions: [],
    activeSessionId: '',
    messages: {},            // { [sessionId]: Array<message> }
    streaming: false,
    streamer: null,

    async boot() {
        if (this.token) {
            try {
                this.user = await api.me();
            } catch { this.logout(); return; }
        }
        await this.loadModels();
        await this.loadSessions();

        // 默认选择模型：列表第一个
        if (!this.modelAlias && this.models.length) {
            this.modelAlias = this.models[0].alias;
        }

        // 确保有一个“空会话”
        if (!this.activeSessionId) {
            await this.ensureActiveSession({});
        }
    },

    setToken(t) { this.token = t; localStorage.setItem('token', t); },
    logout() { this.token = ''; localStorage.removeItem('token'); window.location.hash = '#/login'; },

    async loadModels() {
        try {
            this.models = await api.listModels();
        } catch (e) { console.warn('listModels failed', e); this.models = []; }
    },

    async loadSessions() {
        try {
            const res = await api.listSessions();
            this.sessions = res.items || [];
            // 选择第一个会话为激活
            if (this.sessions.length && !this.activeSessionId) {
                this.switchSession(this.sessions[0].id);
            }
        } catch (e) {
            console.warn('listSessions failed', e);
            this.sessions = [];
        }
    },

    sessionById(id) { return this.sessions.find(s => s.id === id) || null; },
    currentMessages() { return this.messages[this.activeSessionId] || []; },
    setMessages(sessionId, list) { this.messages[sessionId] = list || []; },

    async ensureActiveSession({ modelAlias, useRag, ragCorpusIds, useStream } = {}) {
        // 规则：若当前 active 会话存在且无消息 → 直接 PATCH/覆盖配置
        // 否则新建；但如果完全没有会话，也新建。
        if (!this.sessions.length) {
            await this._createAndActivate({ modelAlias, useRag, ragCorpusIds, useStream });
            return;
        }
        if (!this.activeSessionId) {
            this.activeSessionId = this.sessions[0].id;
        }
        const sid = this.activeSessionId;
        const hasMsg = (this.messages[sid]?.length || 0) > 0;
        if (!hasMsg) {
            await this._tryPatchConfig(sid, { modelAlias, useRag, ragCorpusIds, useStream });
            return;
        }
        await this._createAndActivate({ modelAlias, useRag, ragCorpusIds, useStream });
    },

    async _createAndActivate({ modelAlias, useRag, ragCorpusIds, useStream }) {
        if (this.sessions.length >= QUOTA.MAX_SESSIONS) {
            alert(`已达到会话上限（${QUOTA.MAX_SESSIONS}）`); return;
        }
        const alias = modelAlias || this.modelAlias || (this.models[0]?.alias || '');
        if (!alias) { alert('无可用模型'); return; }
        const body = {
            model_alias: alias,
            use_rag: !!useRag,
            rag_corpus_ids: ragCorpusIds || [],
            meta: { stream: useStream ?? this.useStream },
        };
        const s = await api.createSession(body);
        this.sessions.unshift(s);
        this.activeSessionId = s.id;
        this.modelAlias = s.model_alias;
        this.useRag = s.use_rag;
        this.ragCorpusIds = s.rag_corpus_ids || [];
        // meta.stream 前端状态同步
        this.useStream = (s.meta && s.meta.stream) ?? this.useStream;
        this.setMessages(s.id, []);
    },

    async _tryPatchConfig(sessionId, { modelAlias, useRag, ragCorpusIds, useStream }) {
        try {
            const body = {};
            if (modelAlias != null) body.model_alias = modelAlias;
            if (useRag != null) body.use_rag = !!useRag;
            if (ragCorpusIds != null) body.rag_corpus_ids = ragCorpusIds;
            if (useStream != null) body.meta = { stream: !!useStream };
            const updated = await api.patchSession(sessionId, body);
            // 写回
            const idx = this.sessions.findIndex(s => s.id === sessionId);
            if (idx >= 0) this.sessions[idx] = updated;
            this.modelAlias = updated.model_alias;
            this.useRag = updated.use_rag;
            this.ragCorpusIds = updated.rag_corpus_ids || [];
            this.useStream = (updated.meta && updated.meta.stream) ?? this.useStream;
        } catch (e) {
            // 405/409 → 新建会话
            await this._createAndActivate({
                modelAlias: modelAlias ?? this.modelAlias,
                useRag: useRag ?? this.useRag,
                ragCorpusIds: ragCorpusIds ?? this.ragCorpusIds,
                useStream: useStream ?? this.useStream,
            });
        }
    },

    async switchSession(sessionId) {
        if (sessionId === this.activeSessionId) return;
        this.activeSessionId = sessionId;
        // 拉取消息（若后端未提供接口，降级为空）
        try {
            const msgs = await api.listMessages(sessionId, 500, 0);
            this.setMessages(sessionId, msgs);
        } catch {
            this.setMessages(sessionId, this.messages[sessionId] || []);
        }
        // 同步会话级配置
        const s = this.sessionById(sessionId);
        if (s) {
            this.modelAlias = s.model_alias;
            this.useRag = s.use_rag;
            this.ragCorpusIds = s.rag_corpus_ids || [];
            this.useStream = (s.meta && s.meta.stream) ?? this.useStream;
        }
    },

    async deleteSession(sessionId) {
        try { await api.deleteSession(sessionId); } catch {}
        this.sessions = this.sessions.filter(s => s.id !== sessionId);
        delete this.messages[sessionId];
        if (this.activeSessionId === sessionId) {
            this.activeSessionId = this.sessions[0]?.id || '';
            if (this.activeSessionId) await this.switchSession(this.activeSessionId);
        }
    },

    async send(input) {
        if (!input || !input.trim()) return;
        if (input.length > QUOTA.MAX_INPUT_CHARS) { alert(`输入不得超过 ${QUOTA.MAX_INPUT_CHARS} 字`); return; }
        const sid = this.activeSessionId;
        const curCount = (this.messages[sid]?.length || 0);
        if (curCount >= QUOTA.MAX_MSG_PER_SESSION) { alert('已达单会话消息上限'); return; }

        // 先本地追加一条 user 消息占位
        const userMsg = {
            id: Date.now(), session_id: sid, role: 'user',
            message_type: 'text', content_text: input, created_at: Math.floor(Date.now()/1000),
        };
        this.messages[sid] = [...(this.messages[sid] || []), userMsg];

        if (!this.useStream) {
            try {
                const result = await api.sendMessage(sid, input);
                const ans = result.answer_message;
                this.messages[sid] = [...this.messages[sid], ans];
            } catch (e) {
                alert('发送失败'); console.error(e);
            }
            return;
        }

        // 流式
        this.streaming = true;
        let acc = '';
        const aiMsgId = Date.now() + 1;
        const aiMsg = {
            id: aiMsgId, session_id: sid, role: 'assistant',
            message_type: 'text', content_text: '', created_at: Math.floor(Date.now()/1000),
        };
        this.messages[sid] = [...this.messages[sid], aiMsg];

        this.streamer = api.streamMessage({
            sessionId: sid,
            content: input,
            onChunk: (tok) => {
                acc += tok;
                // 实时写入
                const list = this.messages[sid];
                const lastIdx = list.findIndex(m => m.id === aiMsgId);
                if (lastIdx >= 0) { list[lastIdx] = { ...list[lastIdx], content_text: acc }; this.messages[sid] = [...list]; }
            },
            onEnd: () => { this.streaming = false; this.streamer = null; },
            onError: (e) => { console.error('stream error', e); this.streaming = false; this.streamer = null; },
        });
    },

    stopStream() {
        if (this.streamer) this.streamer.abort();
        this.streaming = false; this.streamer = null;
    },
});
