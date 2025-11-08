self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("notificationclick", (event) => {
  const data = (event.notification && event.notification.data) || {};
  const id = data.id;
  const action = event.action;
  event.notification.close();

  if (!id) return;

  // IMPORTANT: SW doesn't know your API base; use same origin backend (Render)
  const API = "https://ai-chatbot-ishk.onrender.com";

  const body = action === "snooze-5" ? { id, snooze_minutes: 5 } : { id };
  event.waitUntil(
    fetch(`${API}/reminders-ack`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).catch(()=>{})
  );
});

self.addEventListener("notificationclose", () => {});
