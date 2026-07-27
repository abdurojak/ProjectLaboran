import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

import '../models/attendance.dart';
import '../models/inventory_item.dart';
import '../models/loan_item.dart';
import '../models/schedule.dart';
import '../models/user_profile.dart';
import '../utils/constants.dart';
import 'api_exception.dart';
import 'token_storage.dart';

class ApiService {
  ApiService(this.storage)
    : dio = Dio(
        BaseOptions(
          baseUrl: AppConstants.apiBaseUrl,
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 25),
          headers: {'Accept': 'application/json'},
        ),
      ) {
    dio.interceptors.add(
      QueuedInterceptorsWrapper(
        onRequest: (options, handler) async {
          var token = await storage.accessToken;
          if (!_isAuthenticationPath(options.path) &&
              token != null &&
              _isTokenExpiring(token)) {
            token = await _refreshAccessToken();
            if (token == null) {
              return handler.reject(
                DioException(
                  requestOptions: options,
                  response: Response(
                    requestOptions: options,
                    statusCode: 401,
                    data: const {
                      'detail':
                          'Sesi Anda sudah berakhir. Silakan login kembali.',
                    },
                  ),
                ),
              );
            }
          }
          if (token != null) options.headers['Authorization'] = 'Bearer $token';
          handler.next(options);
        },
        onError: (error, handler) async {
          if (error.response?.statusCode != 401 ||
              error.requestOptions.extra['retried'] == true) {
            return handler.next(error);
          }
          final access = await _refreshAccessToken();
          if (access == null) return handler.next(error);

          final request = error.requestOptions;
          request.extra['retried'] = true;
          request.headers['Authorization'] = 'Bearer $access';
          return handler.resolve(await dio.fetch(request));
        },
      ),
    );
  }

  final Dio dio;
  final TokenStorage storage;
  void Function()? onSessionExpired;
  Future<String?>? _activeRefresh;

  bool _isAuthenticationPath(String path) =>
      path.endsWith('auth/login/') || path.endsWith('auth/refresh/');

  bool _isTokenExpiring(String token) {
    try {
      final parts = token.split('.');
      if (parts.length != 3) return true;
      final payload = jsonDecode(
        utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))),
      );
      final expiresAt = DateTime.fromMillisecondsSinceEpoch(
        (payload['exp'] as num).toInt() * 1000,
        isUtc: true,
      );
      return expiresAt.isBefore(
        DateTime.now().toUtc().add(const Duration(seconds: 45)),
      );
    } catch (_) {
      return true;
    }
  }

  Future<String?> _refreshAccessToken() {
    final activeRefresh = _activeRefresh;
    if (activeRefresh != null) return activeRefresh;

    final refresh = _performTokenRefresh();
    _activeRefresh = refresh;
    return refresh.whenComplete(() {
      if (identical(_activeRefresh, refresh)) _activeRefresh = null;
    });
  }

  Future<String?> _performTokenRefresh() async {
    final refresh = await storage.refreshToken;
    if (refresh == null) {
      onSessionExpired?.call();
      return null;
    }

    try {
      final refreshDio = Dio(BaseOptions(baseUrl: AppConstants.apiBaseUrl));
      final response = await refreshDio.post(
        'auth/refresh/',
        data: {'refresh': refresh},
      );
      final tokens = Map<String, dynamic>.from(response.data['tokens'] as Map);
      await storage.saveTokens(tokens);
      return tokens['access'] as String;
    } catch (_) {
      await storage.clear();
      onSessionExpired?.call();
      return null;
    }
  }

  Future<UserProfile> login(String identifier, String password) async {
    try {
      final response = await dio.post(
        'auth/login/',
        data: {'identifier': identifier, 'password': password},
      );
      await storage.saveTokens(
        Map<String, dynamic>.from(response.data['tokens'] as Map),
      );
      return UserProfile.fromJson(
        Map<String, dynamic>.from(response.data['user'] as Map),
      );
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<void> logout() async {
    try {
      await dio.post('auth/logout/');
    } catch (_) {
      // Token lokal tetap wajib dibersihkan saat server tidak terjangkau.
    }
    await storage.clear();
  }

  Future<Map<String, dynamic>> profile() => _getMap('profile/');
  Future<Map<String, dynamic>> dashboard() => _getMap('dashboard/');
  Future<Map<String, dynamic>> laboranDashboard() =>
      _getMap('laboran/dashboard/');
  Future<Map<String, dynamic>> locationConfig() => _getMap('config/location/');

  Future<List<PraktikumSchedule>> schedules() async {
    final data = await _getMap('schedules/');
    return (data['results'] as List)
        .map(
          (item) => PraktikumSchedule.fromJson(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList();
  }

  Future<Map<String, dynamic>> scheduleDetail(int id) =>
      _getMap('schedules/$id/');

  Future<String> askChatbot(String message) async {
    try {
      final response = await dio.post('chatbot/', data: {'message': message});
      final data = Map<String, dynamic>.from(response.data as Map);
      return data['answer'] as String? ?? 'Maaf, bot belum memberi jawaban.';
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<Map<String, dynamic>> adminChat() => _getMap('chat-admin/');

  Future<Map<String, dynamic>> startAdminChat() async {
    try {
      final response = await dio.post('chat-admin/', data: {'action': 'start'});
      return Map<String, dynamic>.from(response.data as Map);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<Map<String, dynamic>> sendAdminMessage(String message) async {
    try {
      final response = await dio.post(
        'chat-admin/',
        data: {'message': message},
      );
      return Map<String, dynamic>.from(response.data as Map);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<List<Map<String, dynamic>>> laboranLocations() async {
    final data = await _getMap('laboran/locations/');
    return (data['results'] as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  Future<List<InventoryItem>> laboranInventory() async {
    final data = await _getMap('laboran/inventory/');
    return (data['results'] as List)
        .map(
          (item) =>
              InventoryItem.fromJson(Map<String, dynamic>.from(item as Map)),
        )
        .toList();
  }

  Future<InventoryItem> laboranInventoryDetail(int id) async {
    final data = await _getMap('laboran/inventory/$id/');
    return InventoryItem.fromJson(data);
  }

  Future<void> deleteLaboranInventory(int id) async {
    try {
      await dio.delete('laboran/inventory/$id/');
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<InventoryItem> updateLaboranInventory({
    required int id,
    required String name,
    required int quantity,
    required int locationId,
    required String description,
  }) async {
    try {
      final response = await dio.patch(
        'laboran/inventory/$id/',
        data: {
          'nama': name,
          'jumlah': quantity,
          'lokasi_id': locationId,
          'keterangan': description,
        },
      );
      return InventoryItem.fromJson(
        Map<String, dynamic>.from(response.data as Map),
      );
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<InventoryItem> createLaboranInventory({
    required String name,
    required int quantity,
    required int locationId,
    required String description,
    required List<XFile> photos,
  }) async {
    try {
      final data = FormData();
      data.fields.addAll([
        MapEntry('nama', name),
        MapEntry('jumlah', '$quantity'),
        MapEntry('lokasi_id', '$locationId'),
        MapEntry('keterangan', description),
      ]);
      for (var index = 0; index < photos.length; index++) {
        final photo = photos[index];
        final isPng = photo.name.toLowerCase().endsWith('.png');
        data.files.add(
          MapEntry(
            index == 0 ? 'foto' : 'foto_galeri',
            await MultipartFile.fromFile(
              photo.path,
              filename: photo.name,
              contentType: DioMediaType('image', isPng ? 'png' : 'jpeg'),
            ),
          ),
        );
      }
      final response = await dio.post('laboran/inventory/', data: data);
      return InventoryItem.fromJson(
        Map<String, dynamic>.from(response.data as Map),
      );
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<List<LoanItem>> laboranLoans() async {
    final data = await _getMap('laboran/loans/');
    return (data['results'] as List)
        .map(
          (item) => LoanItem.fromJson(Map<String, dynamic>.from(item as Map)),
        )
        .toList();
  }

  Future<LoanItem> updateLaboranLoanStatus(int id, String status) async {
    try {
      final response = await dio.post(
        'laboran/loans/$id/status/',
        data: {'status': status},
      );
      return LoanItem.fromJson(Map<String, dynamic>.from(response.data as Map));
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<List<AttendanceRecord>> history() async {
    final data = await _getMap('attendance/history/');
    return (data['results'] as List)
        .map(
          (item) =>
              AttendanceRecord.fromJson(Map<String, dynamic>.from(item as Map)),
        )
        .toList();
  }

  Future<AttendanceRecord> checkIn({
    required int scheduleId,
    required XFile photo,
    XFile? video,
  }) async {
    try {
      final photoType = photo.name.toLowerCase().endsWith('.png')
          ? DioMediaType('image', 'png')
          : DioMediaType('image', 'jpeg');
      final data = <String, dynamic>{
        'jadwal_id': scheduleId,
        'foto_absensi': await MultipartFile.fromFile(
          photo.path,
          filename: photo.name,
          contentType: photoType,
        ),
      };
      if (video != null) {
        data['video_absensi'] = await MultipartFile.fromFile(
          video.path,
          filename: video.name,
          contentType: DioMediaType('video', 'mp4'),
        );
      }
      final response = await dio.post(
        'attendance/check-in/',
        data: FormData.fromMap(data),
      );
      return AttendanceRecord.fromJson(
        Map<String, dynamic>.from(response.data as Map),
      );
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<Map<String, dynamic>> _getMap(String path) async {
    try {
      final response = await dio.get(path);
      return Map<String, dynamic>.from(response.data as Map);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}
