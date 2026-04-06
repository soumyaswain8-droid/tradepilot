import 'package:flutter_test/flutter_test.dart';
import 'package:tradepilot_app/main.dart';

void main() {
  testWidgets('TradePilot app smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const TradePilotApp());
    await tester.pump();
    // App starts without crashing
    expect(find.byType(TradePilotApp), findsOneWidget);
  });
}
