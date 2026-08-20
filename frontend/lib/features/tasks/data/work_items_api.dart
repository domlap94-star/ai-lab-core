import 'package:dio/dio.dart';
import 'dart:typed_data';
import '../../auth/domain/auth_session.dart';
import '../domain/work_item.dart';

class WorkItemsApi {
  const WorkItemsApi(this._dio);
  final Dio _dio;
  Options _o(AuthSession s) =>
      Options(headers: {'Authorization': '${s.tokenType} ${s.accessToken}'});
  Future<CalendarMonthData> month(AuthSession s, DateTime m) async =>
      CalendarMonthData.fromJson(
        (await _dio.get<Map<String, dynamic>>(
          '/api/v1/calendar/month',
          queryParameters: {'year': m.year, 'month': m.month},
          options: _o(s),
        )).data!,
      );
  Future<List<WorkAssignee>> assignees(AuthSession session) async {
    final response = await _dio.get<List<dynamic>>(
      '/api/v1/work-items/assignees',
      options: _o(session),
    );
    return response.data!
        .cast<Map<String, dynamic>>()
        .map(WorkAssignee.fromJson)
        .toList();
  }

  Future<List<WorkItem>> list(
    AuthSession s, {
    int? clientId,
    String? type,
    String? status,
    String? priority,
    int? assigneeUserId,
    DateTime? dateFrom,
    DateTime? dateTo,
  }) async {
    final d = (await _dio.get<Map<String, dynamic>>(
      '/api/v1/work-items',
      queryParameters: {
        'limit': 200,
        'client_id': ?clientId,
        'item_type': ?type,
        'status': ?status,
        'priority': ?priority,
        'assignee_user_id': ?assigneeUserId,
        'date_from': ?dateFrom?.toUtc().toIso8601String(),
        'date_to': ?dateTo?.toUtc().toIso8601String(),
      },
      options: _o(s),
    )).data!;
    return (d['items'] as List)
        .cast<Map<String, dynamic>>()
        .map(WorkItem.fromJson)
        .toList();
  }

  Future<WorkItem> get(AuthSession s, int id) async => WorkItem.fromJson(
    (await _dio.get<Map<String, dynamic>>(
      '/api/v1/work-items/$id',
      options: _o(s),
    )).data!,
  );
  Future<WorkItem> create(AuthSession s, Map<String, dynamic> d) async =>
      WorkItem.fromJson(
        (await _dio.post<Map<String, dynamic>>(
          '/api/v1/work-items',
          data: d,
          options: _o(s),
        )).data!,
      );
  Future<WorkItem> update(
    AuthSession s,
    int id,
    Map<String, dynamic> d,
  ) async => WorkItem.fromJson(
    (await _dio.patch<Map<String, dynamic>>(
      '/api/v1/work-items/$id',
      data: d,
      options: _o(s),
    )).data!,
  );
  Future<WorkItem> archive(AuthSession session, int id, int version) async =>
      WorkItem.fromJson(
        (await _dio.post<Map<String, dynamic>>(
          '/api/v1/work-items/$id/archive',
          data: {'expected_version': version},
          options: _o(session),
        )).data!,
      );
  Future<List<AbsenceRequestItem>> absences(AuthSession s) async {
    final d = (await _dio.get<Map<String, dynamic>>(
      '/api/v1/absence-requests',
      queryParameters: {'limit': 200},
      options: _o(s),
    )).data!;
    return (d['items'] as List)
        .cast<Map<String, dynamic>>()
        .map(AbsenceRequestItem.fromJson)
        .toList();
  }

