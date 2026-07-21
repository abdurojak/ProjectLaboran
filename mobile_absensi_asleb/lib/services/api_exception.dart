import 'package:dio/dio.dart';

class ApiException implements Exception {
  const ApiException(this.message);
  final String message;

  factory ApiException.fromDio(DioException error) {
    final data = error.response?.data;
    if (data is Map) {
      final detail = data['detail'];
      if (detail is String) return ApiException(detail);
      final message = data['message'];
      if (message is String) return ApiException(message);
      for (final value in data.values) {
        final parsed = _firstMessage(value);
        if (parsed != null) return ApiException(parsed);
      }
    }
    final statusCode = error.response?.statusCode;
    if (statusCode != null && statusCode >= 500) {
      return const ApiException(
        'Server LabHub sedang bermasalah saat memproses data.',
      );
    }
    if (error.type == DioExceptionType.connectionError ||
        error.type == DioExceptionType.connectionTimeout) {
      return const ApiException('Tidak dapat terhubung ke server LabHub.');
    }
    return const ApiException('Terjadi kesalahan. Silakan coba lagi.');
  }

  static String? _firstMessage(Object? value) {
    if (value is String && value.trim().isNotEmpty) return value;
    if (value is List && value.isNotEmpty) {
      return _firstMessage(value.first);
    }
    if (value is Map && value.isNotEmpty) {
      for (final nested in value.values) {
        final parsed = _firstMessage(nested);
        if (parsed != null) return parsed;
      }
    }
    return null;
  }

  @override
  String toString() => message;
}
