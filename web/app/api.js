// web/app/api.js
const BASE = ''; // same-origin

const http = axios.create({
    baseURL: BASE,
    timeout: 60000,
});

http.interceptors.request.use((cfg) => {
    const token = localStorage.getItem('token');
    if (token) cfg.headers.Authorization = `Bearer ${token}`;
    return cfg;
});

http.interceptors.response.use(
    (res) => res,
    (err) => {
        if (err?.response?.status === 401) {
            localStorage.removeItem('token');
            window.location.hash = '#/login';
        }
        return Promise.reject(err);
    }
);

export const api = {
    // Auth
    async login(username, password) {
        const form = new URLSearchParams();
        form.set('grant_type', 'password');
        form.set('username', username);
        form.set('password', password);
        const res = await http.post('/api/auth/login', form, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        });
        return res.data; // { access_token, token_type }
    },
    async me() {
        const res = await http.get('/api/auth/me');
        return res.data;
    },

    // Models
    async listModels() {
        const res = await http.get('/api/models', { params: { enabled: true } });
        return res.data;
    },

    // Sessions
    async createSession(payload) {
        const res = await http.post('/api/chat/sessions', payload);
        return res.data;
    },
    async listSessions() {
        const res = await http.get('/api/chat/sessions');
        return res.data;
    },
    async getSession(id) {
        const res = await http.get(`/api/chat/sessions/${id}`);
        return res.data;
    },
    async deleteSession(id) {
        const res = await http.delete(`/api/chat/sessions/${id}`);
        return res.data;
    },
    async patchSession(id, payload) {
        // 需后端支持 PATCH；若 405/409，调用处会兜底新建
        const res = await http.patch(`/api/chat/sessions/${id}`, payload);
        return res.data;
    },
    async listMessages(sessionId, limit = 200, offset = 0) {
        // 需后端 GET /api/chat/sessions/{id}/messages
        const res = await http.get(`/api/chat/sessions/${sessionId}/messages`, { params: { limit, offset } });
        return res.data?.items || [];
    },

    // Chat
    async sendMessage(sessionId, content) {
        const res = await http.post(`/api/chat/sessions/${sessionId}/messages`, {
            content,
            message_type: 'text',
        });
        return res.data;
    },

    streamMessage({ sessionId, content, onChunk, onEnd, onError }) {
        // 用 fetch 解析 SSE，带上 Authorization 头
        const ctrl = new AbortController();
        const url = `/api/chat/sessions/${encodeURIComponent(sessionId)}/stream?` + new URLSearchParams({
            content,
            message_type: 'text',
        }).toString();

        fetch(url, {
            method: 'GET',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token') || ''}` },
            signal: ctrl.signal,
        }).then(async (res) => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const reader = res.body.getReader();
            const dec = new TextDecoder('utf-8');
            let buf = '';
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buf += dec.decode(value, { stream: true });
                const parts = buf.split('\n\n');
                buf = parts.pop() || '';
                for (const part of parts) {
                    // SSE: lines
                    const lines = part.split('\n');
                    let dataLine = lines.find(l => l.startsWith('data: '));
                    if (!dataLine) continue;
                    const data = dataLine.slice(6);
                    if (data === '[DONE]') { onEnd?.(); return; }
                    onChunk?.(data);
                }
            }
            onEnd?.();
        }).catch((e) => onError?.(e));

        return { abort: () => ctrl.abort() };
    },
};

// 简单配额常量（前端校验用；后端仍会再校验）
export const QUOTA = {
    MAX_SESSIONS: 100,
    MAX_MSG_PER_SESSION: 1000,
    MAX_INPUT_CHARS: 4000,
};
