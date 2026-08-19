import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/domain/auth_session.dart';
import '../domain/global_mail.dart';

class GlobalMailApi {
  const GlobalMailApi(this._dio);

  final Dio _dio;

  Options _options(AuthSession session) => Options(
    headers: <String, Object>{
      'Authorization': '${session.tokenType} ${session.accessToken}',
    },
  );

  Future<GlobalMailPageData> list({
    required AuthSession session,
    required int skip,
    String? search,
    String? direction,
    String? readState,
    bool? linked,
    bool? hasAttachments,
    DateTime? dateFrom,
    DateTime? dateTo,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/mail',
      queryParameters: <String, dynamic>{
        'skip': skip,
        'limit': 50,
        'search': ?search,
        'direction': ?direction,
        'read_state': ?readState,
        'linked': ?linked,
        'has_attachments': ?hasAttachments,
        'date_from': ?dateFrom?.toUtc().toIso8601String(),
        'date_to': ?dateTo?.toUtc().toIso8601String(),
      },
      options: _options(session),
    );
    return GlobalMailPageData.fromJson(response.data ?? <String, dynamic>{});
  }

  Future<GlobalMailItem> detail(AuthSession session, int sourceId) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/mail/$sourceId',
      options: _options(session),
    );
    return GlobalMailItem.fromJson(response.data ?? <String, dynamic>{});
  }

  Future<List<GlobalMailItem>> thread(
    AuthSession session,
    String threadId,
  ) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/mail/threads/${Uri.encodeComponent(threadId)}',
      options: _options(session),
    );
    return (response.data?['items'] as List<dynamic>? ?? const <dynamic>[])
        .whereType<Map<String, dynamic>>()
        .map(GlobalMailItem.fromJson)
        .toList(growable: false);
  }

  Future<MailSendResult> send(
    AuthSession session, {
    required String operationId,
    required List<String> to,
    required String subject,
    required String body,
    List<String> cc = const <String>[],
    List<String> bcc = const <String>[],
    List<int> attachmentDocumentIds = const <int>[],
    int? clientId,
    int? sourceId,
    String action = 'compose',
  }) async {
    final String path = action == 'compose'
        ? '/api/v1/mail/send'
        : '/api/v1/mail/$sourceId/$action';
    final Map<String, dynamic> payload = <String, dynamic>{
      'operation_id': operationId,
      if (action != 'reply') 'to': to,
      if (action != 'reply') 'cc': cc,
      if (action != 'reply') 'bcc': bcc,
      if (action != 'reply') 'subject': subject,
      'body': body,
      'attachment_document_ids': attachmentDocumentIds,
      if (action == 'compose') 'client_id': clientId,
    };
    final response = await _dio.post<Map<String, dynamic>>(
      path,
      data: payload,
      options: _options(session),
    );
    return MailSendResult.fromJson(response.data ?? <String, dynamic>{});
  }
}

final globalMailApiProvider = Provider<GlobalMailApi>(
  (Ref ref) => GlobalMailApi(ref.watch(dioProvider)),
);
