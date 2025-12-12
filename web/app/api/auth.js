import { http, setToken } from "./http.js";

export async function loginByPassword(username, password){
    const form = new URLSearchParams();
    form.set("grant_type", "password");
    form.set("username", username);
    form.set("password", password);
    // 与 /docs 的安全方案一致：/api/auth/login
    const resp = await http.post("/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
    });
    const token = resp?.data?.access_token;
    if (token) setToken(token);
    return resp.data;
}

export async function getMe(){
    const resp = await http.get("/auth/me");
    return resp.data;
}

export function logout(){
    setToken("");
}
