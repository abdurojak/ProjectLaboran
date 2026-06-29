import http from "node:http";
import { createSign } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Server as SocketIOServer } from "socket.io";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const publicDir = path.join(__dirname, "public");
const configPath = path.join(__dirname, "server.config.json");

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
};

const demoStore = {
  items: [
    {
      id: "BRG-001",
      name: "Laptop Dell Latitude 5420",
      category: "Elektronik",
      stockTotal: 6,
      location: "Lab Komputasi A",
      unit: "unit",
      notes: "Untuk presentasi dan coding",
    },
    {
      id: "BRG-002",
      name: "Proyektor Epson EB-X06",
      category: "Presentasi",
      stockTotal: 3,
      location: "Ruang Multimedia",
      unit: "unit",
      notes: "Lengkap dengan remote",
    },
    {
      id: "BRG-003",
      name: "Kamera Canon EOS M50",
      category: "Dokumentasi",
      stockTotal: 2,
      location: "Studio Kreatif",
      unit: "unit",
      notes: "Tripod terpisah",
    },
    {
      id: "BRG-004",
      name: "Speaker Portable JBL PartyBox",
      category: "Audio",
      stockTotal: 4,
      location: "Gudang Event",
      unit: "unit",
      notes: "Siap untuk kegiatan kelas",
    },
  ],
  loans: [
    {
      loanId: "PMJ-20260618-001",
      borrowerName: "Alya Putri",
      borrowerId: "2211001",
      department: "Teknik Informatika",
      itemId: "BRG-001",
      itemName: "Laptop Dell Latitude 5420",
      quantity: 1,
      purpose: "Demo capstone",
      loanDate: "2026-06-18",
      dueDate: "2026-06-21",
      status: "Dipinjam",
      requestNotes: "Dipakai untuk testing aplikasi",
      returnNotes: "",
      returnedAt: "",
      createdAt: "2026-06-18T08:30:00.000Z",
      sheetRowNumber: 2,
    },
    {
      loanId: "PMJ-20260617-004",
      borrowerName: "Raka Mahendra",
      borrowerId: "2211012",
      department: "Sistem Informasi",
      itemId: "BRG-002",
      itemName: "Proyektor Epson EB-X06",
      quantity: 1,
      purpose: "Presentasi sidang",
      loanDate: "2026-06-17",
      dueDate: "2026-06-18",
      status: "Terlambat",
      requestNotes: "Butuh adaptor HDMI",
      returnNotes: "",
      returnedAt: "",
      createdAt: "2026-06-17T02:10:00.000Z",
      sheetRowNumber: 3,
    },
  ],
  chatMessages: [
    {
      id: "CHAT-001",
      roomId: "general",
      roomLabel: "Chat Umum",
      roomType: "general",
      senderName: "Admin Lab",
      senderRole: "admin",
      message:
        "Halo, kalau ada kendala peminjaman barang silakan tulis di sini ya.",
      createdAt: "2026-06-29T06:00:00.000Z",
    },
  ],
  activityEvents: [
    {
      id: "ACT-001",
      type: "system",
      title: "Dashboard realtime aktif",
      description: "Socket.IO siap menyinkronkan data peminjaman, stok, dan chat.",
      emphasis: "system",
      createdAt: "2026-06-29T06:00:00.000Z",
    },
  ],
};

const appContext = await createAppContext();

const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url || "/", `http://${request.headers.host}`);

    if (url.pathname.startsWith("/api/")) {
      await handleApiRequest(request, response, url);
      return;
    }

    await serveStaticAsset(response, url.pathname);
  } catch (error) {
    console.error(error);
    const statusCode = error.statusCode || 500;
    sendJson(response, statusCode, {
      error:
        statusCode >= 500 ? "Terjadi kesalahan pada server." : error.message,
      detail: error.message,
    });
  }
});

const io = new SocketIOServer(server, {
  path: "/socket.io",
  cors: {
    origin: true,
    credentials: true,
  },
});

wireRealtime(io);

