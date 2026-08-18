import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/ai/presentation/ai_page.dart';
import '../../features/cases/presentation/cases_page.dart';
import '../../features/client_candidates/presentation/client_candidate_details_page.dart';
import '../../features/client_candidates/presentation/client_candidates_bulk_page.dart';
import '../../features/clients/presentation/client_details_page.dart';
import '../../features/clients/presentation/clients_page.dart';
import '../../features/dashboard/presentation/dashboard_page.dart';
import '../../features/documents/presentation/documents_page.dart';
import '../../features/documents/application/documents_controller.dart';
import '../../features/documents/domain/document_filters.dart';
import '../../features/settings/presentation/settings_page.dart';
import '../../features/projects/presentation/projects_page.dart';
import '../../features/projects/presentation/project_details_page.dart';
import '../../features/inspections/presentation/inspections_page.dart';
import '../../features/inspections/presentation/inspection_details_page.dart';
import '../../features/system_control/presentation/system_control_page.dart';
import '../../features/global_search/presentation/global_search_page.dart';
import '../widgets/app_shell.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/dashboard',
  routes: <RouteBase>[
    ShellRoute(
      builder: (BuildContext context, GoRouterState state, Widget child) {
        return AppShell(currentLocation: state.uri.toString(), child: child);
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
          path: '/client-candidates',
          builder: (BuildContext context, GoRouterState state) {
            return const ClientCandidatesBulkPage();
          },
        ),
        GoRoute(
          path: '/client-candidates/:candidateId',
          builder: (BuildContext context, GoRouterState state) {
            final int? candidateId = int.tryParse(
              state.pathParameters['candidateId'] ?? '',
            );

            if (candidateId == null || candidateId <= 0) {
              return const ClientCandidatesBulkPage();
            }

            return ClientCandidateDetailsPage(candidateId: candidateId);
          },
        ),
        GoRoute(
          path: '/clients/:clientId',
          builder: (BuildContext context, GoRouterState state) {
            final int? clientId = int.tryParse(
              state.pathParameters['clientId'] ?? '',
            );

            if (clientId == null || clientId <= 0) {
              return const ClientsPage();
            }

            final int? emailSourceId = int.tryParse(
              state.uri.queryParameters['email_source_id'] ?? '',
            );
            return ClientDetailsPage(
              clientId: clientId,
              emailSourceId: emailSourceId != null && emailSourceId > 0
                  ? emailSourceId
                  : null,
            );
          },
        ),
        GoRoute(
          path: '/projects',
          builder: (BuildContext context, GoRouterState state) =>
              const ProjectsPage(),
        ),
        GoRoute(
          path: '/projects/:projectId',
          builder: (BuildContext context, GoRouterState state) {
            final id = int.tryParse(state.pathParameters['projectId'] ?? '');
            return id == null
                ? const ProjectsPage()
                : ProjectDetailsPage(projectId: id);
          },
        ),
        GoRoute(
          path: '/inspections',
          builder: (BuildContext context, GoRouterState state) =>
              const InspectionsPage(),
        ),
        GoRoute(
          path: '/inspections/:inspectionId',
          builder: (BuildContext context, GoRouterState state) {
            final id = int.tryParse(state.pathParameters['inspectionId'] ?? '');
            final String? returnPath = AppNavigationPolicy.detailReturnPath(
              state.uri.queryParameters['return_to'],
            );
            return id == null
                ? const InspectionsPage()
                : InspectionDetailsPage(
                    inspectionId: id,
                    returnPath: returnPath,
                  );
          },
        ),
        GoRoute(
          path: '/documents',
          builder: (BuildContext context, GoRouterState state) {
            final int? clientId = int.tryParse(
              state.uri.queryParameters['client_id'] ?? '',
            );
            final String? clientName = state.uri.queryParameters['client_name']
                ?.trim();
            final int? projectId = int.tryParse(
              state.uri.queryParameters['project_id'] ?? '',
            );
            final int? inspectionId = int.tryParse(
              state.uri.queryParameters['inspection_id'] ?? '',
            );
            final int? documentId = int.tryParse(
              state.uri.queryParameters['document_id'] ?? '',
            );
            final DocumentFilters filters = clientId != null && clientId > 0
                ? DocumentFilters(
                    clientId: clientId,
                    clientName: clientName?.isNotEmpty == true
                        ? clientName
                        : 'Klient #$clientId',
                    projectId: projectId,
                    inspectionId: inspectionId,
                    documentId: documentId,
                  )
                : DocumentFilters(
                    projectId: projectId,
                    inspectionId: inspectionId,
                    documentId: documentId,
                  );

            return ProviderScope(
              overrides: [
                documentsControllerProvider.overrideWith(
                  () => DocumentsController(initialFilters: filters),
                ),
              ],
              child: const DocumentsPage(),
            );
          },
        ),
        GoRoute(
          path: '/ai',
          builder: (BuildContext context, GoRouterState state) {
            return const AiPage();
          },
        ),
        GoRoute(
          path: '/system',
          builder: (BuildContext context, GoRouterState state) {
            return const SystemControlPage();
          },
        ),
        GoRoute(
          path: '/search',
          builder: (BuildContext context, GoRouterState state) {
            return GlobalSearchPage(
              initialQuery: state.uri.queryParameters['q'] ?? '',
            );
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
