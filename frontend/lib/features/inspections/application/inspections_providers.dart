import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/auth_session.dart';
import '../data/inspections_api.dart';
import '../domain/inspection.dart';

final inspectionsApiProvider = Provider<InspectionsApi>(
  (ref) => InspectionsApi(ref.watch(dioProvider)),
);
AuthSession requireInspectionSession(Ref ref) {
  final session = ref.watch(authControllerProvider).value?.session;
  if (session == null) throw StateError('Brak aktywnej sesji.');
  return session;
}

AuthSession requireInspectionWidgetSession(WidgetRef ref) {
  final session = ref.read(authControllerProvider).value?.session;
  if (session == null) throw StateError('Brak aktywnej sesji.');
  return session;
}

class InspectionQuery {
  const InspectionQuery({
    this.projectId,
    this.clientId,
    this.search = '',
    this.status,
    this.dateFrom,
    this.dateTo,
    this.skip = 0,
    this.limit = 50,
  });
  final int? projectId;
  final int? clientId;
  final String search;
  final InspectionStatus? status;
  final DateTime? dateFrom;
  final DateTime? dateTo;
  final int skip;
  final int limit;
  @override
  int get hashCode => Object.hash(
    projectId,
    clientId,
    search,
    status,
    dateFrom,
    dateTo,
    skip,
    limit,
  );
  @override
  bool operator ==(Object other) =>
      other is InspectionQuery &&
      other.projectId == projectId &&
      other.clientId == clientId &&
      other.search == search &&
      other.status == status &&
      other.dateFrom == dateFrom &&
      other.dateTo == dateTo &&
      other.skip == skip &&
      other.limit == limit;
}

final inspectionsPageProvider =
    FutureProvider.family<InspectionPage, InspectionQuery>(
      (ref, query) => ref
          .watch(inspectionsApiProvider)
          .list(
            requireInspectionSession(ref),
            search: query.search,
            projectId: query.projectId,
            clientId: query.clientId,
            status: query.status,
            dateFrom: query.dateFrom,
            dateTo: query.dateTo,
            skip: query.skip,
            limit: query.limit,
          ),
    );
final inspectionDetailsProvider = FutureProvider.family<Inspection, int>(
  (ref, id) =>
      ref.watch(inspectionsApiProvider).get(requireInspectionSession(ref), id),
);
