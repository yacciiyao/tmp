// /web/app/api/http.js
// 依赖全局 <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
const axiosInstance = window.axios.create({
    baseURL: "/api",
    headers: { "Content-Type": "application/json" },
    withCredentials: false,
});

export function getToken() {
    try { return localStorage.getItem("token") || ""; } catch { return ""; }
}

axiosInstance.interceptors.request.use((config) => {
    const t = getToken();
    if (t) config.headers.Authorization = `Bearer ${t}`;
    return config;
});

axiosInstance.interceptors.response.use(
    (resp) => resp,
    (err) => {
        if (err?.response?.status === 401) {
            // 未登录 → 跳登录
            location.hash = "#/login";
        }
        return Promise.reject(err);
    }
);

export const http = axiosInstance;
