import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../features/ai/presentation/ai_page.dart';
import '../../features/cases/presentation/cases_page.dart';
import '../../features/clients/presentation/clients_page.dart';
import '../../features/dashboard/presentation/dashboard_page.dart';
import '../../features/documents/presentation/documents_page.dart';
import '../../features/settings/presentation/settings_page.dart';
import '../widgets/app_shell.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/dashboard',
  routes: <RouteBase>[
    ShellRoute(
      builder: (BuildContext context, GoRouterState state, Widget child) {
        return AppShell(currentLocation: state.uri.path, child: child);
      },
      routes: <RouteBase>[
        GoRoute(
          path: '/dashboard',
          builder: (BuildContext context, GoRouterState state) {
            return const DashboardPage();
          },
        ),
        GoRoute(
          path: '/cases',
          builder: (BuildContext context, GoRouterState state) {
            return const CasesPage();
          },
        ),
        GoRoute(
          path: '/clients',
          builder: (BuildContext context, GoRouterState state) {
            return const ClientsPage();
          },
        ),
        GoRoute(
          path: '/documents',
          builder: (BuildContext context, GoRouterState state) {
            return const DocumentsPage();
          },
        ),
        GoRoute(
          path: '/ai',
          builder: (BuildContext context, GoRouterState state) {
            return const AiPage();
          },
        ),
        GoRoute(
          path: '/settings',
          builder: (BuildContext context, GoRouterState state) {
            return const SettingsPage();
          },
        ),
      ],
    ),
  ],
);
