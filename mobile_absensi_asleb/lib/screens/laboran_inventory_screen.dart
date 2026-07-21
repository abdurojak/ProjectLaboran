import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../models/inventory_item.dart';
import '../providers/laboran_provider.dart';
import '../utils/app_theme.dart';

class LaboranInventoryScreen extends StatefulWidget {
  const LaboranInventoryScreen({super.key});
  @override
  State<LaboranInventoryScreen> createState() => _LaboranInventoryScreenState();
}

class _LaboranInventoryScreenState extends State<LaboranInventoryScreen> {
  String query = '';
  @override
  void initState() {
    super.initState();
    Future.microtask(context.read<LaboranProvider>().loadInventory);
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<LaboranProvider>();
    final items = state.inventory
        .where(
          (item) => '${item.nama} ${item.kode}'.toLowerCase().contains(
            query.toLowerCase(),
          ),
        )
        .toList();
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Inventaris',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: state.locations.isEmpty
            ? null
            : () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const _AddInventoryScreen()),
              ),
        icon: const Icon(Icons.add_photo_alternate_outlined),
        label: const Text('Tambah Barang'),
      ),
      body: RefreshIndicator(
        onRefresh: state.loadInventory,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 100),
          children: [
            TextField(
              onChanged: (value) => setState(() => query = value),
              decoration: const InputDecoration(
                hintText: 'Cari nama atau kode barang',
                prefixIcon: Icon(Icons.search),
              ),
            ),
            const SizedBox(height: 16),
            if (state.loading && state.inventory.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(50),
                  child: CircularProgressIndicator(),
                ),
              )
            else if (state.error != null && state.inventory.isEmpty)
              Center(child: Text(state.error!))
            else if (items.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(50),
                  child: Text('Belum ada barang yang sesuai.'),
                ),
              )
            else
              ...items.map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _InventoryCard(item: item),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _InventoryCard extends StatelessWidget {
  const _InventoryCard({required this.item});
  final InventoryItem item;
  @override
  Widget build(BuildContext context) => Card(
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => _InventoryDetailScreen(initialItem: item),
        ),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 104,
            height: 118,
            child: item.photoUrl == null
                ? Container(
                    color: const Color(0xFFE4F2F1),
                    child: const Icon(
                      Icons.inventory_2_outlined,
                      color: AppTheme.teal,
                      size: 38,
                    ),
                  )
                : Image.network(
                    item.photoUrl!,
                    fit: BoxFit.cover,
                    errorBuilder: (_, _, _) =>
                        const Icon(Icons.broken_image_outlined),
                  ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.nama,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w900,
                      color: AppTheme.navy,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    item.kode,
                    style: const TextStyle(
                      color: Color(0xFF64748B),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      _Chip('${item.tersedia} tersedia', AppTheme.teal),
                      _Chip('${item.dipinjam} dipinjam', AppTheme.amber),
                      if (item.photoUrls.length > 1)
                        _Chip(
                          '${item.photoUrls.length} foto',
                          const Color(0xFF2563EB),
                        ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  const Row(
                    children: [
                      Text(
                        'Lihat detail',
                        style: TextStyle(
                          color: AppTheme.teal,
                          fontSize: 12,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      SizedBox(width: 3),
                      Icon(
                        Icons.arrow_forward_rounded,
                        size: 15,
                        color: AppTheme.teal,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

class _InventoryDetailScreen extends StatefulWidget {
  const _InventoryDetailScreen({required this.initialItem});
  final InventoryItem initialItem;

  @override
  State<_InventoryDetailScreen> createState() => _InventoryDetailScreenState();
}

class _InventoryDetailScreenState extends State<_InventoryDetailScreen> {
  late Future<InventoryItem> detail;

  @override
  void initState() {
    super.initState();
    detail = context.read<LaboranProvider>().loadInventoryDetail(
      widget.initialItem.id,
    );
  }

  Future<void> deleteItem(InventoryItem item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        icon: const Icon(
          Icons.delete_outline_rounded,
          color: Color(0xFFDC2626),
        ),
        title: const Text('Hapus barang inventaris?'),
        content: Text(
          '${item.nama} akan dihapus beserta data unit dan fotonya. '
          'Barang yang memiliki riwayat peminjaman tidak dapat dihapus.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Batal'),
          ),
          FilledButton.icon(
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFFDC2626),
            ),
            onPressed: () => Navigator.pop(dialogContext, true),
            icon: const Icon(Icons.delete_outline_rounded),
            label: const Text('Ya, hapus'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    final provider = context.read<LaboranProvider>();
    final success = await provider.deleteInventory(item.id);
    if (!mounted) return;
    if (success) {
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Barang inventaris berhasil dihapus.')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(provider.error ?? 'Barang gagal dihapus.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text(
        'Detail Barang',
        style: TextStyle(fontWeight: FontWeight.w900),
      ),
    ),
    body: FutureBuilder<InventoryItem>(
      future: detail,
      initialData: widget.initialItem,
      builder: (context, snapshot) {
        final item = snapshot.data;
        if (item == null) {
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Text('Detail barang gagal dimuat: ${snapshot.error}'),
              ),
            );
          }
          return const Center(child: CircularProgressIndicator());
        }
        return ListView(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 30),
          children: [
            _InventoryGallery(item: item),
            const SizedBox(height: 18),
            Text(
              item.nama,
              style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 5),
            Text(
              item.kode,
              style: const TextStyle(
                color: Color(0xFF64748B),
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 18),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _Chip('${item.jumlah} total unit', const Color(0xFF2563EB)),
                _Chip('${item.tersedia} tersedia', AppTheme.teal),
                _Chip('${item.dipinjam} dipinjam', AppTheme.amber),
              ],
            ),
            const SizedBox(height: 22),
            _DetailSection(
              icon: Icons.location_on_outlined,
              title: 'Lokasi penyimpanan',
              value: item.locations.isEmpty
                  ? 'Belum ditentukan'
                  : item.locations
                        .map((location) => location['nama'])
                        .join(', '),
            ),
            const SizedBox(height: 12),
            _DetailSection(
              icon: Icons.notes_rounded,
              title: 'Keterangan',
              value: item.keterangan.trim().isEmpty
                  ? 'Tidak ada keterangan.'
                  : item.keterangan,
            ),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: const Color(0xFFDC2626),
                side: const BorderSide(color: Color(0xFFFCA5A5)),
              ),
              onPressed: context.watch<LaboranProvider>().submitting
                  ? null
                  : () => deleteItem(item),
              icon: const Icon(Icons.delete_outline_rounded),
              label: const Text('Hapus Barang'),
            ),
          ],
        );
      },
    ),
  );
}

class _InventoryGallery extends StatelessWidget {
  const _InventoryGallery({required this.item});
  final InventoryItem item;

  @override
  Widget build(BuildContext context) {
    if (item.photoUrls.isEmpty) {
      return Container(
        height: 250,
        decoration: BoxDecoration(
          color: const Color(0xFFE4F2F1),
          borderRadius: BorderRadius.circular(26),
        ),
        child: const Icon(
          Icons.inventory_2_outlined,
          size: 70,
          color: AppTheme.teal,
        ),
      );
    }
    return SizedBox(
      height: 280,
      child: PageView.builder(
        itemCount: item.photoUrls.length,
        itemBuilder: (context, index) => Padding(
          padding: const EdgeInsets.only(right: 8),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(26),
            child: Stack(
              fit: StackFit.expand,
              children: [
                Image.network(item.photoUrls[index], fit: BoxFit.cover),
                Positioned(
                  right: 12,
                  bottom: 12,
                  child: _Chip(
                    '${index + 1}/${item.photoUrls.length}',
                    AppTheme.navy,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DetailSection extends StatelessWidget {
  const _DetailSection({
    required this.icon,
    required this.title,
    required this.value,
  });
  final IconData icon;
  final String title;
  final String value;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(17),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(20),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: AppTheme.teal),
        const SizedBox(width: 13),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
              const SizedBox(height: 4),
              Text(value, style: const TextStyle(height: 1.45)),
            ],
          ),
        ),
      ],
    ),
  );
}

class _Chip extends StatelessWidget {
  const _Chip(this.label, this.color);
  final String label;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
    decoration: BoxDecoration(
      color: color.withValues(alpha: .1),
      borderRadius: BorderRadius.circular(99),
    ),
    child: Text(
      label,
      style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w900),
    ),
  );
}

class _AddInventoryScreen extends StatefulWidget {
  const _AddInventoryScreen();
  @override
  State<_AddInventoryScreen> createState() => _AddInventoryScreenState();
}

class _AddInventoryScreenState extends State<_AddInventoryScreen> {
  final formKey = GlobalKey<FormState>();
  final name = TextEditingController();
  final quantity = TextEditingController(text: '1');
  final description = TextEditingController();
  final picker = ImagePicker();
  List<XFile> photos = [];
  int? locationId;

  @override
  void dispose() {
    name.dispose();
    quantity.dispose();
    description.dispose();
    super.dispose();
  }

  void appendPhotos(Iterable<XFile> selected) {
    setState(() => photos = [...photos, ...selected].take(9).toList());
  }

  Future<void> pickFromCamera() async {
    final selected = await picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 82,
    );
    if (selected != null) appendPhotos([selected]);
  }

  Future<void> pickFromGallery() async {
    final selected = await picker.pickMultiImage(imageQuality: 82);
    if (selected.isNotEmpty) appendPhotos(selected);
  }

  Future<void> pickFromDocuments() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: const ['jpg', 'jpeg', 'png', 'webp'],
    );
    if (result == null) return;
    appendPhotos(
      result.files
          .where((file) => file.path != null)
          .map((file) => XFile(file.path!, name: file.name)),
    );
  }

  Future<void> pickPhotos() async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 4, 18, 18),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Tambahkan foto barang',
                style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 6),
              const Text(
                'Ambil foto langsung atau pilih gambar yang sudah tersimpan.',
              ),
              const SizedBox(height: 18),
              FilledButton.icon(
                onPressed: () {
                  Navigator.pop(sheetContext);
                  pickFromCamera();
                },
                icon: const Icon(Icons.camera_alt_outlined),
                label: const Text('Buka Kamera'),
              ),
              const SizedBox(height: 9),
              OutlinedButton.icon(
                onPressed: () {
                  Navigator.pop(sheetContext);
                  pickFromGallery();
                },
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('Pilih dari Galeri'),
              ),
              const SizedBox(height: 9),
              OutlinedButton.icon(
                onPressed: () {
                  Navigator.pop(sheetContext);
                  pickFromDocuments();
                },
                icon: const Icon(Icons.folder_open_outlined),
                label: const Text('Pilih dari Dokumen'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> submit() async {
    if (!formKey.currentState!.validate()) return;
    final state = context.read<LaboranProvider>();
    final success = await state.createInventory(
      name: name.text.trim(),
      quantity: int.parse(quantity.text),
      locationId: locationId!,
      description: description.text.trim(),
      photos: photos,
    );
    if (!mounted) return;
    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Inventaris berhasil ditambahkan.')),
      );
      Navigator.pop(context);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(state.error ?? 'Gagal menambah inventaris.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<LaboranProvider>();
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Tambah Inventaris',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      body: Form(
        key: formKey,
        child: ListView(
          padding: const EdgeInsets.all(18),
          children: [
            TextFormField(
              controller: name,
              decoration: const InputDecoration(labelText: 'Nama barang'),
              validator: (v) => v == null || v.trim().isEmpty
                  ? 'Nama barang wajib diisi.'
                  : null,
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: quantity,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Jumlah stok'),
              validator: (v) =>
                  (int.tryParse(v ?? '') ?? 0) < 1 ? 'Jumlah minimal 1.' : null,
            ),
            const SizedBox(height: 14),
            DropdownButtonFormField<int>(
              initialValue: locationId,
              decoration: const InputDecoration(
                labelText: 'Lokasi penyimpanan',
              ),
              items: state.locations
                  .map(
                    (item) => DropdownMenuItem(
                      value: item['id'] as int,
                      child: Text(item['nama'] as String),
                    ),
                  )
                  .toList(),
              onChanged: (value) => setState(() => locationId = value),
              validator: (value) =>
                  value == null ? 'Pilih lokasi penyimpanan.' : null,
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: description,
              minLines: 3,
              maxLines: 5,
              decoration: const InputDecoration(
                labelText: 'Keterangan (opsional)',
              ),
            ),
            const SizedBox(height: 18),
            OutlinedButton.icon(
              onPressed: pickPhotos,
              icon: const Icon(Icons.add_photo_alternate_outlined),
              label: Text(
                photos.isEmpty
                    ? 'Pilih beberapa foto'
                    : '${photos.length} foto dipilih',
              ),
            ),
            const SizedBox(height: 8),
            if (photos.isNotEmpty) ...[
              SizedBox(
                height: 92,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: photos.length,
                  separatorBuilder: (_, _) => const SizedBox(width: 8),
                  itemBuilder: (context, index) => Stack(
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(14),
                        child: Image.file(
                          File(photos[index].path),
                          width: 92,
                          height: 92,
                          fit: BoxFit.cover,
                        ),
                      ),
                      Positioned(
                        right: 4,
                        top: 4,
                        child: InkWell(
                          onTap: () => setState(() => photos.removeAt(index)),
                          child: Container(
                            padding: const EdgeInsets.all(4),
                            decoration: BoxDecoration(
                              color: Colors.black.withValues(alpha: .66),
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(
                              Icons.close,
                              size: 15,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 10),
            ],
            const Text(
              'Foto pertama menjadi sampul. Maksimal 9 foto, masing-masing 5 MB.',
              style: TextStyle(color: Color(0xFF64748B), fontSize: 12),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: state.submitting ? null : submit,
              icon: state.submitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.save_outlined),
              label: Text(
                state.submitting ? 'Menyimpan...' : 'Simpan Inventaris',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
