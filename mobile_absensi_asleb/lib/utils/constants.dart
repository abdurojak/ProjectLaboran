class AppConstants {
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.24.80.245:8000/api/mobile/v1/',
  );
}
