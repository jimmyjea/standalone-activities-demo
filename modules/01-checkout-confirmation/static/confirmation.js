const params = new URLSearchParams(window.location.search);
const orderId = params.get("order_id");
let pollCount = 0;

const byId = (id) => document.getElementById(id);

function renderAttempts(order) {
  if (order.module !== "webhook-retries") return;

  byId("module-title").textContent = "Retrying webhook";
  byId("retry-panel").classList.remove("hidden");
  byId("attempt-count").textContent = `${order.attempts.length} / 3`;

  const attemptList = byId("attempt-list");
  attemptList.replaceChildren();
  for (let number = 1; number <= 3; number += 1) {
    const recorded = order.attempts.find((attempt) => attempt.attempt === number);
    const row = document.createElement("div");
    row.className = `attempt ${recorded?.status || "waiting"}`;

    const label = document.createElement("strong");
    label.textContent = `Attempt ${number}`;
    const detail = document.createElement("span");
    detail.textContent = recorded
      ? recorded.status === "delivered"
        ? "200 · Accepted"
        : "503 · Intermittent failure"
      : "Waiting";
    row.append(label, detail);
    attemptList.append(row);
  }
}

function render(order) {
  byId("order-id").textContent = order.id;
  byId("customer-name").textContent = order.customer_name.split(" ")[0];
  byId("activity-id").textContent = order.activity_id;
  renderAttempts(order);

  if (order.status === "delivered") {
    const badge = byId("status-badge");
    badge.className = "status-badge delivered";
    badge.innerHTML = "✓ Delivered";
    byId("activity-step").className = "complete";
    byId("webhook-step").className = "complete";
    byId("webhook-step").querySelector("small").textContent = "Receipt acknowledged";
    byId("email-subject").textContent = order.subject;
    byId("email-message").textContent = order.message;
    byId("provider-id").textContent = order.provider_message_id;
    byId("delivered-at").textContent = new Date(order.delivered_at).toLocaleTimeString();
    byId("inbox").classList.remove("hidden");
    byId("status-detail").textContent =
      order.module === "webhook-retries"
        ? "Attempts 1 and 2 failed with HTTP 503. Temporal retried and attempt 3 delivered."
        : "The Worker completed the Activity and the idempotent webhook recorded its receipt.";
    return true;
  }

  if (order.status === "scheduling_failed") {
    const badge = byId("status-badge");
    badge.className = "status-badge failed";
    badge.textContent = "Scheduling failed";
    byId("status-detail").textContent = order.error;
    return true;
  }

  const failedAttempts = order.attempts.filter((attempt) => attempt.status === "failed");
  if (failedAttempts.length) {
    byId("status-badge").lastChild.textContent =
      ` Retrying · attempt ${failedAttempts.length + 1}`;
    byId("webhook-step").className = "active";
    byId("webhook-step").querySelector("small").textContent =
      `${failedAttempts.length} failed webhook call${failedAttempts.length > 1 ? "s" : ""}`;
    byId("status-detail").textContent =
      "The HTTP error escaped the Activity, so Temporal scheduled the next attempt.";
  } else {
    byId("status-badge").lastChild.textContent = " Processing";
    byId("status-detail").textContent =
      pollCount > 3
        ? "The job is durable and waiting. Make sure the confirmation Worker is running."
        : "Checkout returned immediately. A Worker is processing the durable job…";
  }
  return false;
}

async function poll() {
  if (!orderId) {
    byId("status-detail").textContent = "No order ID was provided.";
    return;
  }

  try {
    const response = await fetch(`/api/orders/${encodeURIComponent(orderId)}`);
    if (!response.ok) throw new Error("Order status is unavailable.");
    pollCount += 1;
    if (!render(await response.json())) {
      window.setTimeout(poll, 800);
    }
  } catch (error) {
    byId("status-detail").textContent = error.message;
    window.setTimeout(poll, 1500);
  }
}

poll();
