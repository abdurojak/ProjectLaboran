import 'package:geolocator/geolocator.dart';

import 'api_exception.dart';

class LocationService {
  Future<Position> currentPosition() async {
    final enabled = await Geolocator.isLocationServiceEnabled();
    if (!enabled) {
      throw const ApiException(
        'GPS belum aktif. Aktifkan layanan lokasi lalu coba lagi.',
      );
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied) {
      throw const ApiException(
        'Izin lokasi diperlukan untuk melakukan absensi.',
      );
    }
    if (permission == LocationPermission.deniedForever) {
      throw const ApiException(
        'Izin lokasi ditolak permanen. Buka pengaturan aplikasi untuk mengaktifkannya.',
      );
    }
    return Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 20),
      ),
    );
  }
}