  Future<AbsenceRequestItem> createAbsence(
    AuthSession s,
    Map<String, dynamic> d,
  ) async => AbsenceRequestItem.fromJson(
    (await _dio.post<Map<String, dynamic>>(
      '/api/v1/absence-requests',
      data: d,
      options: _o(s),
    )).data!,
  );
  Future<AbsenceRequestItem> updateAbsence(
    AuthSession session,
    int id,
    Map<String, dynamic> data,
  ) async => AbsenceRequestItem.fromJson(
    (await _dio.patch<Map<String, dynamic>>(
      '/api/v1/absence-requests/$id',
      data: data,
      options: _o(session),
    )).data!,
  );
  Future<AbsenceRequestItem> reviewAbsence(
    AuthSession s,
    int id,
    int version, {
    required bool approve,
  }) async => AbsenceRequestItem.fromJson(
    (await _dio.post<Map<String, dynamic>>(
      '/api/v1/absence-requests/$id/${approve ? 'approve' : 'reject'}',
      data: {'expected_version': version},
      options: _o(s),
    )).data!,
  );

  Future<AbsenceRequestItem> cancelAbsence(
    AuthSession session,
    int id,
    int version,
  ) async => AbsenceRequestItem.fromJson(
    (await _dio.post<Map<String, dynamic>>(
      '/api/v1/absence-requests/$id/cancel',
      data: {'expected_version': version},
      options: _o(session),
    )).data!,
  );

  Future<List<WorkItemNote>> notes(AuthSession session, int itemId) async {
    final response = await _dio.get<List<dynamic>>(
      '/api/v1/work-items/$itemId/notes',
      options: _o(session),
    );
    return response.data!
        .cast<Map<String, dynamic>>()
        .map(WorkItemNote.fromJson)
        .toList();
  }

  Future<List<WorkItemDocument>> documents(
    AuthSession session,
    int itemId,
  ) async {
    final response = await _dio.get<List<dynamic>>(
      '/api/v1/work-items/$itemId/documents',
      options: _o(session),
    );
    return response.data!
        .cast<Map<String, dynamic>>()
        .map(WorkItemDocument.fromJson)
        .toList();
  }

  Future<WorkItemNote> createNote(
    AuthSession session,
    int itemId,
    String text,
  ) async => WorkItemNote.fromJson(
    (await _dio.post<Map<String, dynamic>>(
      '/api/v1/work-items/$itemId/notes',
      data: {'text': text},
      options: _o(session),
    )).data!,
  );

  Future<WorkItemNote> updateNote(
    AuthSession session,
    int itemId,
    WorkItemNote note,
    String text,
  ) async => WorkItemNote.fromJson(
    (await _dio.patch<Map<String, dynamic>>(
      '/api/v1/work-items/$itemId/notes/${note.id}',
      data: {'text': text, 'expected_version': note.version},
      options: _o(session),
    )).data!,
  );

  Future<WorkItemNote> archiveNote(
    AuthSession session,
    int itemId,
    WorkItemNote note,
  ) async => WorkItemNote.fromJson(
    (await _dio.post<Map<String, dynamic>>(
      '/api/v1/work-items/$itemId/notes/${note.id}/archive',
      data: {'expected_version': note.version},
      options: _o(session),
    )).data!,
  );

  Future<void> uploadDocument(
    AuthSession session,
    int itemId, {
    required String name,
    required Uint8List bytes,
    required String sourceType,
    DateTime? capturedAt,
    double? latitude,
    double? longitude,
    double? accuracy,
    int? noteId,
  }) async {
    await _dio.post<Map<String, dynamic>>(
      '/api/v1/work-items/$itemId/documents/upload',
      data: FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: name),
        'source_type': sourceType,
        'captured_at': ?capturedAt?.toUtc().toIso8601String(),
        'latitude': ?latitude,
        'longitude': ?longitude,
        'location_accuracy_m': ?accuracy,
        'note_id': ?noteId,
      }),
      options: _o(session),
    );
  }

  Future<void> detachDocument(
    AuthSession session,
    int itemId,
    int documentId,
  ) async {
    await _dio.delete<void>(
      '/api/v1/work-items/$itemId/documents/$documentId',
      options: _o(session),
    );
  }
}
