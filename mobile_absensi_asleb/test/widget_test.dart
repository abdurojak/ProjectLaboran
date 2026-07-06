import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_absensi_asleb/widgets/status_badge.dart';

void main() {
  testWidgets('status absensi tampil dengan label yang sesuai', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: StatusBadge(status: 'sudah_absen')),
      ),
    );

    expect(find.text('Sudah Absen'), findsOneWidget);
    expect(find.byIcon(Icons.check_circle_outline), findsOneWidget);
  });
}
