const state = {
  mode: "demo",
  items: [],
  loans: [],
  chatRooms: [],
  chatMessages: [],
  onlineUsers: 0,
  roomUsers: 0,
  connectedClients: 0,
  activityEvents: [],
  currentSenderName: localStorage.getItem("chat-sender-name") || "",
  currentSenderRole: localStorage.getItem("chat-sender-role") || "pengguna",
  activeChatRoomId: localStorage.getItem("chat-room-id") || "general",
  typingName: "",
  lastLiveUpdateText: "Menunggu sinkronisasi realtime...",
  stats: {
    totalItems: 0,
    activeLoans: 0,
    overdueLoans: 0,
    itemsReady: 0,
    returnedToday: 0,
  },
  selectedLoanId: "",
};

let socket = null;
let typingTimeoutId = null;
let typingClearTimeoutId = null;

const elements = {
  itemSelect: document.querySelector("#itemSelect"),
  itemsTableBody: document.querySelector("#itemsTableBody"),
  loansTableBody: document.querySelector("#loansTableBody"),
  loanForm: document.querySelector("#loanForm"),
  returnForm: document.querySelector("#returnForm"),
  returnSummary: document.querySelector("#returnSummary"),
  returnLoanId: document.querySelector("#returnLoanId"),
  loanSubmitButton: document.querySelector("#loanSubmitButton"),
  returnSubmitButton: document.querySelector("#returnSubmitButton"),
  searchInput: document.querySelector("#searchInput"),
  statusFilter: document.querySelector("#statusFilter"),
  modeBadge: document.querySelector("#modeBadge"),
  modeDescription: document.querySelector("#modeDescription"),
  toast: document.querySelector("#toast"),
  loanDateInput: document.querySelector("#loanDateInput"),
  dueDateInput: document.querySelector("#dueDateInput"),
  returnedAtInput: document.querySelector("#returnedAtInput"),
  statTotalItems: document.querySelector("#statTotalItems"),
  statActiveLoans: document.querySelector("#statActiveLoans"),
  statItemsReady: document.querySelector("#statItemsReady"),
  statOverdueLoans: document.querySelector("#statOverdueLoans"),
  miniTotalItems: document.querySelector("#miniTotalItems"),
  miniActiveLoans: document.querySelector("#miniActiveLoans"),
  chatFeed: document.querySelector("#chatFeed"),
  chatForm: document.querySelector("#chatForm"),
  chatSenderInput: document.querySelector("#chatSenderInput"),
  chatRoleSelect: document.querySelector("#chatRoleSelect"),
  chatRoleBanner: document.querySelector("#chatRoleBanner"),
  chatRoomSelect: document.querySelector("#chatRoomSelect"),
  chatRoomTitle: document.querySelector("#chatRoomTitle"),
  chatRoomSubtitle: document.querySelector("#chatRoomSubtitle"),
  chatMessageInput: document.querySelector("#chatMessageInput"),
  chatSubmitButton: document.querySelector("#chatSubmitButton"),
  chatConnectionBadge: document.querySelector("#chatConnectionBadge"),
  chatPresenceText: document.querySelector("#chatPresenceText"),
  chatTypingIndicator: document.querySelector("#chatTypingIndicator"),
  chatHelperText: document.querySelector("#chatHelperText"),
  activityFeed: document.querySelector("#activityFeed"),
  liveClientCount: document.querySelector("#liveClientCount"),
  liveUpdateText: document.querySelector("#liveUpdateText"),
};

window.addEventListener("DOMContentLoaded", () => {
  setDefaultDates();
  primeChatIdentity();
  wireEvents();
  bootstrap();
  connectChat();
});

function wireEvents() {
  elements.loanForm.addEventListener("submit", onLoanSubmit);
  elements.returnForm.addEventListener("submit", onReturnSubmit);
  elements.searchInput.addEventListener("input", renderLoans);
  elements.statusFilter.addEventListener("change", renderLoans);
  elements.chatForm.addEventListener("submit", onChatSubmit);
  elements.chatSenderInput.addEventListener("input", onChatIdentityChange);
  elements.chatRoleSelect.addEventListener("change", onChatIdentityChange);
  elements.chatRoomSelect.addEventListener("change", onChatRoomChange);
  elements.chatMessageInput.addEventListener("input", onChatTyping);
  elements.loansTableBody.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-loan-id]");

    if (!trigger) {
      return;
    }

    const loanId = trigger.getAttribute("data-loan-id");
    selectLoan(loanId);
  });
}

