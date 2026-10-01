class AppConstants {
  static const appVersion = '1.0.8';
  static const appBuild = 9;
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://lab1.trisakti.ac.id/labhub/api/mobile/v1/',
  );
}
