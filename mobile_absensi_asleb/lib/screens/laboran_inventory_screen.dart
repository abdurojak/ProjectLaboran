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
              ],
            ),
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

  Future<void> pickPhotos() async {
    final selected = await picker.pickMultiImage(imageQuality: 82);
    if (selected.isNotEmpty) setState(() => photos = selected.take(9).toList());
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
