import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../data/work_items_api.dart';
import '../domain/work_item.dart';

final workItemsApiProvider = Provider<WorkItemsApi>(
  (ref) => WorkItemsApi(ref.watch(dioProvider)),
);
final calendarMonthProvider =
    FutureProvider.family<CalendarMonthData, DateTime>((ref, m) {
      final s = ref.watch(authControllerProvider).value?.session;
      if (s == null) throw StateError('Brak sesji');
      return ref.watch(workItemsApiProvider).month(s, m);
    });
final workItemsProvider = FutureProvider.family<List<WorkItem>, int?>((ref, c) {
  final s = ref.watch(authControllerProvider).value?.session;
  if (s == null) throw StateError('Brak sesji');
  return ref.watch(workItemsApiProvider).list(s, clientId: c);
});

class WorkItemListFilter {
  const WorkItemListFilter({
    this.type,
    this.status,
    this.priority,
    this.assigneeUserId,
    this.clientId,
    this.dateFrom,
    this.dateTo,
  });
  final String? type, status, priority;
  final int? assigneeUserId, clientId;
  final DateTime? dateFrom, dateTo;

  @override
  bool operator ==(Object other) =>
      other is WorkItemListFilter &&
      other.type == type &&
      other.status == status &&
      other.priority == priority &&
      other.assigneeUserId == assigneeUserId &&
      other.clientId == clientId &&
      other.dateFrom == dateFrom &&
      other.dateTo == dateTo;

  @override
  int get hashCode => Object.hash(
    type,
    status,
    priority,
    assigneeUserId,
    clientId,
    dateFrom,
    dateTo,
  );
}

final filteredWorkItemsProvider =
    FutureProvider.family<List<WorkItem>, WorkItemListFilter>((ref, filter) {
      final session = ref.watch(authControllerProvider).value?.session;
      if (session == null) throw StateError('Brak sesji');
      return ref
          .watch(workItemsApiProvider)
          .list(
            session,
            clientId: filter.clientId,
            type: filter.type,
            status: filter.status,
            priority: filter.priority,
            assigneeUserId: filter.assigneeUserId,
            dateFrom: filter.dateFrom,
            dateTo: filter.dateTo,
          );
    });
final workAssigneesProvider = FutureProvider<List<WorkAssignee>>((ref) {
  final session = ref.watch(authControllerProvider).value?.session;
  if (session == null) throw StateError('Brak sesji');
  return ref.watch(workItemsApiProvider).assignees(session);
});
final absencesProvider = FutureProvider<List<AbsenceRequestItem>>((ref) {
  final s = ref.watch(authControllerProvider).value?.session;
  if (s == null) throw StateError('Brak sesji');
  return ref.watch(workItemsApiProvider).absences(s);
});
final workItemNotesProvider = FutureProvider.family<List<WorkItemNote>, int>((
  ref,
  itemId,
) {
  final session = ref.watch(authControllerProvider).value?.session;
  if (session == null) throw StateError('Brak sesji');
  return ref.watch(workItemsApiProvider).notes(session, itemId);
});
final workItemDocumentsProvider =
    FutureProvider.family<List<WorkItemDocument>, int>((ref, itemId) {
      final session = ref.watch(authControllerProvider).value?.session;
      if (session == null) throw StateError('Brak sesji');
      return ref.watch(workItemsApiProvider).documents(session, itemId);
    });
