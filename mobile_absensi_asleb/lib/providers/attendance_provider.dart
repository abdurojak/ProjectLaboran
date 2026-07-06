import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';

import '../models/attendance.dart';
import '../models/schedule.dart';
import '../models/user_profile.dart';
import '../services/api_exception.dart';
import '../services/api_service.dart';

class AttendanceProvider extends ChangeNotifier {
  AttendanceProvider(this.api);

  final ApiService api;
  bool loading = false;
  String? error;
  UserProfile? profile;
  List<String> courses = [];
  List<PraktikumSchedule> todaySchedules = [];
  List<PraktikumSchedule> schedules = [];
  List<AttendanceRecord> history = [];
  Map<String, dynamic>? locationConfig;

  Future<void> loadDashboard() async {
    await _guard(() async {
      final data = await api.dashboard();
      profile = UserProfile.fromJson(
        Map<String, dynamic>.from(data['profile'] as Map),
      );
      courses = List<String>.from(data['mata_kuliah'] as List);
      todaySchedules = (data['jadwal_hari_ini'] as List)
          .map(
            (item) => PraktikumSchedule.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList();
    });
  }

  Future<void> loadSchedules() async =>
      _guard(() async => schedules = await api.schedules());
  Future<void> loadHistory() async =>
      _guard(() async => history = await api.history());

  Future<Map<String, dynamic>> loadScheduleDetail(int id) =>
      api.scheduleDetail(id);

  Future<void> ensureLocationConfig() async {
    locationConfig ??= await api.locationConfig();
  }

  Future<AttendanceRecord> checkIn({
    required PraktikumSchedule schedule,
    required XFile photo,
    XFile? video,
  }) async {
    final record = await api.checkIn(
      scheduleId: schedule.id,
      photo: photo,
      video: video,
    );
    await Future.wait([loadDashboard(), loadSchedules(), loadHistory()]);
    return record;
  }

  Future<void> _guard(Future<void> Function() action) async {
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
