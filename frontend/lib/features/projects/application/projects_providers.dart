import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../data/projects_api.dart';
import '../domain/project.dart';

final projectsApiProvider = Provider<ProjectsApi>(
  (ref) => ProjectsApi(ref.watch(dioProvider)),
);
AuthSession requireProjectSession(Ref ref) {
  final session = ref.watch(authControllerProvider).value?.session;
  if (session == null) throw StateError('Brak aktywnej sesji.');
  return session;
}

AuthSession requireProjectWidgetSession(WidgetRef ref) {
  final session = ref.read(authControllerProvider).value?.session;
  if (session == null) throw StateError('Brak aktywnej sesji.');
  return session;
}

class ProjectQuery {
  const ProjectQuery({
    this.clientId,
    this.search = '',
    this.status,
    this.skip = 0,
    this.limit = 50,
  });
  final int? clientId;
  final String search;
  final ProjectStatus? status;
  final int skip;
  final int limit;
  @override
  int get hashCode => Object.hash(clientId, search, status, skip, limit);
  @override
  bool operator ==(Object other) =>
      other is ProjectQuery &&
      other.clientId == clientId &&
      other.search == search &&
      other.status == status &&
      other.skip == skip &&
      other.limit == limit;
}

final projectsPageProvider = FutureProvider.family<ProjectPage, ProjectQuery>(
  (ref, query) => ref
      .watch(projectsApiProvider)
      .list(
        requireProjectSession(ref),
        search: query.search,
        clientId: query.clientId,
        status: query.status,
        skip: query.skip,
        limit: query.limit,
      ),
);
final projectDetailsProvider = FutureProvider.family<Project, int>(
  (ref, id) =>
      ref.watch(projectsApiProvider).get(requireProjectSession(ref), id),
);