server.listen(appContext.config.port, appContext.config.host, () => {
  const browserHost =
    appContext.config.host === "0.0.0.0" ? "localhost" : appContext.config.host;

  console.log(
    `Peminjaman Barang berjalan di http://${browserHost}:${appContext.config.port} (${appContext.mode})`,
  );
});

async function createAppContext() {
  const config = await loadConfig();
  const serviceAccount = await loadServiceAccount(config.serviceAccountFile);
  const isGoogleMode = Boolean(config.spreadsheetId && serviceAccount);
  const initialDemoStore = structuredClone(demoStore);

  if (isGoogleMode) {
    initialDemoStore.chatMessages = [];
  }

  return {
    config,
    mode: isGoogleMode ? "google-sheets" : "demo",
    serviceAccount,
    demoStore: initialDemoStore,
    onlineUsers: 0,
    socketClients: 0,
    socketRoomById: new Map(),
  };
}

async function loadConfig() {
  let fileConfig = {};

  try {
    fileConfig = JSON.parse(await readFile(configPath, "utf8"));
  } catch (error) {
    if (error.code !== "ENOENT") {
      throw error;
    }
  }

  return {
    host: process.env.HOST || fileConfig.host || "127.0.0.1",
    port: Number(process.env.PORT || fileConfig.port || 3000),
    spreadsheetId: process.env.SPREADSHEET_ID || fileConfig.spreadsheetId || "",
    serviceAccountFile: path.resolve(
      __dirname,
      process.env.GOOGLE_SERVICE_ACCOUNT_FILE ||
        fileConfig.serviceAccountFile ||
        "./google-service-account.json",
    ),
  };
}

async function loadServiceAccount(serviceAccountFile) {
  try {
    const content = await readFile(serviceAccountFile, "utf8");
    const parsed = JSON.parse(content);

    if (!parsed.client_email || !parsed.private_key) {
      return null;
    }

    return parsed;
  } catch (error) {
    if (error.code === "ENOENT") {
      return null;
    }

    throw error;
  }
}

async function handleApiRequest(request, response, url) {
  if (request.method === "GET" && url.pathname === "/api/health") {
    sendJson(response, 200, {
      status: "ok",
      mode: appContext.mode,
    });
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/bootstrap") {
    const snapshot = await getSnapshot();
    sendJson(response, 200, snapshot);
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/loans") {
    const payload = await parseJsonBody(request);
    const createdLoan = await createLoan(payload);
    const activity = pushActivityEvent({
      type: "loan",
      title: `${createdLoan.borrowerName} membuat peminjaman baru`,
      description: `${createdLoan.itemName} sebanyak ${createdLoan.quantity} unit sampai ${createdLoan.dueDate}.`,
      emphasis: "pinjam",
    });
    const snapshot = await getSnapshot();
    io.emit("inventory:snapshot", snapshot);
    io.emit("activity:new", activity);
    sendJson(response, 201, {
      message: "Peminjaman berhasil disimpan.",
      snapshot,
    });
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/returns") {
    const payload = await parseJsonBody(request);
    const returnedLoan = await returnLoan(payload);
    const activity = pushActivityEvent({
      type: "return",
      title: `${returnedLoan.borrowerName} menyelesaikan pengembalian`,
      description: `${returnedLoan.itemName} dikembalikan pada ${returnedLoan.returnedAt}.`,
      emphasis: "kembali",
    });
    const snapshot = await getSnapshot();
    io.emit("inventory:snapshot", snapshot);
    io.emit("activity:new", activity);
    sendJson(response, 200, {
      message: "Pengembalian berhasil diperbarui.",
      snapshot,
    });
    return;
  }

  sendJson(response, 404, {
    error: "Endpoint tidak ditemukan.",
  });
}

