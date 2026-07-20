import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';

import '../models/inventory_item.dart';
import '../models/loan_item.dart';
import '../services/api_exception.dart';
import '../services/api_service.dart';

class LaboranProvider extends ChangeNotifier {
  LaboranProvider(this.api);

  final ApiService api;
  bool loading = false;
  bool submitting = false;
  String? error;
  Map<String, dynamic> summary = {};
  List<InventoryItem> inventory = [];
  List<LoanItem> loans = [];
  List<Map<String, dynamic>> locations = [];

  Future<void> loadDashboard() async {
    await _load(() async {
      final data = await api.laboranDashboard();
      summary = Map<String, dynamic>.from(data['summary'] as Map? ?? {});
    });
  }

  Future<void> loadInventory() async {
    await _load(() async {
      inventory = await api.laboranInventory();
      locations = await api.laboranLocations();
    });
  }

  Future<void> loadLoans() async {
    await _load(() async => loans = await api.laboranLoans());
  }

  Future<bool> createInventory({
    required String name,
    required int quantity,
    required int locationId,
    required String description,
    required List<XFile> photos,
  }) async {
    submitting = true;
    error = null;
    notifyListeners();
    try {
      final item = await api.createLaboranInventory(
        name: name,
        quantity: quantity,
        locationId: locationId,
        description: description,
        photos: photos,
      );
      inventory = [item, ...inventory];
      return true;
    } on ApiException catch (exception) {
      error = exception.message;
      return false;
    } finally {
      submitting = false;
      notifyListeners();
    }
  }

  Future<bool> updateLoanStatus(LoanItem loan, String status) async {
    submitting = true;
    error = null;
    notifyListeners();
    try {
      final updated = await api.updateLaboranLoanStatus(loan.id, status);
      loans = loans
          .map((item) => item.id == updated.id ? updated : item)
          .toList();
      return true;
    } on ApiException catch (exception) {
      error = exception.message;
      return false;
    } finally {
      submitting = false;
      notifyListeners();
    }
  }

  Future<void> _load(Future<void> Function() action) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      await action();
    } on ApiException catch (exception) {
      error = exception.message;
    } finally {
      loading = false;
      notifyListeners();
    }
  }
}
