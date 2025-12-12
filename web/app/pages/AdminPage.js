// web/app/pages/AdminPage.js
import AppTopbar from '../components/AppTopbar.js';
import { listModels, listCorpora, uploadAndIngest } from '../api.js';

const { ref, onMounted } = Vue;
const { ElMessage } = ElementPlus;

export default {
    name: 'AdminPage',
    components: { AppTopbar },
    setup() {
        const activeTab = ref('models');

        // Models
        const models = ref([]);
        async function loadModels() {
            try {
                const data = await listModels();
                models.value = Array.isArray(data) ? data : (data?.items || []);
            } catch (e) {
                console.error(e);
                ElMessage.error('模型列表加载失败');
            }
        }

        // RAG
        const corpora = ref([]);
        const corpusId = ref('');
        const ingesting = ref(false);
        const lastIngest = ref(null);

        async function loadCorpora() {
            try {
                const data = await listCorpora();
                const items = Array.isArray(data) ? data : (data?.items || []);
                corpora.value = items;
                if (!corpusId.value && items.length) corpusId.value = items[0].id;
            } catch (e) {
                console.error(e);
                ElMessage.error('知识库加载失败');
            }
        }

        async function onPickFile(e) {
            const file = e.target.files?.[0];
            if (!file) return;
            if (!corpusId.value) {
                ElMessage.warning('请先选择知识库');
                return;
            }
            ingesting.value = true;
            try {
                const resp = await uploadAndIngest(corpusId.value, file);
                lastIngest.value = resp;
                ElMessage.success('上传并入库完成');
            } catch (e2) {
                console.error(e2);
                ElMessage.error(`入库失败：${e2?.response?.data?.detail || e2.message}`);
            } finally {
                ingesting.value = false;
                e.target.value = '';
            }
        }

        onMounted(async () => {
            await loadModels();
            await loadCorpora();
        });

        return { activeTab, models, corpora, corpusId, ingesting, lastIngest, onPickFile };
    },
    template: `
  <div style="height:100vh;display:flex;flex-direction:column;">
    <app-topbar />
    <div style="padding:12px;">
      <el-card shadow="never">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="模型管理" name="models">
            <el-table :data="models" size="small" border>
              <el-table-column prop="alias" label="Alias" width="220"></el-table-column>
              <el-table-column prop="provider" label="Provider" width="120"></el-table-column>
              <el-table-column prop="model_name" label="Model"></el-table-column>
              <el-table-column prop="is_default" label="默认" width="80">
                <template #default="{row}">
                  <el-tag v-if="row.is_default" type="success" size="small">Yes</el-tag>
                  <el-tag v-else type="info" size="small">No</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="RAG 管理" name="rag">
            <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px;">
              <div>知识库：</div>
              <el-select v-model="corpusId" placeholder="选择知识库" style="width:260px;">
                <el-option v-for="c in corpora" :key="c.id" :value="c.id" :label="c.name" />
              </el-select>

              <input type="file" @change="onPickFile" />
              <el-icon v-if="ingesting" class="is-loading"><loading /></el-icon>
            </div>

            <el-alert v-if="lastIngest" type="success" :closable="false" show-icon>
              <template #title>最近一次入库响应</template>
              <pre style="white-space:pre-wrap;line-height:1.4;">{{ JSON.stringify(lastIngest, null, 2) }}</pre>
            </el-alert>
          </el-tab-pane>

          <el-tab-pane disabled label="Agent（建设中）" name="agents">
            <div style="color:#6b7280;">将来在此管理内部 Agent 配置与测试。</div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>
  </div>
  `,
};
