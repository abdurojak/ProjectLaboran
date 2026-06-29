import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");
const outputDir = path.join(rootDir, "outputs");
const outputFile = path.join(outputDir, "capstone-peminjaman-template.xlsx");

await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
const itemsSheet = workbook.worksheets.add("Items");
const loansSheet = workbook.worksheets.add("Loans");
const chatsSheet = workbook.worksheets.add("Chats");
const guideSheet = workbook.worksheets.add("Guide");

itemsSheet.getRange("A1:G5").values = [
  ["item_id", "item_name", "category", "stock_total", "location", "unit", "notes"],
  ["BRG-001", "Laptop Dell Latitude 5420", "Elektronik", 6, "Lab Komputasi A", "unit", "Untuk presentasi dan coding"],
  ["BRG-002", "Proyektor Epson EB-X06", "Presentasi", 3, "Ruang Multimedia", "unit", "Lengkap dengan remote"],
  ["BRG-003", "Kamera Canon EOS M50", "Dokumentasi", 2, "Studio Kreatif", "unit", "Tripod terpisah"],
  ["BRG-004", "Speaker Portable JBL PartyBox", "Audio", 4, "Gudang Event", "unit", "Dipakai acara kampus"],
];

loansSheet.getRange("A1:O2").values = [
  [
    "loan_id",
    "borrower_name",
    "borrower_id",
    "department",
    "item_id",
    "item_name",
    "quantity",
    "purpose",
    "loan_date",
    "due_date",
    "status",
    "request_notes",
    "return_notes",
    "returned_at",
    "created_at",
  ],
  [
    "PMJ-20260618-001",
    "Alya Putri",
    "2211001",
    "Teknik Informatika",
    "BRG-001",
    "Laptop Dell Latitude 5420",
    1,
    "Demo capstone",
    "2026-06-18",
    "2026-06-21",
    "Dipinjam",
    "Dipakai testing aplikasi",
    "",
    "",
    "2026-06-18T08:30:00.000Z",
  ],
];

chatsSheet.getRange("A1:H2").values = [
  [
    "chat_id",
    "room_id",
    "room_label",
    "room_type",
    "sender_name",
    "sender_role",
    "message",
    "created_at",
  ],
  [
    "CHAT-001",
    "general",
    "Chat Umum",
    "general",
    "Admin Lab",
    "admin",
    "Halo, kalau ada kendala peminjaman barang silakan tulis di sini ya.",
    "2026-06-29T06:00:00.000Z",
  ],
];

guideSheet.getRange("A1:B9").values = [
  ["Panduan", "Keterangan"],
  ["1", "Gunakan sheet Items untuk daftar inventaris master."],
  ["2", "Gunakan sheet Loans sebagai log transaksi peminjaman dan pengembalian."],
  ["3", "Gunakan sheet Chats untuk menyimpan histori chat realtime per room."],
  ["4", "Kolom item_id di Loans harus sesuai item_id di Items."],
  ["5", "Kolom status pakai nilai Dipinjam, Terlambat, atau Dikembalikan."],
  ["6", "Server aplikasi akan membaca ketiga sheet ini secara langsung."],
  ["7", "Bagikan spreadsheet ke email service account sebagai Editor."],
  ["8", "Simpan spreadsheet ID ke server.config.json pada project web."],
];

for (const sheet of [itemsSheet, loansSheet, chatsSheet, guideSheet]) {
  sheet.showGridLines = true;
  sheet.freezePanes.freezeRows(1);
}

itemsSheet.getRange("A1:G5").format = {
  font: { color: "#111827" },
  wrapText: true,
};
itemsSheet.getRange("A1:G1").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
};
itemsSheet.getRange("A1:G5").format.borders = {
  preset: "all",
  style: "thin",
  color: "#D1D5DB",
};
itemsSheet.getRange("D2:D20").format.numberFormat = "0";
itemsSheet.getRange("A1:G20").format.autofitColumns();

loansSheet.getRange("A1:O2").format = {
  font: { color: "#111827" },
  wrapText: true,
};
loansSheet.getRange("A1:O1").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
};
loansSheet.getRange("A1:O12").format.borders = {
  preset: "all",
  style: "thin",
  color: "#D1D5DB",
};
loansSheet.getRange("G2:G1000").format.numberFormat = "0";
loansSheet.getRange("I2:J1000").format.numberFormat = "yyyy-mm-dd";
loansSheet.getRange("A1:O30").format.autofitColumns();

chatsSheet.getRange("A1:H2").format = {
  font: { color: "#111827" },
  wrapText: true,
};
chatsSheet.getRange("A1:H1").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
};
chatsSheet.getRange("A1:H20").format.borders = {
  preset: "all",
  style: "thin",
  color: "#D1D5DB",
};
chatsSheet.getRange("H2:H1000").format.numberFormat = "yyyy-mm-dd hh:mm";
chatsSheet.getRange("A1:H24").format.autofitColumns();

guideSheet.getRange("A1:B9").format = {
  font: { color: "#111827" },
  wrapText: true,
};
guideSheet.getRange("A1:B1").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
};
guideSheet.getRange("A1:B9").format.borders = {
  preset: "all",
  style: "thin",
  color: "#D1D5DB",
};
guideSheet.getRange("A1:B10").format.autofitColumns();

const exportedFile = await SpreadsheetFile.exportXlsx(workbook);
await exportedFile.save(outputFile);

console.log(outputFile);
