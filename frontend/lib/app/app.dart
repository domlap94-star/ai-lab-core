import 'package:flutter/material.dart';
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

class App extends ConsumerWidget {
  const App({super.key});

  MaterialApp _materialApp({required Widget home}) {
    return MaterialApp(
      title: 'AI LAB',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      home: home,
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<AuthState> authState = ref.watch(authControllerProvider);

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
          title: 'AI LAB',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          darkTheme: AppTheme.dark,
          themeMode: ThemeMode.system,
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
              'AI LAB',
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
