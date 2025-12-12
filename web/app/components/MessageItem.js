export default {
    name:"MessageItem",
    props:{ msg:{ type:Object, required:true } },
    computed:{
        role(){ return this.msg.role || "assistant"; },
        bubbleClass(){
            const t = (this.msg.parsed_text || this.msg.content_text || "").trim();
            const short = t.length <= 18 && !t.includes("\n");
            return ["bubble", short ? "short" : ""].join(" ");
        },
        avatar(){
            return this.role === "user" ? "/web/assets/user.jpg" : "/web/assets/ai.jpg";
        },
        html(){
            const raw = (this.msg.parsed_text || this.msg.content_text || "").trim();
            const html = window.marked.parse(raw);
            return window.DOMPurify.sanitize(html);
        }
    },
    template: `
    <div class="msg" :class="role">
      <div class="avatar"><img :src="avatar" alt="" /></div>
      <div :class="bubbleClass" v-html="html"></div>
    </div>
  `
};
