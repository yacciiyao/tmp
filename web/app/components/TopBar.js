import { logout } from "../api/auth.js";
import { appState } from "../main.js";

export default {
    name:"TopBar",
    setup(){ return { appState, logout }; },
    template: `
    <div class="app-topbar">
      <div class="brand">
        <img src="/web/assets/logo.svg" alt="logo" />
        <div class="name">Multi-Agent Hub</div>
      </div>
      <div class="userbox">
        <div style="color:var(--muted)">{{ appState.me?.username || "-" }}</div>
        <button class="btn ghost" @click="() => { logout(); location.href='/web/chat.html#/login'; }">退出</button>
      </div>
    </div>
  `
};