async function bootstrap() {
  try {
    const snapshot = await api("/api/bootstrap");
    hydrateState(snapshot);
    renderAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

function hydrateState(snapshot) {
  state.mode = snapshot.mode;
  state.items = snapshot.items;
  state.loans = snapshot.loans;
  state.stats = snapshot.stats;
  state.chatRooms = snapshot.chat?.rooms || [];
  state.chatMessages = snapshot.chat?.messages || state.chatMessages;
  state.onlineUsers = snapshot.chat?.onlineUsers ?? state.onlineUsers;
  state.connectedClients =
    snapshot.realtime?.connectedClients ?? state.connectedClients;
  state.activityEvents = snapshot.realtime?.activities || state.activityEvents;

  if (state.selectedLoanId) {
    const stillExists = state.loans.some(
      (loan) => loan.loanId === state.selectedLoanId && loan.status !== "Dikembalikan",
    );

    if (!stillExists) {
      state.selectedLoanId = "";
    }
  }

  if (!state.chatRooms.some((room) => room.id === state.activeChatRoomId)) {
    state.activeChatRoomId = "general";
  }
}

function renderAll() {
  renderModeBadge();
  renderStats();
  renderItems();
  renderLoans();
  renderItemSelect();
  renderReturnSummary();
  renderChatRooms();
  renderChat();
  renderActivities();
}

function renderModeBadge() {
  const usingGoogleSheet = state.mode === "google-sheets";
  elements.modeBadge.textContent = usingGoogleSheet ? "Google Sheet aktif" : "Mode demo";
  elements.modeDescription.textContent = usingGoogleSheet
    ? "Server sudah membaca dan menulis data ke spreadsheet Google Sheet kamu."
    : "Server berjalan dengan data demo lokal. Hubungkan spreadsheet dan service account untuk mode produksi.";
}

function renderStats() {
  elements.statTotalItems.textContent = state.stats.totalItems;
  elements.statActiveLoans.textContent = state.stats.activeLoans;
  elements.statItemsReady.textContent = state.stats.itemsReady;
  elements.statOverdueLoans.textContent = state.stats.overdueLoans;
  elements.miniTotalItems.textContent = state.stats.totalItems;
  elements.miniActiveLoans.textContent = state.stats.activeLoans;
}

function renderItems() {
  if (state.items.length === 0) {
    elements.itemsTableBody.innerHTML =
      '<tr><td colspan="5" class="empty-state">Belum ada data inventaris.</td></tr>';
    return;
  }

  elements.itemsTableBody.innerHTML = state.items
    .map((item) => {
      const stockClass = item.stockAvailable < 2 ? "low" : "good";

      return `
        <tr>
          <td><strong>${escapeHtml(item.id)}</strong></td>
          <td>
            <div class="item-title">
              <strong>${escapeHtml(item.name)}</strong>
              <small>${escapeHtml(item.notes || "Siap digunakan untuk kegiatan operasional")}</small>
            </div>
          </td>
          <td>${escapeHtml(item.category || "-")}</td>
          <td>${escapeHtml(item.location || "-")}</td>
          <td><span class="stock-badge ${stockClass}">${item.stockAvailable}/${item.stockTotal}</span></td>
        </tr>
      `;
    })
    .join("");
}

function renderItemSelect() {
  const options = state.items
    .map((item) => {
      const disabled = item.stockAvailable < 1 ? "disabled" : "";
      const label = `${item.name} (${item.stockAvailable}/${item.stockTotal} tersedia)`;

      return `<option value="${escapeHtml(item.id)}" ${disabled}>${escapeHtml(label)}</option>`;
    })
    .join("");

  elements.itemSelect.innerHTML = `<option value="">Pilih barang</option>${options}`;
}

function renderLoans() {
  const keyword = elements.searchInput.value.trim().toLowerCase();
  const status = elements.statusFilter.value;

  const filteredLoans = state.loans.filter((loan) => {
    const matchesKeyword =
      !keyword ||
      [loan.loanId, loan.borrowerName, loan.itemName, loan.borrowerId]
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    const matchesStatus = status === "Semua" || loan.status === status;
    return matchesKeyword && matchesStatus;
  });

  if (filteredLoans.length === 0) {
    elements.loansTableBody.innerHTML =
      '<tr><td colspan="6" class="empty-state">Tidak ada data yang cocok dengan filter saat ini.</td></tr>';
    return;
  }

  elements.loansTableBody.innerHTML = filteredLoans
    .map((loan) => {
      const canReturn = loan.status !== "Dikembalikan";
      const actionClass = canReturn ? "" : "is-disabled";
      const statusClass = loan.status.toLowerCase();
      const dateLabel = `${formatDate(loan.loanDate)} - ${formatDate(loan.dueDate)}`;
      const actionText = canReturn ? "Proses kembali" : "Selesai";

      return `
        <tr>
          <td><strong>${escapeHtml(loan.loanId)}</strong></td>
          <td>
            <div class="borrower-meta">
              <strong>${escapeHtml(loan.borrowerName)}</strong>
              <small>${escapeHtml(loan.borrowerId)} - ${escapeHtml(loan.department)}</small>
            </div>
          </td>
          <td>
            <div class="item-status">
              <strong>${escapeHtml(loan.itemName)}</strong>
              <small>${loan.quantity} unit - ${escapeHtml(loan.purpose)}</small>
            </div>
          </td>
          <td>${escapeHtml(dateLabel)}</td>
          <td><span class="status-pill ${statusClass}">${escapeHtml(loan.status)}</span></td>
          <td>
            <button class="loan-action ${actionClass}" data-loan-id="${escapeHtml(loan.loanId)}">
              ${actionText}
            </button>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderReturnSummary() {
  const selectedLoan = state.loans.find((loan) => loan.loanId === state.selectedLoanId);

  if (!selectedLoan) {
    elements.returnSummary.innerHTML = `
      <strong>Belum ada transaksi dipilih</strong>
      <p>Pilih tombol <em>Proses kembali</em> pada daftar peminjaman aktif.</p>
    `;
    elements.returnLoanId.value = "";
    return;
  }

  elements.returnLoanId.value = selectedLoan.loanId;
  elements.returnSummary.innerHTML = `
    <strong>${escapeHtml(selectedLoan.borrowerName)} - ${escapeHtml(selectedLoan.loanId)}</strong>
    <p>
      ${escapeHtml(selectedLoan.itemName)} sebanyak ${selectedLoan.quantity} unit.
      Batas kembali ${escapeHtml(formatDate(selectedLoan.dueDate))}.
    </p>
  `;
}

function renderChatRooms() {
  const options = state.chatRooms
    .map((room) => {
      const label = `${room.label} - ${room.subtitle || room.type}`;
      const selected = room.id === state.activeChatRoomId ? "selected" : "";
      return `<option value="${escapeHtml(room.id)}" ${selected}>${escapeHtml(label)}</option>`;
    })
    .join("");

  elements.chatRoomSelect.innerHTML =
    options || '<option value="general">Chat Umum - Untuk pertanyaan umum seputar peminjaman.</option>';

  const activeRoom = getActiveChatRoom();
  elements.chatRoomTitle.textContent = activeRoom.label;
  elements.chatRoomSubtitle.textContent = activeRoom.subtitle;
}

function renderChat() {
  const sortedMessages = [...state.chatMessages]
    .filter((message) => (message.roomId || "general") === state.activeChatRoomId)
    .sort((left, right) => {
      return new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime();
    });
  const activeRoom = getActiveChatRoom();
  const isAdmin = state.currentSenderRole === "admin";

  elements.chatConnectionBadge.textContent = socket?.connected
    ? "Socket terhubung"
    : "Menyambung...";
  elements.chatConnectionBadge.classList.toggle("connected", Boolean(socket?.connected));
  elements.chatPresenceText.textContent = `${state.onlineUsers} online • ${state.roomUsers} di room ini`;
  elements.chatTypingIndicator.textContent = state.typingName
    ? `${state.typingName} sedang mengetik...`
    : "";
  elements.chatHelperText.textContent = `Pesan akan dikirim ke room ${activeRoom.label}.`;
  elements.chatRoleBanner.textContent = isAdmin
    ? `Mode admin aktif. Kamu sedang memantau ${activeRoom.label} dan bisa memberi arahan cepat ke peminjam.`
    : `Mode pengguna aktif. Kamu sedang berada di ${activeRoom.label} untuk tanya stok, loan, atau pengembalian.`;
  document.body.dataset.chatRole = state.currentSenderRole;
  elements.chatMessageInput.placeholder = isAdmin
    ? `Tulis update admin untuk ${activeRoom.label}...`
    : `Tulis pertanyaanmu di ${activeRoom.label}...`;

  if (sortedMessages.length === 0) {
    elements.chatFeed.innerHTML =
      '<div class="empty-state">Belum ada pesan di room ini. Mulai percakapan dari panel ini.</div>';
    return;
  }

  elements.chatFeed.innerHTML = sortedMessages
    .map((message) => {
      const isSelf = normalizeSenderName(state.currentSenderName) === message.senderName;
      const roleClass = message.senderRole === "admin" ? "is-admin" : "";
      const selfClass = isSelf ? "is-self" : "";
      const roleLabel = message.senderRole === "admin" ? "Admin Lab" : "Pengguna";

      return `
        <article class="chat-message ${roleClass} ${selfClass}">
          <div class="chat-message-header">
            <strong>${escapeHtml(message.senderName)} <span>(${escapeHtml(roleLabel)})</span></strong>
            <span>${escapeHtml(formatDateTime(message.createdAt))}</span>
          </div>
          <p>${escapeHtml(message.message)}</p>
        </article>
      `;
    })
    .join("");

  elements.chatFeed.scrollTop = elements.chatFeed.scrollHeight;
}

function renderActivities() {
  elements.liveClientCount.textContent = `${state.connectedClients} client aktif`;
  elements.liveUpdateText.textContent = state.lastLiveUpdateText;

  if (state.activityEvents.length === 0) {
    elements.activityFeed.innerHTML =
      '<div class="empty-state">Belum ada aktivitas realtime untuk ditampilkan.</div>';
    return;
  }

  elements.activityFeed.innerHTML = state.activityEvents
    .slice(0, 6)
    .map((activity) => {
      return `
        <article class="activity-card ${escapeHtml(activity.emphasis || "system")}">
          <strong>${escapeHtml(activity.title)}</strong>
          <p>${escapeHtml(activity.description)}</p>
          <small>${escapeHtml(formatDateTime(activity.createdAt))}</small>
        </article>
      `;
    })
    .join("");
}

function selectLoan(loanId) {
  const loan = state.loans.find((entry) => entry.loanId === loanId);

  if (!loan || loan.status === "Dikembalikan") {
    return;
  }

  state.selectedLoanId = loanId;
  state.activeChatRoomId = `loan:${loan.loanId.toLowerCase()}`;
  localStorage.setItem("chat-room-id", state.activeChatRoomId);
  if (socket?.connected) {
    socket.emit("chat:join-room", {
      roomId: state.activeChatRoomId,
    });
  }
  renderReturnSummary();
  renderChatRooms();
  renderChat();
  elements.returnForm.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function onLoanSubmit(event) {
  event.preventDefault();
  toggleButton(elements.loanSubmitButton, true, "Menyimpan...");

  try {
    const formData = new FormData(elements.loanForm);
    const payload = Object.fromEntries(formData.entries());
    payload.quantity = Number(payload.quantity);

    const response = await api("/api/loans", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    hydrateState(response.snapshot);
    renderAll();
    elements.loanForm.reset();
    setDefaultDates();
    showToast(response.message);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    toggleButton(elements.loanSubmitButton, false, "Simpan peminjaman");
  }
}

async function onReturnSubmit(event) {
  event.preventDefault();
  toggleButton(elements.returnSubmitButton, true, "Memproses...");

  try {
    const formData = new FormData(elements.returnForm);
    const payload = Object.fromEntries(formData.entries());

    if (!payload.loanId) {
      throw new Error("Pilih transaksi aktif terlebih dahulu.");
    }

    const response = await api("/api/returns", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    state.selectedLoanId = "";
    hydrateState(response.snapshot);
    renderAll();
    elements.returnForm.reset();
    elements.returnedAtInput.value = todayInputValue();
    showToast(response.message);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    toggleButton(elements.returnSubmitButton, false, "Tandai sudah kembali");
  }
}

async function onChatSubmit(event) {
  event.preventDefault();

  if (!socket) {
    showToast("Socket belum siap. Tunggu sebentar lalu coba lagi.", true);
    return;
  }

  const senderName = normalizeSenderName(elements.chatSenderInput.value);
  const message = elements.chatMessageInput.value.trim();

  if (!senderName) {
    showToast("Isi nama pengirim dulu untuk memakai chat.", true);
    elements.chatSenderInput.focus();
    return;
  }

  if (!message) {
    showToast("Pesan chat tidak boleh kosong.", true);
    elements.chatMessageInput.focus();
    return;
  }

  toggleButton(elements.chatSubmitButton, true, "Mengirim...");

  const payload = {
    senderName,
    senderRole: elements.chatRoleSelect.value,
    message,
    roomId: state.activeChatRoomId,
    roomLabel: getActiveChatRoom().label,
    roomType: getActiveChatRoom().type,
  };

  const acknowledgment = await new Promise((resolve) => {
    socket.emit("chat:message", payload, resolve);
  });

  toggleButton(elements.chatSubmitButton, false, "Kirim pesan");

  if (!acknowledgment?.ok) {
    showToast(acknowledgment?.error || "Pesan gagal dikirim.", true);
    return;
  }

  elements.chatMessageInput.value = "";
  state.typingName = "";
  renderChat();
}

function onChatIdentityChange() {
  state.currentSenderName = normalizeSenderName(elements.chatSenderInput.value);
  state.currentSenderRole = elements.chatRoleSelect.value;
  localStorage.setItem("chat-sender-name", state.currentSenderName);
  localStorage.setItem("chat-sender-role", state.currentSenderRole);
  renderChat();
}

function onChatRoomChange() {
  state.activeChatRoomId = elements.chatRoomSelect.value || "general";
  localStorage.setItem("chat-room-id", state.activeChatRoomId);
  state.typingName = "";
  if (socket?.connected) {
    socket.emit("chat:join-room", {
      roomId: state.activeChatRoomId,
    });
  }
  renderChatRooms();
  renderChat();
}

function onChatTyping() {
  if (!socket?.connected) {
    return;
  }

  const senderName = normalizeSenderName(elements.chatSenderInput.value);

  if (!senderName) {
    return;
  }

  window.clearTimeout(typingTimeoutId);
  typingTimeoutId = window.setTimeout(() => {
    socket.emit("chat:typing", {
      senderName,
      roomId: state.activeChatRoomId,
    });
  }, 180);
}

function primeChatIdentity() {
  elements.chatSenderInput.value = state.currentSenderName;
  elements.chatRoleSelect.value = state.currentSenderRole;
  elements.chatRoomSelect.value = state.activeChatRoomId;
}

function getActiveChatRoom() {
  return (
    state.chatRooms.find((room) => room.id === state.activeChatRoomId) || {
      id: "general",
      type: "general",
      label: "Chat Umum",
      subtitle: "Untuk pertanyaan umum seputar peminjaman.",
    }
  );
}

function connectChat() {
  if (typeof io !== "function") {
    showToast("Client Socket.IO tidak ditemukan.", true);
    return;
  }

  socket = io({
    path: "/socket.io",
    transports: ["websocket", "polling"],
  });

  socket.on("connect", () => {
    state.lastLiveUpdateText = "Terhubung ke server realtime.";
    socket.emit("chat:join-room", {
      roomId: state.activeChatRoomId,
    });
    renderChat();
    renderActivities();
  });

  socket.on("disconnect", () => {
    state.lastLiveUpdateText = "Koneksi realtime terputus. Mencoba menyambung ulang...";
    renderChat();
    renderActivities();
  });

  socket.on("chat:history", (payload) => {
    state.chatMessages = payload.messages || [];
    state.onlineUsers = payload.onlineUsers || 0;
    state.activeChatRoomId = payload.activeRoomId || state.activeChatRoomId;
    renderChatRooms();
    renderChat();
  });

  socket.on("chat:room-joined", (payload) => {
    if (payload.roomId !== state.activeChatRoomId) {
      return;
    }

    state.roomUsers = payload.roomUsers || 0;
    renderChat();
  });

  socket.on("activity:history", (payload) => {
    state.connectedClients = payload.connectedClients || 0;
    state.activityEvents = payload.activities || [];
    renderActivities();
  });

  socket.on("chat:new-message", (message) => {
    state.chatMessages = [...state.chatMessages, message].slice(-50);
    if ((message.roomId || "general") === state.activeChatRoomId) {
      state.typingName = "";
    }
    state.lastLiveUpdateText = `Pesan baru dari ${message.senderName} di ${message.roomLabel || "chat"}.`;
    renderChat();
    renderActivities();
  });

  socket.on("chat:presence", (payload) => {
    state.onlineUsers = payload.onlineUsers || 0;
    renderChat();
  });

  socket.on("app:presence", (payload) => {
    state.connectedClients = payload.connectedClients || 0;
    renderActivities();
  });

  socket.on("chat:typing", (payload) => {
    const senderName = normalizeSenderName(payload?.senderName);
    const roomId = payload?.roomId || "general";

    if (
      roomId !== state.activeChatRoomId ||
      !senderName ||
      senderName === normalizeSenderName(state.currentSenderName)
    ) {
      return;
    }

    state.typingName = senderName;
    renderChat();
    window.clearTimeout(typingClearTimeoutId);
    typingClearTimeoutId = window.setTimeout(() => {
      state.typingName = "";
      renderChat();
    }, 1400);
  });

  socket.on("chat:room-presence", (payload) => {
    if ((payload.roomId || "general") !== state.activeChatRoomId) {
      return;
    }

    state.roomUsers = payload.roomUsers || 0;
    renderChat();
  });

  socket.on("inventory:snapshot", (snapshot) => {
    hydrateState(snapshot);
    state.lastLiveUpdateText = "Data inventaris dan riwayat diperbarui realtime.";
    renderAll();
    showToast("Data menu lain sudah sinkron realtime.");
  });

  socket.on("activity:new", (activity) => {
    state.activityEvents = [activity, ...state.activityEvents]
      .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
      .slice(0, 20);
    state.lastLiveUpdateText = activity.title;
    renderActivities();
  });
}

async function api(pathname, options = {}) {
  const response = await fetch(pathname, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.error || payload.detail || "Permintaan gagal diproses.");
  }

  return payload;
}

function toggleButton(button, disabled, label) {
  button.disabled = disabled;
  button.textContent = label;
}

function setDefaultDates() {
  elements.loanDateInput.value = todayInputValue();
  elements.returnedAtInput.value = todayInputValue();
  const dueDate = new Date();
  dueDate.setDate(dueDate.getDate() + 3);
  elements.dueDateInput.value = dueDate.toISOString().slice(0, 10);
}

function todayInputValue() {
  return new Date().toISOString().slice(0, 10);
}

function formatDate(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function showToast(message, isError = false) {
  elements.toast.textContent = message;
  elements.toast.style.background = isError
    ? "rgba(174, 46, 46, 0.95)"
    : "rgba(23, 32, 51, 0.95)";
  elements.toast.classList.add("visible");

  window.clearTimeout(showToast.timeoutId);
  showToast.timeoutId = window.setTimeout(() => {
    elements.toast.classList.remove("visible");
  }, 2600);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalizeSenderName(value) {
  return String(value || "").trim().slice(0, 40);
}
