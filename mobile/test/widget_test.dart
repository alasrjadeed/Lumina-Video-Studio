import 'package:flutter_test/flutter_test.dart';
import 'package:lumina_mobile_app/app.dart';

void main() {
  testWidgets('App starts', (WidgetTester tester) async {
    await tester.pumpWidget(const LuminaApp());
    expect(find.text('Lumina'), findsOneWidget);
  });
}
