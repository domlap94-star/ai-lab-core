import 'package:ai_lab/app/app.dart';
import 'package:ai_lab/core/router/app_router.dart';
import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/app_update/application/update_provider.dart';
import 'package:ai_lab/features/app_version/application/app_version_provider.dart';
import 'package:ai_lab/features/app_version/domain/app_version_info.dart';
import 'package:ai_lab/features/system_status/application/system_status_provider.dart';
import 'package:ai_lab/features/system_status/domain/backend_status.dart';
import 'package:ai_lab/features/dashboard/application/dashboard_providers.dart';
import 'package:ai_lab/features/tasks/application/tasks_providers.dart';
import 'package:ai_lab/features/tasks/domain/work_item.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('NEXT Stabil displays login page for unauthenticated user', (
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
          appVersionProvider.overrideWith(
            (Ref ref) async =>
                const AppVersionInfo(version: '1.0.2', buildNumber: '23'),
          ),
          updateCheckProvider.overrideWith(
            (Ref ref) async => throw StateError('offline in branding test'),
          ),
        ],
        child: const App(),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Zaloguj się, aby przejść do systemu.'), findsOneWidget);
    expect(find.text('Nazwa użytkownika'), findsOneWidget);
    expect(find.text('Hasło'), findsOneWidget);
    expect(find.text('Zaloguj się'), findsOneWidget);
    expect(find.text('NEXT Stabil 1.0.2+23'), findsOneWidget);
    expect(
      tester.widget<MaterialApp>(find.byType(MaterialApp)).title,
      'NEXT Stabil',
    );
  });

  testWidgets('NEXT Stabil displays dashboard for authenticated user', (
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
          dashboardRecentMailProvider.overrideWith((Ref ref) async => []),
          dashboardRecentDocumentsProvider.overrideWith((Ref ref) async => []),
          dashboardRecentActivityProvider.overrideWith((Ref ref) async => []),
          calendarMonthProvider.overrideWith(
            (Ref ref, DateTime month) async => CalendarMonthData(
              year: month.year,
              month: month.month,
              items: const [],
              total: 0,
              dayCounts: const {},
              truncated: false,
            ),
          ),
        ],
        child: const App(),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Dashboard'), findsWidgets);
    expect(find.text('Backend: ONLINE'), findsOneWidget);
    expect(find.text('0.1.0'), findsOneWidget);
    expect(find.text('12 ms'), findsOneWidget);
    expect(find.text('Kalendarz i zadania'), findsOneWidget);
    expect(find.text('Maile'), findsWidgets);
    expect(find.text('Ostatnia aktywność'), findsOneWidget);
    expect(find.text('Dokumenty'), findsWidgets);
    expect(find.text('Asystent AI'), findsOneWidget);
  });

  testWidgets('expired session displays one clear login message', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(
            _ExpiredSessionAuthController.new,
          ),
          appVersionProvider.overrideWith(
            (Ref ref) async =>
                const AppVersionInfo(version: '1.0.2', buildNumber: '17'),
          ),
          updateCheckProvider.overrideWith(
            (Ref ref) async => throw StateError('offline in session test'),
          ),
        ],
        child: const App(),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.byKey(const Key('session-expired-message')), findsOneWidget);
    expect(find.text('Sesja wygasła. Zaloguj się ponownie.'), findsOneWidget);
    expect(find.textContaining('DioException'), findsNothing);
  });

  testWidgets('session loss resets protected navigation history', (
    WidgetTester tester,
  ) async {
    final _SessionTransitionAuthController controller =
        _SessionTransitionAuthController();
    appRouter.go('/dashboard');
    addTearDown(() => appRouter.go('/dashboard'));

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(() => controller),
          updateCheckProvider.overrideWith(
            (Ref ref) async => throw StateError('offline in session test'),
          ),
        ],
        child: const App(),
      ),
    );
    await tester.pumpAndSettle();

    appRouter.go('/settings');
    await tester.pumpAndSettle();
    expect(find.text('Ustawienia'), findsWidgets);

    controller.expire();
    await tester.pumpAndSettle();

    expect(find.text('Zaloguj się, aby przejść do systemu.'), findsOneWidget);
    expect(find.text('Ustawienia'), findsNothing);
    expect(
      appRouter.routerDelegate.currentConfiguration.uri.path,
      '/dashboard',
    );
  });

  testWidgets('admin Settings exposes Change History navigation', (
    WidgetTester tester,
  ) async {
    appRouter.go('/settings');
    addTearDown(() => appRouter.go('/dashboard'));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(_AuthenticatedAuthController.new),
          backendStatusProvider.overrideWith(
            (Ref ref) async => const BackendStatus(
              isOnline: true,
              application: 'AI-Lab',
              version: 'test',
              environment: 'test',
              debug: false,
              latencyMilliseconds: 1,
              baseUrl: 'https://example.invalid',
            ),
          ),
          appVersionProvider.overrideWith(
            (Ref ref) async =>
                const AppVersionInfo(version: '1.0.2', buildNumber: '22'),
          ),
          updateCheckProvider.overrideWith(
            (Ref ref) async => throw StateError('offline in navigation test'),
          ),
        ],
        child: const App(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Historia zmian'), findsOneWidget);
  });

  testWidgets('normal user Settings hides Change History navigation', (
    WidgetTester tester,
  ) async {
    appRouter.go('/settings');
    addTearDown(() => appRouter.go('/dashboard'));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(_NormalUserAuthController.new),
          backendStatusProvider.overrideWith(
            (Ref ref) async => const BackendStatus(
              isOnline: true,
              application: 'AI-Lab',
              version: 'test',
              environment: 'test',
              debug: false,
              latencyMilliseconds: 1,
              baseUrl: 'https://example.invalid',
            ),
          ),
          appVersionProvider.overrideWith(
            (Ref ref) async =>
                const AppVersionInfo(version: '1.0.2', buildNumber: '22'),
          ),
          updateCheckProvider.overrideWith(
            (Ref ref) async => throw StateError('offline in navigation test'),
          ),
        ],
        child: const App(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Historia zmian'), findsNothing);
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
        mustChangePassword: false,
        passwordResetRequested: false,
      ),
    );
  }
}

class _ExpiredSessionAuthController extends AuthController {
  @override
  Future<AuthState> build() async {
    return const AuthState.unauthenticated(
      notice: 'Sesja wygasła. Zaloguj się ponownie.',
    );
  }
}

class _NormalUserAuthController extends AuthController {
  @override
  Future<AuthState> build() async {
    return const AuthState(
      session: AuthSession(
        accessToken: 'normal-user-token',
        tokenType: 'bearer',
      ),
      user: CurrentUser(
        id: 2,
        username: 'user',
        email: 'user@example.com',
        role: 'User',
        isActive: true,
        mustChangePassword: false,
        passwordResetRequested: false,
      ),
    );
  }
}

class _SessionTransitionAuthController extends _AuthenticatedAuthController {
  void expire() {
    state = const AsyncData<AuthState>(
      AuthState.unauthenticated(notice: 'Sesja wygasła. Zaloguj się ponownie.'),
    );
  }
}
