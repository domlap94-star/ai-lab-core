import 'package:go_router/go_router.dart';

import '../../features/dashboard/presentation/dashboard_page.dart';

final GoRouter appRouter = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const DashboardPage(),
    ),
  ],
);