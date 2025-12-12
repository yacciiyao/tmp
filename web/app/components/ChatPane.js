// web/app/components/ChatPane.js
import {
    listModels, listSessions, createSession, deleteSession,
    chatCompletion, chatStream, listMessages
} from '../api.js';

const { ref, reactive, computed, onMounted, watch } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

function pickSessionId(s) {
    return s?.session_uuid || s?.id || s?.session_id || '';
}

export default {
    name: 'ChatPane',
    setup() {
        const models = ref([]);
        const selectedModel = ref('');
        const useRag = ref(true);
        const useStream = ref(true);

        const sessions = ref([]);
        const activeSid = ref('');
        const loadingSessions = ref(false);
        const modelOf = reactive({});
        const msgsBySid = reactive({});
        const inputText = ref('');
        const sending = ref(false);

        const activeMsgs = computed(() => msgsBySid[activeSid.value] || []);
        const activeSession = computed(() => sessions.value.find(s => pickSessionId(s) === activeSid.value) || null);

        async function initModels() {
            try {
                const data = await listModels();
                const items = Array.isArray(data) ? data : (data?.items || []);
                models.value = items;
                if (!selectedModel.value && items.length) {
                    selectedModel.value = items[0].alias || items[0].model_alias || '';
                }
            } catch (e) {
                console.error(e);
                ElMessage.error('模型列表加载失败（请先登录）');
            }
        }

        async function loadSessions() {
            loadingSessions.value = true;
            try {
                const data = await listSessions({ limit: 100, offset: 0 });
                const items = Array.isArray(data) ? data : (data?.items || []);
                sessions.value = items;
                items.forEach(s => { modelOf[pickSessionId(s)] = s.model_alias; });

                if (!activeSid.value && items.length) {
                    await selectSessionById(pickSessionId(items[0]));
                }
            } catch (e) {
                console.error(e);
                // 未登录时这里会 401，已在 http.js 里处理跳登录
            } finally {
                loadingSessions.value = false;
            }
        }

        async function refreshMessages(sid) {
            try {
                const res = await listMessages(sid, { limit: 200, offset: 0 });
                const items = Array.isArray(res) ? res : (res?.items || res?.messages || []);
                msgsBySid[sid] = (items || []).map(m => ({
                    role: m.role,
                    content: m.content_text || '',
                    ragMeta: m.parsed_meta || null,
                }));
            } catch {
                msgsBySid[sid] = msgsBySid[sid] || [];
            }
        }

        async function onCreateSession() {
            if (!selectedModel.value) {
                ElMessage.warning('请先选择模型');
                return;
            }
            try {
                const s = await createSession({
                    model_alias: selectedModel.value,
                    use_rag: useRag.value,
                    rag_corpus_ids: [],
                });
                sessions.value.unshift(s);
                const sid = pickSessionId(s);
                modelOf[sid] = s.model_alias;
                await selectSessionById(sid);
                ElMessage.success('已创建新会话');
            } catch (e) {
                console.error(e);
                ElMessage.error('创建会话失败');
            }
        }

        async function onDeleteSession(s) {
            const sid = pickSessionId(s);
            try {
                await ElMessageBox.confirm('确定删除该会话吗？此操作不可恢复', '提示', { type: 'warning' });
            } catch { return; }
            try {
                await deleteSession(sid);
                sessions.value = sessions.value.filter(it => pickSessionId(it) !== sid);
                delete msgsBySid[sid];
                delete modelOf[sid];
                if (activeSid.value === sid) {
                    activeSid.value = '';
                    if (sessions.value.length) {
                        await selectSessionById(pickSessionId(sessions.value[0]));
                    }
                }
                ElMessage.success('已删除');
            } catch (e) {
                console.error(e);
                ElMessage.error('删除失败');
            }
        }

        async function selectSessionById(sid) {
            activeSid.value = sid;
            if (!msgsBySid[sid]) msgsBySid[sid] = [];
            selectedModel.value = modelOf[sid] || selectedModel.value;
            await refreshMessages(sid);
        }

        function onSelectSession(s) {
            selectSessionById(pickSessionId(s));
        }

        async function onChangeModel(nv) {
            const cur = activeSession.value;
            if (!cur) return;
            const bound = cur.model_alias;
            if (bound === nv) return;
            try {
                await ElMessageBox.confirm(
                    '每个会话绑定一个模型，切换模型将新建会话。是否继续？',
                    '切换模型',
                    { type: 'warning', confirmButtonText: '新建会话', cancelButtonText: '取消' },
                );
                await onCreateSession();
            } catch {
                selectedModel.value = bound;
            }
        }

        function extractRagRefs(resp) {
            const rag = resp?.extra?.rag || resp?.answer_message?.parsed_meta?.rag;
            const hits = rag?.hits || [];
            return hits.map(h => {
                const src = h.source_uri || h.doc_id || h.chunk_id || '';
                const score = typeof h.score === 'number' ? h.score.toFixed(3) : '';
                return { src, score, text: h.text || '' };
            });
        }

        async function send() {
            const text = (inputText.value || '').trim();
            if (!text) return;

            if (!activeSid.value) {
                await onCreateSession();
                if (!activeSid.value) return;
            }

            const ours = { role: 'user', content: text };
            msgsBySid[activeSid.value].push(ours);
            inputText.value = '';
            sending.value = true;

            try {
                if (useStream.value) {
                    const asst = { role: 'assistant', content: '' };
                    msgsBySid[activeSid.value].push(asst);
                    await chatStream({
                        session_id: activeSid.value,
                        content_text: text,
                        onChunk: (chunk) => { asst.content += chunk; },
                        onDone: async () => { await refreshMessages(activeSid.value); },
                        onError: () => { ElementPlus.ElMessage.error('发送失败（流式）'); },
                    });
                } else {
                    const resp = await chatCompletion({ session_id: activeSid.value, content_text: text });
                    const ragRefs = extractRagRefs(resp);
                    msgsBySid[activeSid.value].push({
                        role: 'assistant',
                        content: resp?.answer_message?.content_text || resp?.answer || '',
                        ragRefs,
                    });
                }
            } catch (e) {
                console.error(e);
                ElementPlus.ElMessage.error('发送失败');
            } finally {
                sending.value = false;
            }
        }

        onMounted(async () => {
            await initModels();
            await loadSessions();
        });

        watch(selectedModel, (nv, ov) => {
            if (!ov) return;
            onChangeModel(nv);
        });

        return {
            models, selectedModel, useRag, useStream,
            sessions, activeSid, loadingSessions,
            msgsBySid, activeMsgs, inputText, sending,
            onCreateSession, onDeleteSession, onSelectSession, send,
            pickSessionId, activeSession,
        };
    },
    template: `
  <div class="chat-wrap">
    <!-- 左侧会话 -->
    <div class="chat-sessions">
      <div class="head">
        <el-button type="success" size="small" @click="onCreateSession">新建会话</el-button>
        <el-input size="small" placeholder="搜索（占位）"></el-input>
      </div>
      <div class="list">
        <div v-for="s in sessions" :key="pickSessionId(s)"
             class="item" :class="{active: pickSessionId(s)===activeSid}"
             @click="onSelectSession(s)">
          <div class="del">
            <el-button text type="danger" size="small" @click.stop="onDeleteSession(s)">删</el-button>
          </div>
          <div class="title">{{ s.title || '未命名会话' }}</div>
          <div class="meta">模型：{{ s.model_alias || '-' }}</div>
        </div>
      </div>
    </div>

    <!-- 工具条 -->
    <div class="chat-toolbar">
      <div>模型：</div>
      <el-select v-model="selectedModel" placeholder="选择模型" size="small" style="width:260px;">
        <el-option v-for="m in models" :key="m.alias || m.model_alias"
                   :label="m.alias || m.model_alias"
                   :value="m.alias || m.model_alias" />
      </el-select>
      <el-divider direction="vertical" />
      <el-switch v-model="useRag" active-text="RAG 开" inactive-text="RAG 关" />
      <el-switch v-model="useStream" active-text="流式" inactive-text="直出" />
      <el-divider direction="vertical" />
      <el-icon v-if="loadingSessions" class="is-loading"><loading /></el-icon>
    </div>

    <!-- 消息 -->
    <div class="chat-messages">
      <div v-if="!activeSid" style="color:#6b7280;">请选择或新建一个会话，然后开始对话。</div>
      <template v-else>
        <div v-for="(m, idx) in activeMsgs" :key="idx" class="msg-row" :class="m.role">
          <template v-if="m.role==='assistant'">
            <div class="avatar">A</div>
            <div class="bubble assistant">
              {{ m.content }}
              <div v-if="m.ragRefs && m.ragRefs.length" class="rag-refs">
                <div style="font-weight:600;margin-bottom:4px;">引用来源</div>
                <div class="rag-ref" v-for="(r,i) in m.ragRefs" :key="i">
                  <span style="color:#6b7280;">[{{ r.score }}]</span> {{ r.src }} — {{ r.text?.slice(0,80) }}
                </div>
              </div>
            </div>
          </template>
          <template v-else>
            <div class="bubble user">{{ m.content }}</div>
            <div class="avatar" title="Me">U</div>
          </template>
        </div>
      </template>
    </div>

    <!-- 输入区 -->
    <div class="chat-composer">
      <div class="composer-inner">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="4"
          resize="none"
          placeholder="输入内容，Enter 发送（Shift+Enter 换行）"
          @keydown.enter.exact.prevent="send"
          @keydown.enter.shift.exact.stop
        />
        <el-button class="btn-send" type="success" :loading="sending" @click="send">
          发送
        </el-button>
      </div>
    </div>
  </div>
  `,
};
