import 'package:dio/dio.dart';

class ApiException implements Exception {
  const ApiException(this.message);
  final String message;

  factory ApiException.fromDio(DioException error) {
    final data = error.response?.data;
    if (data is Map<String, dynamic>) {
      final detail = data['detail'];
      if (detail is String) return ApiException(detail);
      for (final value in data.values) {
        if (value is List && value.isNotEmpty) {
          return ApiException(value.first.toString());
        }
      }
    }
    if (error.type == DioExceptionType.connectionError ||
        error.type == DioExceptionType.connectionTimeout) {
      return const ApiException('Tidak dapat terhubung ke server LabHub.');
    }
    return const ApiException('Terjadi kesalahan. Silakan coba lagi.');
  }

  @override
  String toString() => message;
}
