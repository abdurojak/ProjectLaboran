class AppConstants {
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://lab1.trisakti.ac.id/labhub/api/mobile/v1/',
  );
}
