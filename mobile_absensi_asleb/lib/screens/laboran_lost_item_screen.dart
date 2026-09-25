import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../providers/laboran_provider.dart';

class LaboranLostItemScreen extends StatefulWidget {
  const LaboranLostItemScreen({super.key});

  @override
  State<LaboranLostItemScreen> createState() => _LaboranLostItemScreenState();
}

class _LaboranLostItemScreenState extends State<LaboranLostItemScreen> {
  final formKey = GlobalKey<FormState>();
  final name = TextEditingController();
  final type = TextEditingController();
  final quantity = TextEditingController(text: '1');
  final location = TextEditingController();
  final ownerName = TextEditingController();
  final ownerNim = TextEditingController();
  final picker = ImagePicker();
  DateTime foundDate = DateTime.now();
  XFile? photo;

  @override
  void dispose() {
    name.dispose();
    type.dispose();
    quantity.dispose();
    location.dispose();
    ownerName.dispose();
    ownerNim.dispose();
    super.dispose();
  }

  Future<void> chooseDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: foundDate,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
    );
    if (selected != null) setState(() => foundDate = selected);
  }

  Future<void> choosePhoto(ImageSource source) async {
    final selected = await picker.pickImage(source: source, imageQuality: 82);
    if (selected != null) setState(() => photo = selected);
  }

  Future<void> photoMenu() => showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (sheetContext) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Foto barang',
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () {
                Navigator.pop(sheetContext);
                choosePhoto(ImageSource.camera);
              },
              icon: const Icon(Icons.camera_alt_outlined),
              label: const Text('Ambil dari Kamera'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: () {
                Navigator.pop(sheetContext);
                choosePhoto(ImageSource.gallery);
              },
              icon: const Icon(Icons.photo_library_outlined),
              label: const Text('Pilih dari Galeri'),
            ),
          ],
        ),
      ),
    ),
  );

  Future<void> submit() async {
    if (!formKey.currentState!.validate()) return;
    final state = context.read<LaboranProvider>();
    final code = await state.createLostItem(
      name: name.text.trim(),
      type: type.text.trim(),
      quantity: int.parse(quantity.text),
      location: location.text.trim(),
      foundDate: DateFormat('yyyy-MM-dd').format(foundDate),
      ownerName: ownerName.text.trim(),
      ownerNim: ownerNim.text.trim(),
      photo: photo,
    );
    if (!mounted) return;
    if (code != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Barang berhasil dicatat dengan kode $code.')),
      );
      Navigator.pop(context);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(state.error ?? 'Barang gagal disimpan.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<LaboranProvider>();
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Input Barang Hilang',
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
              validator: requiredText,
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: type,
              decoration: const InputDecoration(labelText: 'Jenis barang'),
              validator: requiredText,
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: quantity,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Jumlah'),
              validator: (value) => (int.tryParse(value ?? '') ?? 0) < 1
                  ? 'Jumlah minimal 1.'
                  : null,
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: location,
              decoration: const InputDecoration(labelText: 'Lokasi ditemukan'),
              validator: requiredText,
            ),
            const SizedBox(height: 14),
            ListTile(
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
                side: BorderSide(
                  color: Theme.of(context).colorScheme.outlineVariant,
                ),
              ),
              leading: const Icon(Icons.calendar_today_outlined),
              title: const Text('Tanggal ditemukan'),
              subtitle: Text(DateFormat('dd/MM/yyyy').format(foundDate)),
              onTap: chooseDate,
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: ownerName,
              decoration: const InputDecoration(
                labelText: 'Nama pemilik (opsional)',
              ),
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: ownerNim,
              decoration: const InputDecoration(
                labelText: 'NIM pemilik (opsional)',
              ),
            ),
            const SizedBox(height: 18),
            if (photo != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: Image.file(
                  File(photo!.path),
                  height: 210,
                  fit: BoxFit.cover,
                ),
              ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: photoMenu,
              icon: const Icon(Icons.add_a_photo_outlined),
              label: Text(photo == null ? 'Tambahkan Foto' : 'Ganti Foto'),
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
                  : const Icon(Icons.campaign_outlined),
              label: Text(
                state.submitting ? 'Menyimpan...' : 'Simpan dan Umumkan',
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String? requiredText(String? value) =>
      value == null || value.trim().isEmpty ? 'Bagian ini wajib diisi.' : null;
}
