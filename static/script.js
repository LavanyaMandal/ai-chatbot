// Clean, stable, externals-ready UI script

document.addEventListener("DOMContentLoaded", () => {

  const $ = id => document.getElementById(id);
  const chatbox = $("chatbox");
  const input = $("userInput");

  const escapeHtml = (s)=> String(s).replace(/[&<>"']/g, m=>(
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]
  ));

  const checked = id => $(id) ? $(id).checked : false;
  const val = (id, fb) => $(id) ? $(id).value : fb;

  // ---------- In-app pretty toast (bottom-right) ----------
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
    snooze.style.background = "#1f2843";
    snooze.style.color = "#dbe3ff";
    snooze.style.border = "1px solid #2b3968";
    snooze.style.borderRadius = "10px";
    snooze.style.padding = "6px 10px";
    snooze.style.cursor = "pointer";

    const done = document.createElement("button");
    done.textContent = "Done";
    done.style.background = "#2f6bff";
    done.style.color = "#fff";
    done.style.border = "none";
    done.style.borderRadius = "10px";
    done.style.padding = "6px 10px";
    done.style.cursor = "pointer";

    row.appendChild(snooze);
    row.appendChild(done);
    card.appendChild(title);
    card.appendChild(txt);
    card.appendChild(row);
    host.appendChild(card);

    snooze.onclick = async ()=>{
      await fetch("/reminders-ack", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ id: rem.id, snooze_minutes: 5 })
      });
      card.remove();
    };
    done.onclick = async ()=>{
      await fetch("/reminders-ack", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ id: rem.id })
      });
      card.remove();
    };
  }
  // --------------------------------------------------------

  // Render messages
  function user(msg){
    chatbox.insertAdjacentHTML("beforeend",
      `<div class="msg user">${escapeHtml(msg)}</div>`);
    chatbox.scrollTop = chatbox.scrollHeight;
  }

  function bot(msg){
    chatbox.insertAdjacentHTML("beforeend",
      `<div class="msg bot">${escapeHtml(msg)}</div>`);
    chatbox.scrollTop = chatbox.scrollHeight;
  }

  function showTyping(){
    chatbox.insertAdjacentHTML("beforeend",
      `<div id="typing" class="msg bot">typing…</div>`);
    chatbox.scrollTop = chatbox.scrollHeight;
  }

  function hideTyping(){
    let t = $("typing");
    if (t) t.remove();
  }

  // Sidebar
  $("openSidebarBtn").onclick = () => {
    $("sidebar").classList.add("show");
    $("overlay").classList.add("show");
  };
  $("closeSidebar").onclick = () => {
    $("sidebar").classList.remove("show");
    $("overlay").classList.remove("show");
  };
  $("overlay").onclick = () => {
    $("sidebar").classList.remove("show");
    $("overlay").classList.remove("show");
  };

  // Theme toggle
  $("themeToggle").onclick = () => {
    const isLight = document.body.classList.toggle("light");
    $("themeToggle").textContent = isLight ? "☀️" : "🌙";
  };

  // MAIN SEND FUNCTION
  async function sendMsg(){
    const text = input.value.trim();
    if (!text) return;

    user(text);
    input.value = "";
    showTyping();

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          message: text,
          voice_enabled: document.getElementById("serverVoiceCheckbox")?.checked || false,
          language: document.getElementById("langSelect")?.value || "auto",
          mode: document.getElementById("modeSelect")?.value || "default"
        })
      });

      const data = await res.json();
      hideTyping();

      if (data.error){
        bot("⚠️ " + data.error);
        return;
      }

      bot(String(data.reply || ""));

      // ✅ Play audio if a URL exists
      if (data.audio_url) {
        try {
          let audio = new Audio(data.audio_url);
          audio.play().catch(err => console.log("Autoplay blocked:", err));
        } catch (err) {
          console.log("Audio play failed:", err);
        }
      }

    } catch (err){
      hideTyping();
      bot("⚠️ Network error.");
    }
  }

  $("sendBtn").onclick = sendMsg;

  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey){
      e.preventDefault();
      sendMsg();
    }
  });

  // New chat
  $("newChat").onclick = async () => {
    showTyping();
    await fetch("/chat", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ message: "clear" })
    });
    hideTyping();
    location.reload();
  };

  // Export / Delete
  $("exportData").onclick = () => window.open("/export-data", "_blank");
  $("deleteData").onclick = async () => {
    await fetch("/delete-data", {method: "DELETE"});
    location.reload();
  };

  // Upload file
  $("uploadBtn").onclick = () => $("fileInput").click();
  $("fileInput").onchange = async ()=>{
    const f = $("fileInput").files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    const endpoint = f.type.startsWith("image") ? "/upload-image" : "/upload-doc";
    showTyping();
    const r = await fetch(endpoint, {method:"POST", body: fd});
    const d = await r.json();
    hideTyping();
    if (d.error) bot("⚠️ " + d.error);
    if (d.message) bot(d.message);
    if (d.analysis) bot(d.analysis);
    if (d.ocr_text) bot("OCR captured.");
  };

  // Speech recognition (UNCHANGED)
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SR && $("micBtn")){
    const rec = new SR();
    rec.lang = "en-IN";
    rec.onresult = e => {
      input.value = e.results[0][0].transcript;
      sendMsg();
    };
    $("micBtn").onclick = ()=> rec.start();
  }

  // Dashboard open
  $("dashboardBtn").onclick = async ()=>{
    $("dashboardModal").classList.remove("hidden");
    $("remList").textContent = "Loading...";
    try{
      const r = await fetch("/dashboard");
      const data = await r.json();
      $("remList").innerHTML = (Array.isArray(data) && data.length)
        ? data.map(x => `✅ ${escapeHtml(x.task || "")}`).join("<br>")
        : "No reminders yet";
    }catch(e){
      $("remList").textContent = "Failed to load reminders.";
    }
  };
  $("closeDash").onclick = () => $("dashboardModal").classList.add("hidden");

  $("addRem").onclick = async ()=>{
    const v = $("newReminder").value.trim();
    if (!v) return;
    try{
      const r = await fetch("/chat", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ message: "remind me " + v })
      });
      const d = await r.json();
      bot(String(d.reply || "Reminder added."));
      $("newReminder").value = "";
    }catch(e){
      bot("⚠️ Could not add reminder.");
    }
  };

  // ---------- OS Notifications + polling (A) ----------
  async function setupNotifications(){
    if (!("serviceWorker" in navigator)) return;

    // register service worker
    try {
      await navigator.serviceWorker.register("/static/sw.js");
    } catch (e) {
      console.log("SW register failed:", e);
    }

    // ask permission
    if (window.Notification && Notification.permission === "default"){
      try { await Notification.requestPermission(); } catch (_) {}
    }

    // polling loop
    async function poll(){
      try{
        const r = await fetch("/reminders-due");
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
            await fetch("/reminders-ack", {
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
  // ----------------------------------------------------

});

// Basic SW for reminder actions
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("notificationclick", (event) => {
  const data = event.notification && event.notification.data || {};
  const id = data.id;
  const action = event.action;

  event.notification.close();

  if (!id) return;

  let body = { id };
  if (action === "snooze-5") {
    body.snooze_minutes = 5;
  }

  event.waitUntil(
    fetch("/reminders-ack", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).catch(()=>{})
  );
});

// optional: clear notifications on close (no network)
self.addEventListener("notificationclose", () => {});
