import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

import '../models/attendance.dart';
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
          final token = await storage.accessToken;
          if (token != null) options.headers['Authorization'] = 'Bearer $token';
          handler.next(options);
        },
        onError: (error, handler) async {
          if (error.response?.statusCode != 401 ||
              error.requestOptions.extra['retried'] == true) {
            return handler.next(error);
          }
          final refresh = await storage.refreshToken;
          if (refresh == null) return handler.next(error);
          try {
            final refreshDio = Dio(
              BaseOptions(baseUrl: AppConstants.apiBaseUrl),
            );
            final response = await refreshDio.post(
              'auth/refresh/',
              data: {'refresh': refresh},
            );
            final tokens = Map<String, dynamic>.from(
              response.data['tokens'] as Map,
            );
            await storage.saveTokens(tokens);
            final request = error.requestOptions;
            request.extra['retried'] = true;
            request.headers['Authorization'] = 'Bearer ${tokens['access']}';
            return handler.resolve(await dio.fetch(request));
          } catch (_) {
            await storage.clear();
            return handler.next(error);
          }
        },
      ),
    );
  }

  final Dio dio;
  final TokenStorage storage;

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
