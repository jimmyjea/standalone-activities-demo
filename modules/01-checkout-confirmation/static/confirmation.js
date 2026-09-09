const params = new URLSearchParams(window.location.search);
const orderId = params.get("order_id");
let pollCount = 0;

const byId = (id) => document.getElementById(id);

function secondsUntilDispatch(order) {
  const dispatchAt =
    new Date(order.created_at).getTime() + (order.start_delay_seconds || 10) * 1000;
  return Math.max(0, Math.ceil((dispatchAt - Date.now()) / 1000));
}

function formatDelay(seconds) {
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function renderAttempts(order) {
  if (
    !["webhook-retries", "pause-unpause", "reset", "update-options"].includes(
      order.module,
    )
  )
    return;

  const pauseDemo = order.module === "pause-unpause";
  const resetDemo = order.module === "reset";
  const updateDemo = order.module === "update-options";
  byId("module-title").textContent = pauseDemo
    ? "Pausable Activity"
    : resetDemo
      ? "Resettable Activity"
      : updateDemo
        ? "Updatable Activity"
      : "Retrying webhook";
  byId("retry-panel").classList.remove("hidden");
  const maximumAttempts = updateDemo
    ? order.retry_maximum_attempts
    : pauseDemo || resetDemo
      ? 20
      : 3;
  const currentAttempt = order.temporal_attempt || order.attempts.length;
  const displayedAttempts =
    resetDemo && order.reset_at ? order.previous_attempts : order.attempts;
  byId("attempt-heading").textContent =
    resetDemo && order.reset_at ? "Attempts before reset" : "Webhook attempts";
  byId("attempt-count").textContent =
    resetDemo && order.reset_at
      ? "Reset → attempt 1"
      : `${currentAttempt} / ${maximumAttempts}`;

  const attemptList = byId("attempt-list");
  attemptList.replaceChildren();
  let attemptNumbers = Array.from({ length: maximumAttempts }, (_, index) => index + 1);
  if (pauseDemo || resetDemo || updateDemo) {
    const lastVisible = Math.min(Math.max(currentAttempt + 1, 3), maximumAttempts);
    attemptNumbers = attemptNumbers.slice(Math.max(0, lastVisible - 6), lastVisible);
  }
  for (const number of attemptNumbers) {
    const recorded = displayedAttempts.find((attempt) => attempt.attempt === number);
    const row = document.createElement("div");
    row.className = `attempt ${recorded?.status || "waiting"}`;

    const label = document.createElement("strong");
    label.textContent = `Attempt ${number}`;
    const detail = document.createElement("span");
    detail.textContent = recorded
      ? recorded.status === "delivered"
        ? "200 · Accepted"
        : pauseDemo || resetDemo || updateDemo
          ? "503 · Downstream bug"
          : "503 · Intermittent failure"
      : "Waiting";
    row.append(label, detail);
    attemptList.append(row);
  }
}

function renderOperator(order) {
  if (
    ![
      "pause-unpause",
      "reset",
      "start-delay",
      "update-options",
      "batch-commands",
      "search-attributes",
    ].includes(order.module)
  )
    return;

  byId("operator-panel").classList.remove("hidden");
  byId("activity-step").querySelector("strong").textContent = "Standalone Activity";
  if (order.module === "batch-commands") {
    byId("module-title").textContent = "Batch operator commands";
    byId("operator-panel").querySelector("h2").textContent =
      "10 long-running Activities";
    byId("pause-button").classList.add("hidden");
    byId("unpause-button").classList.add("hidden");
    byId("reset-button").classList.add("hidden");
    byId("cancel-button").classList.add("hidden");
    byId("update-retries-button").classList.add("hidden");
    byId("update-options-help").classList.add("hidden");
    byId("bug-state").classList.add("hidden");
    byId("pause-state").className = order.all_canceled
      ? "paused-pill"
      : "neutral-pill";
    byId("pause-state").textContent = order.all_canceled
      ? "10 Activities canceled"
      : `${order.canceled_count} / 10 Activities canceled`;
    byId("operator-detail").textContent = order.all_canceled
      ? "All 10 Activities observed cancellation through their heartbeats."
      : order.all_cancellation_requested
        ? "Cancellation was requested. Waiting for the next heartbeats."
        : "Select these Activities in Temporal UI and run the batch Cancel action.";

    byId("batch-status").classList.remove("hidden");
    const list = byId("batch-activity-list");
    list.replaceChildren();
    for (const item of order.batch_activities) {
      const row = document.createElement("div");
      const canceled = item.status === 4;
      const cancellationRequested = item.run_state === 3;
      row.className = `batch-activity ${canceled || cancellationRequested ? "cancel-requested" : "running"}`;
      const id = document.createElement("code");
      id.textContent = item.activity_id;
      const state = document.createElement("span");
      state.textContent = canceled
        ? "Canceled"
        : cancellationRequested
          ? "Cancel requested"
          : "Running";
      row.append(id, state);
      list.append(row);
    }

    byId("batch-cli").classList.toggle(
      "hidden",
      !order.all_canceled,
    );
    byId("batch-cli-heading").textContent =
      "Run the same batch cancellation from the CLI:";
    byId("batch-cli-note").classList.add("hidden");
    byId("batch-cli-command").textContent =
      `temporal activity cancel \\\n` +
      `  --query 'ActivityId STARTS_WITH "batch-long-running:${order.id}:"' \\\n` +
      `  --reason "Cancel demo batch" \\\n` +
      `  --yes`;
    return;
  }

  if (order.module === "search-attributes") {
    byId("module-title").textContent = "Search Attributes";
    byId("operator-panel").querySelector("h2").textContent =
      "Mixed Activity executions";
    byId("pause-button").classList.add("hidden");
    byId("unpause-button").classList.add("hidden");
    byId("reset-button").classList.add("hidden");
    byId("cancel-button").classList.add("hidden");
    byId("update-retries-button").classList.add("hidden");
    byId("update-options-help").classList.add("hidden");
    byId("bug-state").className = "fixed-pill";
    byId("bug-state").textContent = `${order.completed_count} completed`;
    byId("pause-state").className = order.all_long_running_canceled
      ? "paused-pill"
      : "neutral-pill";
    byId("pause-state").textContent =
      `${order.canceled_count} / 5 long-running canceled`;
    byId("operator-detail").textContent = order.all_long_running_canceled
      ? "The five long-running Activities received cancellation through heartbeats."
      : "Five Activities completed immediately. Find and cancel the five still running.";

    byId("batch-status").classList.remove("hidden");
    const list = byId("batch-activity-list");
    list.replaceChildren();
    for (const item of order.search_activities) {
      const row = document.createElement("div");
      const canceled = item.status === 4;
      const completed = item.status === 2;
      const cancellationRequested = item.run_state === 3;
      row.className = `batch-activity ${
        completed
          ? "completed"
          : canceled || cancellationRequested
            ? "cancel-requested"
            : "running"
      }`;
      const id = document.createElement("code");
      id.textContent = item.activity_id;
      const state = document.createElement("span");
      state.textContent = completed
        ? "Completed"
        : canceled
          ? "Canceled"
          : cancellationRequested
            ? "Cancel requested"
            : "Running";
      row.append(id, state);
      list.append(row);
    }

    byId("batch-cli").classList.toggle(
      "hidden",
      !order.all_long_running_canceled,
    );
    byId("batch-cli-heading").textContent =
      "Cancel running Activities with a built-in Search Attribute:";
    byId("batch-cli-note").classList.remove("hidden");
    byId("batch-cli-note").textContent =
      "You can also add custom Search Attributes when starting an Activity to filter by business-specific metadata.";
    byId("batch-cli-command").textContent =
      `temporal activity cancel \\\n` +
      `  --query 'ExecutionStatus = "Running"' \\\n` +
      `  --reason "Cancel running Activities" \\\n` +
      `  --yes`;
    return;
  }

  if (order.module === "start-delay") {
    const canCancel =
      order.temporal_status === 1 && !order.activity_started && order.status !== "canceled";
    byId("module-title").textContent = "Delayed Activity";
    byId("operator-panel").querySelector("h2").textContent = "Scheduled confirmation";
    byId("pause-button").classList.add("hidden");
    byId("unpause-button").classList.add("hidden");
    byId("reset-button").classList.add("hidden");
    byId("update-retries-button").classList.add("hidden");
    byId("cancel-button").classList.remove("hidden");
    byId("cancel-button").disabled = !canCancel;
    byId("bug-state").classList.add("hidden");
    byId("pause-state").className = "neutral-pill";
    byId("pause-state").textContent = canCancel
      ? `Starts in ${secondsUntilDispatch(order)}s`
      : order.status === "canceled"
        ? "Canceled"
        : "Activity started";
    byId("operator-detail").textContent = canCancel
      ? "The Activity is durably scheduled but has not been dispatched to a Worker."
      : order.status === "canceled"
        ? "Temporal canceled the Activity before any Worker executed it."
        : "The start delay elapsed and a Worker received the Activity.";
    return;
  }

  if (order.module === "update-options") {
    const canUpdate =
      order.temporal_status === 1 &&
      !order.retry_updated_at;
    byId("module-title").textContent = "Updatable Activity";
    byId("operator-panel").querySelector("h2").textContent = "Retry policy";
    byId("pause-button").classList.add("hidden");
    byId("unpause-button").classList.add("hidden");
    byId("reset-button").classList.add("hidden");
    byId("cancel-button").classList.add("hidden");
    byId("update-retries-button").classList.remove("hidden");
    byId("update-retries-button").disabled = !canUpdate;
    byId("update-options-help").classList.toggle(
      "hidden",
      !order.retry_updated_at,
    );
    byId("bug-state").className = "incident-pill";
    byId("bug-state").textContent = "● Downstream unavailable";
    byId("pause-state").className = order.retry_updated_at
      ? "fixed-pill"
      : "neutral-pill";
    byId("pause-state").textContent =
      `Maximum attempts · ${order.retry_maximum_attempts}`;
    byId("operator-detail").textContent = order.retry_updated_at
      ? "Temporal updated the running Activity's retry policy to stop after five attempts."
      : "The Activity can retry 20 times. Reduce the maximum attempts to five.";
    return;
  }

  if (order.module === "reset") {
    const readyToReset =
      order.attempts.length > 0 && order.temporal_status === 1 && !order.reset_at;
    byId("operator-panel").querySelector("h2").textContent = "Downstream system issue";
    byId("pause-button").classList.add("hidden");
    byId("unpause-button").classList.add("hidden");
    byId("reset-button").classList.remove("hidden");
    byId("reset-button").disabled = !readyToReset || order.status === "delivered";
    byId("bug-state").className = order.bug_fixed ? "fixed-pill" : "incident-pill";
    byId("bug-state").textContent = order.bug_fixed ? "✓ Bug fixed" : "● Bug active";
    byId("pause-state").className = readyToReset ? "incident-pill" : "neutral-pill";
    byId("pause-state").textContent = readyToReset
      ? `${order.attempts.length} failed attempt${order.attempts.length > 1 ? "s" : ""} · retrying`
      : order.reset_at
        ? "Reset · 5-second call"
        : "Activity running";
    byId("operator-detail").textContent = readyToReset
      ? "The downstream issue is causing retries. Deploy the fix and reset running Activities."
      : order.reset_at
        ? "Temporal reset the same Activity Execution; the repaired call takes five seconds."
        : "Waiting for the first failed attempt.";
    return;
  }

  const paused = Boolean(order.paused);
  const bugFixed = Boolean(order.bug_fixed);

  byId("bug-state").className = bugFixed ? "fixed-pill" : "incident-pill";
  byId("bug-state").textContent = bugFixed ? "✓ Bug fixed" : "● Bug active";
  byId("pause-state").className = paused ? "paused-pill" : "neutral-pill";
  byId("pause-state").textContent = paused ? "Ⅱ Activity paused" : "Activity running";
  byId("pause-button").disabled = paused || bugFixed || order.status === "delivered";
  byId("unpause-button").disabled = !paused || !bugFixed || order.status === "delivered";

  if (paused && bugFixed) {
    byId("operator-detail").textContent =
      "Temporal has paused retry dispatch. The downstream bug is fixed and ready to test.";
  } else if (bugFixed) {
    byId("operator-detail").textContent =
      "The bug is fixed. Temporal is dispatching the Activity again.";
  }
}

function render(order) {
  byId("order-id").textContent = order.id;
  byId("customer-name").textContent = order.customer_name.split(" ")[0];
  byId("activity-id").textContent = order.activity_id;
  renderAttempts(order);
  renderOperator(order);

  if (order.module === "batch-commands") {
    byId("payment-accepted-card").classList.add("hidden");
    document
      .querySelector(".confirmation-layout")
      .classList.add("batch-confirmation");
    const badge = byId("status-badge");
    badge.className = order.all_canceled
      ? "status-badge paused"
      : "status-badge queued";
    badge.textContent = order.all_canceled
      ? "10 Activities canceled"
      : "10 Activities running";
    byId("activity-step").className = "active";
    byId("webhook-step").querySelector("strong").textContent = "Batch cancellation";
    byId("webhook-step").querySelector("small").textContent =
      `${order.canceled_count} of 10 canceled`;
    byId("status-detail").textContent = order.all_canceled
      ? "Each Activity heartbeat received the cancellation and stopped its running work."
      : order.all_cancellation_requested
        ? "Cancellation requested; heartbeats are moving the Activities to Canceled."
        : "Use Temporal UI to select all 10 Activities and request cancellation.";
    return order.all_canceled;
  }

  if (order.module === "search-attributes") {
    byId("payment-accepted-card").classList.add("hidden");
    document
      .querySelector(".confirmation-layout")
      .classList.add("batch-confirmation");
    const badge = byId("status-badge");
    badge.className = order.all_long_running_canceled
      ? "status-badge paused"
      : "status-badge queued";
    badge.textContent = order.all_long_running_canceled
      ? "Search complete"
      : `${order.completed_count} completed · ${10 - order.completed_count - order.canceled_count} running`;
    byId("activity-step").className = "active";
    byId("webhook-step").querySelector("strong").textContent =
      "Search Attribute filter";
    byId("webhook-step").querySelector("small").textContent =
      'ExecutionStatus = "Running"';
    byId("status-detail").textContent = order.all_long_running_canceled
      ? "The running executions were identified and canceled."
      : "Use the ExecutionStatus Search Attribute to find the five running Activities.";
    return order.all_long_running_canceled;
  }

  if (order.status === "canceled" || order.temporal_status === 4) {
    const badge = byId("status-badge");
    badge.className = "status-badge canceled";
    badge.textContent = "Canceled";
    byId("activity-step").className = "canceled";
    byId("webhook-step").querySelector("small").textContent = "No webhook sent";
    byId("status-detail").textContent =
      "The delayed Activity was canceled before it reached a Worker.";
    return true;
  }

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
        : order.module === "reset"
          ? "The operator repaired and reset the running Activity; the reset attempt completed."
        : "The Worker completed the Activity and the idempotent webhook recorded its receipt.";
    return true;
  }

  if (order.module === "update-options" && order.temporal_status === 3) {
    const badge = byId("status-badge");
    badge.className = "status-badge failed";
    badge.textContent = "Attempts exhausted";
    byId("activity-step").className = "failed";
    byId("webhook-step").querySelector("small").textContent =
      `${order.attempts.length} failed webhook calls`;
    byId("status-detail").textContent =
      "Temporal stopped retrying after reaching the updated maximum of five attempts.";
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
  if (order.module === "start-delay") {
    const badge = byId("status-badge");
    if (order.activity_started) {
      badge.className = "status-badge queued";
      badge.innerHTML = '<span class="spinner"></span> Processing';
      byId("status-detail").textContent =
        `The ${formatDelay(order.start_delay_seconds || 10)} start delay elapsed and Temporal dispatched the Activity.`;
    } else {
      const seconds = secondsUntilDispatch(order);
      badge.className = "status-badge queued";
      badge.textContent = `Scheduled · ${formatDelay(seconds)}`;
      byId("status-detail").textContent =
        "Cancel now, or Temporal will dispatch the confirmation when the delay expires.";
    }
    return false;
  }

  if (order.module === "update-options") {
    const badge = byId("status-badge");
    badge.className = "status-badge queued";
    badge.innerHTML =
      `<span class="spinner"></span> Retrying · attempt ${order.temporal_attempt}`;
    byId("webhook-step").className = "active";
    byId("webhook-step").querySelector("small").textContent =
      `${failedAttempts.length} failed webhook call${failedAttempts.length === 1 ? "" : "s"}`;
    byId("status-detail").textContent = order.retry_updated_at
      ? "Temporal is applying the updated five-attempt limit to this running Activity."
      : "The downstream issue is failing every attempt; the current policy allows 20 attempts.";
    return false;
  }

  if (order.module === "reset") {
    const badge = byId("status-badge");
    badge.className = "status-badge queued";
    badge.innerHTML = order.reset_at
      ? '<span class="spinner"></span> Reset · completing'
      : `<span class="spinner"></span> Retrying · attempt ${failedAttempts.length + 1}`;
    byId("status-detail").textContent = order.reset_at
      ? "Temporal reset the attempt count and dispatched the repaired Activity."
      : "The downstream issue is causing an HTTP 503 on every attempt.";
    return false;
  }

  if (order.module === "pause-unpause") {
    const badge = byId("status-badge");
    if (order.paused) {
      badge.className = "status-badge paused";
      badge.textContent = "Ⅱ Paused";
      byId("status-detail").textContent =
        "Temporal is holding the next retry until an operator unpauses the Activity.";
    } else {
      badge.className = "status-badge queued";
      badge.innerHTML = '<span class="spinner"></span> Retrying';
      byId("status-detail").textContent =
        failedAttempts.length > 0
          ? "The downstream bug is causing an HTTP 503 on every attempt."
          : "The Standalone Activity is starting…";
    }
    return false;
  }

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

async function operatorAction(action) {
  const button = byId(`${action}-button`);
  const originalText = button.textContent;
  byId("operator-error").textContent = "";
  button.disabled = true;
  button.textContent =
    action === "pause"
      ? "Pausing…"
      : action === "reset"
        ? "Resetting…"
        : action === "cancel"
          ? "Canceling…"
          : action === "update-retries"
            ? "Updating…"
          : "Unpausing…";
  try {
    const response = await fetch(
      `/api/orders/${encodeURIComponent(orderId)}/${action}`,
      { method: "POST" },
    );
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.detail || `Could not ${action} the Activity.`);
    }
  } catch (error) {
    byId("operator-error").textContent = error.message;
    button.disabled = false;
  } finally {
    button.textContent = originalText;
  }
}

byId("pause-button").addEventListener("click", () => operatorAction("pause"));
byId("unpause-button").addEventListener("click", () => operatorAction("unpause"));
byId("reset-button").addEventListener("click", () => operatorAction("reset"));
byId("cancel-button").addEventListener("click", () => operatorAction("cancel"));
byId("update-retries-button").addEventListener("click", () =>
  operatorAction("update-retries"),
);

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
