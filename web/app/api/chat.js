// /web/app/api/chat.js
import { http } from "./http.js";

// 会话
export async function createSession(payload) {
    const resp = await http.post("/chat/sessions", payload);
    return resp.data;
}
export async function listSessions({ limit = 50, offset = 0 } = {}) {
    const resp = await http.get("/chat/sessions", { params: { limit, offset } });
    return resp.data; // { items, total }
}
export async function getSession(sessionId) {
    const resp = await http.get(`/chat/sessions/${encodeURIComponent(sessionId)}`);
    return resp.data;
}
export async function deleteSession(sessionId) {
    await http.delete(`/chat/sessions/${encodeURIComponent(sessionId)}`);
}
export async function patchSession(sessionId, payload) {
    const resp = await http.patch(`/chat/sessions/${encodeURIComponent(sessionId)}`, payload);
    return resp.data;
}

// 消息
export async function listMessages(sessionId, { limit = 500, offset = 0 } = {}) {
    const resp = await http.get(
        `/chat/sessions/${encodeURIComponent(sessionId)}/messages`,
        { params: { limit, offset } }
    );
    return resp.data; // 直接返回数组
}
export async function sendMessage(sessionId, { content, message_type = "text" }) {
    const resp = await http.post(
        `/chat/sessions/${encodeURIComponent(sessionId)}/messages`,
        { content, message_type }
    );
    return resp.data; // { session, request_message, answer_message, used_rag, extra }
}

// 流式（按需）
export function stream(sessionId, { content, message_type = "text", onChunk, onEnd, onError }) {
    const url = new URL(`/api/chat/sessions/${encodeURIComponent(sessionId)}/stream`, window.location.origin);
    url.searchParams.set("content", content);
    url.searchParams.set("message_type", message_type);

    const es = new EventSource(url.toString(), { withCredentials: true });
    es.onmessage = (e) => onChunk && onChunk(e.data);
    es.addEventListener("end", () => { onEnd && onEnd(); es.close(); });
    es.addEventListener("error", (e) => { onError && onError(e); es.close(); });
    return () => es.close();
}
