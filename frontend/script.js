// Clean, stable, externals-ready UI script
const API = "https://ai-chatbot-ishk.onrender.com";

document.addEventListener("DOMContentLoaded", () => {
  const $ = id => document.getElementById(id);
  const chatbox = $("chatbox");
  const input = $("userInput");

  const escapeHtml = (s)=> String(s).replace(/[&<>"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const checked = id => $(id) ? $(id).checked : false;

  function ensureToastHost(){
    if ($("toastHost")) return $("toastHost");
    const host = document.createElement("div");
    host.id = "toastHost";
    host.style.position = "fixed";
    host.style.right = "18px";
    host.style.bottom = "18px";
    host.style.display = "grid";
    host.style.gap = "10px";
    host.style.zIndex = "1000";
    document.body.appendChild(host);
    return host;
  }

  function showReminderToast(rem){
    const host = ensureToastHost();
    const card = document.createElement("div");
    card.className = "toast-card";
    card.style.background = "linear-gradient(135deg,#151826,#0e1222)";
    card.style.border = "1px solid #2a2f45";
    card.style.color = "#e7e9ee";
    card.style.borderRadius = "14px";
    card.style.padding = "12px 14px";
    card.style.minWidth = "260px";
    card.style.boxShadow = "0 8px 24px rgba(0,0,0,.35)";
    card.style.fontSize = "14px";

    const title = document.createElement("div");
    title.style.fontWeight = "600";
    title.style.marginBottom = "6px";
    title.textContent = "⏰ Reminder";

    const txt = document.createElement("div");
    txt.style.opacity = ".95";
    txt.style.marginBottom = "10px";
    txt.textContent = (rem.task || "").replace(/^remind( me)?/i,"").trim() || rem.task || "Reminder";

    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.gap = "8px";
    row.style.justifyContent = "flex-end";

    const snooze = document.createElement("button");
    snooze.textContent = "Snooze 5 min";
    snooze.className = "btn-snooze";

    const done = document.createElement("button");
    done.textContent = "Done";
    done.className = "btn-done";

    row.appendChild(snooze);
    row.appendChild(done);
    card.appendChild(title);
    card.appendChild(txt);
    card.appendChild(row);
    host.appendChild(card);

    snooze.onclick = async ()=>{
      await fetch(`${API}/reminders-ack`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ id: rem.id, snooze_minutes: 5 })
      });
      card.remove();
    };
    done.onclick = async ()=>{
      await fetch(`${API}/reminders-ack`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ id: rem.id })
      });
      card.remove();
    };
  }

  function user(msg){
    chatbox.insertAdjacentHTML("beforeend", `<div class="msg user">${escapeHtml(msg)}</div>`);
    chatbox.scrollTop = chatbox.scrollHeight;
  }
  function bot(msg){
    chatbox.insertAdjacentHTML("beforeend", `<div class="msg bot">${escapeHtml(msg)}</div>`);
    chatbox.scrollTop = chatbox.scrollHeight;
  }
  function showTyping(){
    chatbox.insertAdjacentHTML("beforeend", `<div id="typing" class="msg bot">typing…</div>`);
    chatbox.scrollTop = chatbox.scrollHeight;
  }
  function hideTyping(){
    const t = document.getElementById("typing");
    if (t) t.remove();
  }

  // Sidebar
  $("openSidebarBtn").onclick = () => { $("sidebar").classList.add("show"); $("overlay").classList.add("show"); };
  $("closeSidebar").onclick = () => { $("sidebar").classList.remove("show"); $("overlay").classList.remove("show"); };
  $("overlay").onclick = () => { $("sidebar").classList.remove("show"); $("overlay").classList.remove("show"); };

  // Theme toggle
  $("themeToggle").onclick = () => {
    const isLight = document.body.classList.toggle("light");
    $("themeToggle").textContent = isLight ? "☀️" : "🌙";
  };

  // Send
  async function sendMsg(){
    const text = input.value.trim();
    if (!text) return;
    user(text); input.value = ""; showTyping();

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          message: text,
          voice_enabled: document.getElementById("serverVoiceCheckbox")?.checked || false,
          language: document.getElementById("langSelect")?.value || "auto",
          mode: document.getElementById("modeSelect")?.value || "default"
        })
      });
      const data = await res.json(); hideTyping();

      if (data.error){ bot("⚠️ " + data.error); return; }
      bot(String(data.reply || ""));

      if (data.audio_url) {
        try {
          const audio = new Audio(data.audio_url);
          await audio.play();
        } catch (err) {
          console.log("Audio autoplay blocked:", err);
        }
      }
    } catch (err){
      hideTyping(); bot("⚠️ Network error.");
    }
  }

  document.getElementById("sendBtn").onclick = sendMsg;
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey){ e.preventDefault(); sendMsg(); }
  });

  // New chat
  document.getElementById("newChat").onclick = async () => {
    showTyping();
    await fetch(`${API}/chat`, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ message: "clear" }) });
    hideTyping(); location.reload();
  };

  // Export / Delete
  document.getElementById("exportData").onclick = () => window.open(`${API}/export-data`, "_blank");
  document.getElementById("deleteData").onclick = async () => { await fetch(`${API}/delete-data`, {method: "DELETE"}); location.reload(); };

  // Upload
  document.getElementById("uploadBtn").onclick = () => document.getElementById("fileInput").click();
  document.getElementById("fileInput").onchange = async ()=>{
    const f = document.getElementById("fileInput").files[0];
    if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    const endpoint = f.type.startsWith("image") ? `${API}/upload-image` : `${API}/upload-doc`;
    showTyping();
    const r = await fetch(endpoint, {method:"POST", body: fd});
    const d = await r.json(); hideTyping();
    if (d.error) bot("⚠️ " + d.error);
    if (d.message) bot(d.message);
    if (d.analysis) bot(d.analysis);
    if (d.ocr_text) bot("OCR captured.");
  };

  // Speech recognition (page mic)
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SR && document.getElementById("micBtn")){
    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = e => { input.value = e.results[0][0].transcript; sendMsg(); };
    rec.onerror = e => { bot("🎙️ Mic error: " + (e.error || "unknown")); };
    document.getElementById("micBtn").onclick = ()=> rec.start();
  } else {
    // Non-supported browsers
    // bot("🎙️ Voice input not supported in this browser.");
  }

  // OS Notifications + polling via Service Worker
  async function setupNotifications(){
    if (!("serviceWorker" in navigator)) return;

    try {
      // IMPORTANT: we must have /static/sw.js file on server
      await navigator.serviceWorker.register("/static/sw.js");
    } catch (e) {
      console.log("SW register failed", e);
    }

    if (window.Notification && Notification.permission === "default"){
      try { await Notification.requestPermission(); } catch (_) {}
    }

    async function poll(){
      try{
        const r = await fetch(`${API}/reminders-due`);
        if (!r.ok) throw new Error("HTTP "+r.status);
        const due = await r.json();
        if (Array.isArray(due) && due.length){
          const reg = await navigator.serviceWorker.getRegistration();
          for (const rem of due){
            if (reg && Notification.permission === "granted"){
              reg.showNotification("⏰ Reminder", {
                body: (rem.task || "").replace(/^remind( me)?/i,"").trim() || rem.task,
                tag: rem.id,
                data: { id: rem.id },
                requireInteraction: true,
                actions: [
                  { action: "snooze-5", title: "Snooze 5 min" },
                  { action: "done",      title: "Done" }
                ]
              });
            }
            showReminderToast(rem);
            await fetch(`${API}/reminders-ack`, {
              method:"POST",
              headers:{"Content-Type":"application/json"},
              body: JSON.stringify({ id: rem.id })
            });
          }
        }
      }catch(e){
        // silent
      }finally{
        setTimeout(poll, 15000);
      }
    }
    poll();
  }
  setupNotifications();
});
