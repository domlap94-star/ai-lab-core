import 'package:ai_lab/app/app.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/system_status/application/system_status_provider.dart';
import 'package:ai_lab/features/system_status/domain/backend_status.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('AI LAB displays login page for unauthenticated user', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 900);
    tester.view.devicePixelRatio = 1.0;

    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(
            _UnauthenticatedAuthController.new,
          ),
        ],
        child: const App(),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('AI LAB'), findsOneWidget);
    expect(find.text('Zaloguj się, aby przejść do systemu.'), findsOneWidget);
    expect(find.text('Nazwa użytkownika'), findsOneWidget);
    expect(find.text('Hasło'), findsOneWidget);
    expect(find.text('Zaloguj się'), findsOneWidget);
  });

  testWidgets('AI LAB displays dashboard for authenticated user', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1.0;

    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(_AuthenticatedAuthController.new),
          backendStatusProvider.overrideWith((Ref ref) async {
            return const BackendStatus(
              isOnline: true,
              application: 'AI-Lab',
              version: '0.1.0',
              environment: 'test',
              debug: true,
              latencyMilliseconds: 12,
              baseUrl: 'http://127.0.0.1:8000',
            );
          }),
        ],
        child: const App(),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('AI LAB'), findsOneWidget);
    expect(find.text('Dashboard'), findsWidgets);
    expect(find.text('Backend: ONLINE'), findsOneWidget);
    expect(find.text('0.1.0'), findsOneWidget);
    expect(find.text('12 ms'), findsOneWidget);
    expect(find.text('Aktywne sprawy'), findsOneWidget);
    expect(find.text('Dokumenty'), findsOneWidget);
    expect(find.text('Asystent AI'), findsOneWidget);
  });
}

class _UnauthenticatedAuthController extends AuthController {
  @override
  Future<AuthState> build() async {
    return const AuthState.unauthenticated();
  }
}

class _AuthenticatedAuthController extends AuthController {
  @override
  Future<AuthState> build() async {
    return const AuthState(
      session: AuthSession(
        accessToken: 'test-access-token',
        tokenType: 'bearer',
      ),
      user: CurrentUser(
        id: 1,
        username: 'admin',
        email: 'admin@example.com',
        role: 'admin',
        isActive: true,
      ),
    );
  }
}
