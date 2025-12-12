import { http } from "./http.js";

export async function listModels(){
    const resp = await http.get("/models");
    return resp.data || [];
}
