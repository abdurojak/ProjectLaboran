class AppConstants {
  static const appVersion = '1.0.5';
  static const appBuild = 6;
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://lab1.trisakti.ac.id/labhub/api/mobile/v1/',
  );
}
