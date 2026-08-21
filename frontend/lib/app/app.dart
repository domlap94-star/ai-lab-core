import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/router/app_router.dart';
import '../core/theme/app_theme.dart';
import '../features/app_update/application/update_provider.dart';
import '../features/app_update/domain/app_update.dart';
import '../features/app_update/presentation/required_update_page.dart';
import '../features/auth/application/auth_controller.dart';
import '../features/auth/application/auth_state.dart';
import '../features/auth/presentation/change_password_page.dart';
import '../features/auth/presentation/login_page.dart';

class App extends ConsumerStatefulWidget {
  const App({super.key});

  @override
  ConsumerState<App> createState() => _AppState();
}

class _AppState extends ConsumerState<App> {
  static const _locale = Locale('pl', 'PL');
  static const _localizationsDelegates = <LocalizationsDelegate<dynamic>>[
    GlobalMaterialLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
  ];
  MaterialApp _materialApp({required Widget home}) {
    return MaterialApp(
      title: 'NEXT Stabil',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      locale: _locale,
      supportedLocales: const <Locale>[_locale],
      localizationsDelegates: _localizationsDelegates,
      home: home,
    );
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<AuthState> authState = ref.watch(authControllerProvider);

    ref.listen<AsyncValue<AuthState>>(authControllerProvider, (
      AsyncValue<AuthState>? previous,
      AsyncValue<AuthState> next,
    ) {
      if (previous?.value?.isAuthenticated == true &&
          next.hasValue &&
          next.requireValue.isAuthenticated != true) {
        appRouter.go('/dashboard');
      }
    });

    final AsyncValue<UpdateCheckResult> updateCheck = ref.watch(
      updateCheckProvider,
    );

    final UpdateCheckResult? updateResult = updateCheck.value;

    final bool nativeUpdateRequired =
        updateResult?.state == AppUpdateState.required &&
        (updateResult?.platform == AppUpdatePlatform.windows ||
            updateResult?.platform == AppUpdatePlatform.android);

    if (nativeUpdateRequired && updateResult != null) {
      return _materialApp(home: RequiredUpdatePage(result: updateResult));
    }

    return authState.when(
      loading: () {
        return _materialApp(home: const _ApplicationLoadingPage());
      },
      error: (Object error, StackTrace stackTrace) {
        return _materialApp(home: const LoginPage());
      },
      data: (AuthState state) {
        if (!state.isAuthenticated) {
          return _materialApp(home: const LoginPage());
        }

        if (state.user?.mustChangePassword == true) {
          return _materialApp(home: const ChangePasswordPage(forced: true));
        }

        return MaterialApp.router(
          title: 'NEXT Stabil',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          darkTheme: AppTheme.dark,
          themeMode: ThemeMode.system,
          locale: _locale,
          supportedLocales: const <Locale>[_locale],
          localizationsDelegates: _localizationsDelegates,
          routerConfig: appRouter,
        );
      },
    );
  }
}

class _ApplicationLoadingPage extends StatelessWidget {
  const _ApplicationLoadingPage();

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: theme.colorScheme.primary,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(
                Icons.hub,
                size: 38,
                color: theme.colorScheme.onPrimary,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'NEXT Stabil',
              style: theme.textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 24),
            const SizedBox(
              width: 28,
              height: 28,
              child: CircularProgressIndicator(strokeWidth: 3),
            ),
            const SizedBox(height: 16),
            Text(
              'Sprawdzanie sesji...',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