async function serveStaticAsset(response, pathname) {
  const safePath = pathname === "/" ? "/index.html" : pathname;
  const requestedPath = path.normalize(path.join(publicDir, safePath));

  if (!requestedPath.startsWith(publicDir)) {
    sendText(response, 403, "Akses ditolak.");
    return;
  }

  try {
    const fileInfo = await stat(requestedPath);

    if (!fileInfo.isFile()) {
      sendText(response, 404, "File tidak ditemukan.");
      return;
    }

    const extension = path.extname(requestedPath);
    const fileBuffer = await readFile(requestedPath);

    response.writeHead(200, {
      "Content-Type": mimeTypes[extension] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    response.end(fileBuffer);
  } catch (error) {
    if (error.code === "ENOENT") {
      sendText(response, 404, "File tidak ditemukan.");
      return;
    }

    throw error;
  }
}

async function parseJsonBody(request) {
  const chunks = [];

  for await (const chunk of request) {
    chunks.push(chunk);
  }

  if (chunks.length === 0) {
    return {};
  }

  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch (error) {
    throw createHttpError(400, "Body JSON tidak valid.");
  }
}

async function getSnapshot() {
  const baseData =
    appContext.mode === "google-sheets"
      ? await loadGoogleSheetData()
      : structuredClone(appContext.demoStore);
  const chatMessages =
    appContext.mode === "google-sheets"
      ? sortChatMessages([...(baseData.chatMessages || []), ...appContext.demoStore.chatMessages])
      : sortChatMessages(baseData.chatMessages || []);

  const loans = enrichLoans(baseData.loans);
  const items = withAvailability(baseData.items, loans);

  return {
    mode: appContext.mode,
    updatedAt: new Date().toISOString(),
    stats: buildStats(items, loans),
    items,
    loans: sortLoans(loans),
    chat: {
      onlineUsers: appContext.onlineUsers,
      rooms: buildChatRooms(items, loans),
      messages: chatMessages,
    },
    realtime: {
      connectedClients: appContext.socketClients,
      activities: getActivityEvents(),
    },
  };
}

function wireRealtime(socketServer) {
  socketServer.on("connection", (socket) => {
    appContext.socketClients += 1;
    appContext.onlineUsers += 1;
    joinSocketRoom(socket, "general");
    socket.emit("chat:history", {
      onlineUsers: appContext.onlineUsers,
      activeRoomId: getSocketRoom(socket.id),
      messages: getChatMessages(),
    });
    socket.emit("activity:history", {
      connectedClients: appContext.socketClients,
      activities: getActivityEvents(),
    });
    socketServer.emit("app:presence", {
      connectedClients: appContext.socketClients,
    });
    socket.broadcast.emit("chat:presence", {
      onlineUsers: appContext.onlineUsers,
    });

    socket.on("chat:join-room", (payload = {}) => {
      const roomId = normalizeChatRoomId(payload.roomId) || "general";
      const previousRoomId = joinSocketRoom(socket, roomId);
      socket.emit("chat:room-joined", {
        roomId,
        roomUsers: countRoomUsers(roomId),
      });
      if (previousRoomId) {
        socketServer.to(getSocketRoomChannel(previousRoomId)).emit("chat:room-presence", {
          roomId: previousRoomId,
          roomUsers: countRoomUsers(previousRoomId),
        });
      }
      socket.to(getSocketRoomChannel(roomId)).emit("chat:room-presence", {
        roomId,
        roomUsers: countRoomUsers(roomId),
      });
    });

    socket.on("chat:typing", (payload) => {
      const senderName = normalizeSenderName(payload?.senderName);
      const roomId = normalizeChatRoomId(payload?.roomId) || getSocketRoom(socket.id);

      if (!senderName || !roomId) {
        return;
      }

      socket.to(getSocketRoomChannel(roomId)).emit("chat:typing", {
        roomId,
        senderName,
      });
    });

    socket.on("chat:message", async (payload, acknowledge = () => {}) => {
      const chatMessage = normalizeChatPayload(payload);

      if (!chatMessage) {
        acknowledge({
          ok: false,
          error: "Nama dan pesan chat wajib diisi.",
        });
        return;
      }

      const savedMessage = {
        id: generateChatId(),
        roomId: chatMessage.roomId,
        roomLabel: chatMessage.roomLabel,
        roomType: chatMessage.roomType,
        senderName: chatMessage.senderName,
        senderRole: chatMessage.senderRole,
        message: chatMessage.message,
        createdAt: new Date().toISOString(),
      };

      await persistChatMessage(savedMessage);
      const activity = pushActivityEvent({
        type: "chat",
        title: `${savedMessage.senderName} mengirim pesan ke ${savedMessage.roomLabel}`,
        description: savedMessage.message,
        emphasis: savedMessage.senderRole === "admin" ? "admin" : "chat",
      });
      socketServer.to(getSocketRoomChannel(savedMessage.roomId)).emit("chat:new-message", savedMessage);
      socketServer.emit("activity:new", activity);
      acknowledge({
        ok: true,
      });
    });

    socket.on("disconnect", () => {
      const activeRoomId = getSocketRoom(socket.id);
      appContext.onlineUsers = Math.max(appContext.onlineUsers - 1, 0);
      appContext.socketClients = Math.max(appContext.socketClients - 1, 0);
      leaveSocketRoom(socket);
      socketServer.emit("chat:presence", {
        onlineUsers: appContext.onlineUsers,
      });
      socketServer.emit("app:presence", {
        connectedClients: appContext.socketClients,
      });
      if (activeRoomId) {
        socketServer.to(getSocketRoomChannel(activeRoomId)).emit("chat:room-presence", {
          roomId: activeRoomId,
          roomUsers: countRoomUsers(activeRoomId),
        });
      }
    });
  });
}

function enrichLoans(loans) {
  return loans.map((loan) => {
    const isReturned = loan.status === "Dikembalikan";
    const today = startOfToday();
    const dueDate = loan.dueDate ? new Date(`${loan.dueDate}T00:00:00`) : null;
    const isOverdue = !isReturned && dueDate && dueDate < today;

    return {
      ...loan,
      status: isOverdue ? "Terlambat" : loan.status,
    };
  });
}

function withAvailability(items, loans) {
  return items.map((item) => {
    const activeBorrowed = loans
      .filter((loan) => loan.itemId === item.id && loan.status !== "Dikembalikan")
      .reduce((total, loan) => total + loan.quantity, 0);

    return {
      ...item,
      stockAvailable: Math.max(item.stockTotal - activeBorrowed, 0),
      stockBorrowed: activeBorrowed,
    };
  });
}

function buildStats(items, loans) {
  const activeLoans = loans.filter((loan) => loan.status !== "Dikembalikan").length;
  const overdueLoans = loans.filter((loan) => loan.status === "Terlambat").length;
  const itemsReady = items.reduce((total, item) => total + item.stockAvailable, 0);
  const returnedToday = loans.filter(
    (loan) => loan.returnedAt && loan.returnedAt.startsWith(todayIsoDate()),
  ).length;

  return {
    totalItems: items.length,
    activeLoans,
    overdueLoans,
    itemsReady,
    returnedToday,
  };
}

function sortLoans(loans) {
  return [...loans].sort((left, right) => {
    const leftValue = new Date(left.createdAt || left.loanDate).getTime();
    const rightValue = new Date(right.createdAt || right.loanDate).getTime();
    return rightValue - leftValue;
  });
}

async function createLoan(payload) {
  const normalized = normalizeLoanPayload(payload);
  const snapshot = await getSnapshot();
  const selectedItem = snapshot.items.find((item) => item.id === normalized.itemId);

  if (!selectedItem) {
    throw createHttpError(400, "Barang yang dipilih tidak tersedia.");
  }

  if (normalized.quantity > selectedItem.stockAvailable) {
    throw createHttpError(
      400,
      `Stok tersedia untuk ${selectedItem.name} hanya ${selectedItem.stockAvailable}.`,
    );
  }

  const loanRow = {
    loanId: generateLoanId(),
    borrowerName: normalized.borrowerName,
    borrowerId: normalized.borrowerId,
    department: normalized.department,
    itemId: selectedItem.id,
    itemName: selectedItem.name,
    quantity: normalized.quantity,
    purpose: normalized.purpose,
    loanDate: normalized.loanDate,
    dueDate: normalized.dueDate,
    status: "Dipinjam",
    requestNotes: normalized.requestNotes,
    returnNotes: "",
    returnedAt: "",
    createdAt: new Date().toISOString(),
  };

  if (appContext.mode === "google-sheets") {
    await appendLoanToGoogleSheet(loanRow);
    return loanRow;
  }

  appContext.demoStore.loans.push({
    ...loanRow,
    sheetRowNumber: appContext.demoStore.loans.length + 2,
  });
  return loanRow;
}

async function returnLoan(payload) {
  const loanId = normalizeText(payload.loanId);
  const returnNotes = normalizeText(payload.returnNotes);
  const returnedAt = normalizeDate(payload.returnedAt || todayIsoDate());

  if (!loanId) {
    throw createHttpError(400, "Loan ID wajib dipilih untuk proses pengembalian.");
  }

  if (appContext.mode === "google-sheets") {
    const googleData = await loadGoogleSheetData();
    const loan = enrichLoans(googleData.loans).find(
      (entry) => entry.loanId === loanId && entry.status !== "Dikembalikan",
    );

    if (!loan) {
      throw createHttpError(404, "Data peminjaman aktif tidak ditemukan.");
    }

    await updateLoanReturnOnGoogleSheet(loan.sheetRowNumber, returnNotes, returnedAt);
    return {
      ...loan,
      returnedAt,
      returnNotes,
    };
  }

  const loan = appContext.demoStore.loans.find(
    (entry) => entry.loanId === loanId && entry.status !== "Dikembalikan",
  );

  if (!loan) {
    throw createHttpError(404, "Data peminjaman aktif tidak ditemukan.");
  }

  loan.status = "Dikembalikan";
  loan.returnNotes = returnNotes;
  loan.returnedAt = returnedAt;
  return loan;
}

function normalizeLoanPayload(payload) {
  const normalized = {
    borrowerName: normalizeText(payload.borrowerName),
    borrowerId: normalizeText(payload.borrowerId),
    department: normalizeText(payload.department),
    itemId: normalizeText(payload.itemId),
    quantity: Number(payload.quantity || 0),
    purpose: normalizeText(payload.purpose),
    loanDate: normalizeDate(payload.loanDate),
    dueDate: normalizeDate(payload.dueDate),
    requestNotes: normalizeText(payload.requestNotes),
  };

  if (
    !normalized.borrowerName ||
    !normalized.borrowerId ||
    !normalized.department ||
    !normalized.itemId ||
    !normalized.purpose ||
    !normalized.loanDate ||
    !normalized.dueDate
  ) {
    throw createHttpError(400, "Semua field wajib harus diisi.");
  }

  if (!Number.isInteger(normalized.quantity) || normalized.quantity < 1) {
    throw createHttpError(400, "Jumlah pinjam minimal 1.");
  }

  if (normalized.dueDate < normalized.loanDate) {
    throw createHttpError(400, "Tanggal kembali tidak boleh lebih awal dari tanggal pinjam.");
  }

  return normalized;
}

function normalizeText(value) {
  return String(value || "").trim();
}

function normalizeSenderName(value) {
  return normalizeText(value).slice(0, 40);
}

function normalizeChatPayload(payload) {
  const senderName = normalizeSenderName(payload?.senderName);
  const message = normalizeText(payload?.message).slice(0, 500);
  const senderRole = normalizeText(payload?.senderRole) || "pengguna";
  const roomId = normalizeChatRoomId(payload?.roomId) || "general";
  const roomLabel = normalizeText(payload?.roomLabel) || describeChatRoom(roomId);
  const roomType = normalizeChatRoomType(payload?.roomType) || inferChatRoomType(roomId);

  if (!senderName || !message) {
    return null;
  }

  return {
    senderName,
    message,
    senderRole,
    roomId,
    roomLabel,
    roomType,
  };
}

function normalizeChatRoomId(value) {
  const normalized = normalizeText(value).toLowerCase();
  return normalized.replace(/[^a-z0-9:_-]/g, "").slice(0, 80);
}

function normalizeChatRoomType(value) {
  const normalized = normalizeText(value).toLowerCase();
  if (["general", "loan", "item"].includes(normalized)) {
    return normalized;
  }
  return "";
}

function normalizeDate(value) {
  const text = normalizeText(value);

  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return "";
  }

  return text;
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function startOfToday() {
  return new Date(`${todayIsoDate()}T00:00:00`);
}

function generateLoanId() {
  const dateToken = todayIsoDate().replaceAll("-", "");
  const suffix = String(Math.floor(Math.random() * 900) + 100);
  return `PMJ-${dateToken}-${suffix}`;
}

function generateChatId() {
  return `CHAT-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

function generateActivityId() {
  return `ACT-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

function buildChatRooms(items, loans) {
  const rooms = [
    {
      id: "general",
      type: "general",
      label: "Chat Umum",
      subtitle: "Untuk pertanyaan umum seputar peminjaman.",
    },
  ];

  for (const loan of sortLoans(loans).slice(0, 12)) {
    rooms.push({
      id: `loan:${loan.loanId.toLowerCase()}`,
      type: "loan",
      label: `Loan ${loan.loanId}`,
      subtitle: `${loan.borrowerName} - ${loan.itemName}`,
    });
  }

  for (const item of items.slice(0, 12)) {
    rooms.push({
      id: `item:${item.id.toLowerCase()}`,
      type: "item",
      label: item.name,
      subtitle: `Barang ${item.id} - ${item.stockAvailable}/${item.stockTotal} tersedia`,
    });
  }

  return rooms;
}

function inferChatRoomType(roomId) {
  if (roomId.startsWith("loan:")) {
    return "loan";
  }
  if (roomId.startsWith("item:")) {
    return "item";
  }
  return "general";
}

function describeChatRoom(roomId) {
  if (roomId.startsWith("loan:")) {
    return `Loan ${roomId.slice(5).toUpperCase()}`;
  }
  if (roomId.startsWith("item:")) {
    return `Barang ${roomId.slice(5).toUpperCase()}`;
  }
  return "Chat Umum";
}

function getSocketRoomChannel(roomId) {
  return `chat:room:${roomId}`;
}

function getSocketRoom(socketId) {
  return appContext.socketRoomById.get(socketId) || "";
}

function joinSocketRoom(socket, roomId) {
  const previousRoomId = getSocketRoom(socket.id);

  if (previousRoomId === roomId) {
    return previousRoomId;
  }

  if (previousRoomId) {
    socket.leave(getSocketRoomChannel(previousRoomId));
  }

  socket.join(getSocketRoomChannel(roomId));
  appContext.socketRoomById.set(socket.id, roomId);
  return previousRoomId;
}

function leaveSocketRoom(socket) {
  appContext.socketRoomById.delete(socket.id);
}

function countRoomUsers(roomId) {
  let total = 0;

  for (const activeRoomId of appContext.socketRoomById.values()) {
    if (activeRoomId === roomId) {
      total += 1;
    }
  }

  return total;
}

function getChatMessages() {
  return sortChatMessages(appContext.demoStore.chatMessages);
}

function sortChatMessages(messages) {
  return [...messages].sort((left, right) => {
    return new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime();
  });
}

async function persistChatMessage(message) {
  if (appContext.mode === "google-sheets") {
    try {
      await appendChatMessageToGoogleSheet(message);
      return;
    } catch (error) {
      console.error("Gagal menyimpan chat ke Google Sheet, fallback ke memory lokal.", error);
    }
  }

  appContext.demoStore.chatMessages.push(message);
  trimChatMessages();
}

function trimChatMessages() {
  const maxMessages = 50;

  if (appContext.demoStore.chatMessages.length <= maxMessages) {
    return;
  }

  appContext.demoStore.chatMessages = appContext.demoStore.chatMessages.slice(-maxMessages);
}

function getActivityEvents() {
  return [...appContext.demoStore.activityEvents].sort((left, right) => {
    return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime();
  });
}

function pushActivityEvent(eventInput) {
  const activity = {
    id: generateActivityId(),
    type: eventInput.type,
    title: eventInput.title,
    description: eventInput.description,
    emphasis: eventInput.emphasis || "system",
    createdAt: new Date().toISOString(),
  };

  appContext.demoStore.activityEvents.push(activity);
  trimActivityEvents();
  return activity;
}

function trimActivityEvents() {
  const maxEvents = 20;

  if (appContext.demoStore.activityEvents.length <= maxEvents) {
    return;
  }

  appContext.demoStore.activityEvents = appContext.demoStore.activityEvents.slice(-maxEvents);
}

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(payload));
}

function sendText(response, statusCode, text) {
  response.writeHead(statusCode, {
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(text);
}

function createHttpError(statusCode, message) {
  const error = new Error(message);
  error.statusCode = statusCode;
  return error;
}

async function loadGoogleSheetData() {
  let valueRanges;

  try {
    valueRanges = await getSheetValuesBatch([
      "Items!A2:G",
      "Loans!A2:O",
      "Chats!A2:H",
    ]);
  } catch (error) {
    valueRanges = await getSheetValuesBatch([
      "Items!A2:G",
      "Loans!A2:O",
    ]);
  }

  const [itemsRange, loansRange, chatsRange] = valueRanges;

  return {
    items: mapItems(itemsRange || []),
    loans: mapLoans(loansRange || []),
    chatMessages: mapChatMessages(chatsRange || []),
  };
}

function mapItems(rows) {
  return rows
    .filter((row) => normalizeText(row[0]) && normalizeText(row[1]))
    .map((row) => ({
      id: normalizeText(row[0]),
      name: normalizeText(row[1]),
      category: normalizeText(row[2]),
      stockTotal: Number(row[3] || 0),
      location: normalizeText(row[4]),
      unit: normalizeText(row[5] || "unit"),
      notes: normalizeText(row[6]),
    }));
}

function mapLoans(rows) {
  return rows
    .map((row, index) => ({
      loanId: normalizeText(row[0]),
      borrowerName: normalizeText(row[1]),
      borrowerId: normalizeText(row[2]),
      department: normalizeText(row[3]),
      itemId: normalizeText(row[4]),
      itemName: normalizeText(row[5]),
      quantity: Number(row[6] || 0),
      purpose: normalizeText(row[7]),
      loanDate: normalizeText(row[8]),
      dueDate: normalizeText(row[9]),
      status: normalizeText(row[10] || "Dipinjam"),
      requestNotes: normalizeText(row[11]),
      returnNotes: normalizeText(row[12]),
      returnedAt: normalizeText(row[13]),
      createdAt: normalizeText(row[14]),
      sheetRowNumber: index + 2,
    }))
    .filter((row) => row.loanId && row.itemId);
}

function mapChatMessages(rows) {
  return rows
    .map((row) => ({
      id: normalizeText(row[0]),
      roomId: normalizeChatRoomId(row[1]) || "general",
      roomLabel: normalizeText(row[2]) || "Chat Umum",
      roomType: normalizeChatRoomType(row[3]) || "general",
      senderName: normalizeSenderName(row[4]),
      senderRole: normalizeText(row[5]) || "pengguna",
      message: normalizeText(row[6]),
      createdAt: normalizeText(row[7]),
    }))
    .filter((row) => row.id && row.senderName && row.message);
}

async function appendLoanToGoogleSheet(loanRow) {
  await googleSheetsRequest(
    `/values/${encodeRange("Loans!A:O")}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS`,
    {
      method: "POST",
      body: JSON.stringify({
        range: "Loans!A:O",
        majorDimension: "ROWS",
        values: [
          [
            loanRow.loanId,
            loanRow.borrowerName,
            loanRow.borrowerId,
            loanRow.department,
            loanRow.itemId,
            loanRow.itemName,
            loanRow.quantity,
            loanRow.purpose,
            loanRow.loanDate,
            loanRow.dueDate,
            loanRow.status,
            loanRow.requestNotes,
            loanRow.returnNotes,
            loanRow.returnedAt,
            loanRow.createdAt,
          ],
        ],
      }),
    },
  );
}

async function appendChatMessageToGoogleSheet(message) {
  await googleSheetsRequest(
    `/values/${encodeRange("Chats!A:H")}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS`,
    {
      method: "POST",
      body: JSON.stringify({
        range: "Chats!A:H",
        majorDimension: "ROWS",
        values: [
          [
            message.id,
            message.roomId,
            message.roomLabel,
            message.roomType,
            message.senderName,
            message.senderRole,
            message.message,
            message.createdAt,
          ],
        ],
      }),
    },
  );
}

async function updateLoanReturnOnGoogleSheet(rowNumber, returnNotes, returnedAt) {
  await googleSheetsRequest("/values:batchUpdate", {
    method: "POST",
    body: JSON.stringify({
      valueInputOption: "USER_ENTERED",
      data: [
        {
          range: `Loans!K${rowNumber}:K${rowNumber}`,
          values: [["Dikembalikan"]],
        },
        {
          range: `Loans!M${rowNumber}:N${rowNumber}`,
          values: [[returnNotes, returnedAt]],
        },
      ],
    }),
  });
}

async function getSheetValuesBatch(ranges) {
  const params = new URLSearchParams();

  for (const range of ranges) {
    params.append("ranges", range);
  }

  params.set("majorDimension", "ROWS");

  const response = await googleSheetsRequest(`/values:batchGet?${params.toString()}`, {
    method: "GET",
  });

  return response.valueRanges.map((entry) => entry.values || []);
}

function encodeRange(range) {
  return encodeURIComponent(range).replaceAll("%20", "+");
}

async function googleSheetsRequest(endpoint, options) {
  const accessToken = await getGoogleAccessToken();
  const response = await fetch(
    `https://sheets.googleapis.com/v4/spreadsheets/${appContext.config.spreadsheetId}${endpoint}`,
    {
      ...options,
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json; charset=utf-8",
        ...(options.headers || {}),
      },
    },
  );

  if (!response.ok) {
    const failureText = await response.text();
    throw new Error(`Google Sheets API gagal: ${failureText}`);
  }

  return response.json();
}

async function getGoogleAccessToken() {
  const header = {
    alg: "RS256",
    typ: "JWT",
  };
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iss: appContext.serviceAccount.client_email,
    scope: "https://www.googleapis.com/auth/spreadsheets",
    aud: "https://oauth2.googleapis.com/token",
    exp: now + 3600,
    iat: now,
  };
  const assertion = signJwt(header, payload, appContext.serviceAccount.private_key);
  const body = new URLSearchParams({
    grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
    assertion,
  });

  const response = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });

  if (!response.ok) {
    const failureText = await response.text();
    throw new Error(`Gagal membuat access token Google: ${failureText}`);
  }

  const tokenPayload = await response.json();
  return tokenPayload.access_token;
}

function signJwt(header, payload, privateKey) {
  const unsignedToken = `${toBase64Url(header)}.${toBase64Url(payload)}`;
  const signer = createSign("RSA-SHA256");
  signer.update(unsignedToken);
  signer.end();
  const signature = signer.sign(privateKey);
  return `${unsignedToken}.${toBase64Url(signature)}`;
}

function toBase64Url(value) {
  const buffer = Buffer.isBuffer(value)
    ? value
    : Buffer.from(typeof value === "string" ? value : JSON.stringify(value));

  return buffer
    .toString("base64")
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

process.on("uncaughtException", (error) => {
  console.error(error);
});

process.on("unhandledRejection", (error) => {
  console.error(error);
});
