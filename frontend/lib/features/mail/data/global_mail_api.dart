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
    int limit = 50,
    String? search,
    String? direction,
    String? readState,
    bool? linked,
    bool? hasAttachments,
    bool? ignored,
    DateTime? dateFrom,
    DateTime? dateTo,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/mail',
      queryParameters: <String, dynamic>{
        'skip': skip,
        'limit': limit,
        'search': ?search,
        'direction': ?direction,
        'read_state': ?readState,
        'linked': ?linked,
        'has_attachments': ?hasAttachments,
        'ignored': ?ignored,
        'date_from': ?dateFrom?.toUtc().toIso8601String(),
        'date_to': ?dateTo?.toUtc().toIso8601String(),
      },
      options: _options(session),
    );
    return GlobalMailPageData.fromJson(response.data ?? <String, dynamic>{});
  }

  Future<List<IgnoredMailSourceRule>> ignoredRules(AuthSession session) async {
    final response = await _dio.get<List<dynamic>>(
      '/api/v1/admin/ignored-mail-sources',
      options: _options(session),
    );
    return (response.data ?? const <dynamic>[])
        .whereType<Map<String, dynamic>>()
        .map(IgnoredMailSourceRule.fromJson)
        .toList(growable: false);
  }

  Future<IgnoredMailSourceRule> ignoreSender(
    AuthSession session, {
    required String value,
    String ruleType = 'email',
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/admin/ignored-mail-sources',
      data: <String, dynamic>{'rule_type': ruleType, 'value': value},
      options: _options(session),
    );
    return IgnoredMailSourceRule.fromJson(response.data ?? <String, dynamic>{});
  }

  Future<void> unignoreSender(AuthSession session, int ruleId) async {
    await _dio.delete<void>(
      '/api/v1/admin/ignored-mail-sources/$ruleId',
      options: _options(session),
    );
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

  Options _reconciliationOptions(AuthSession session) =>
      _options(session).copyWith(
        receiveTimeout: const Duration(minutes: 2),
        sendTimeout: const Duration(seconds: 15),
      );

  Future<MailReconciliationDryRun> reconciliationDryRun(
    AuthSession session, {
    int windowDays = 7,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/mail/reconcile/dry-run',
      data: <String, dynamic>{'window_days': windowDays},
      options: _reconciliationOptions(session),
    );
    return MailReconciliationDryRun.fromJson(
      response.data ?? <String, dynamic>{},
    );
  }

  Future<MailReconciliationResult> reconciliationApply(
    AuthSession session,
    MailReconciliationDryRun dryRun,
  ) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/mail/reconcile/apply',
      data: <String, dynamic>{
        'window_days': dryRun.windowDays,
        'dry_run_token': dryRun.dryRunToken,
      },
      options: _reconciliationOptions(session),
    );
    return MailReconciliationResult.fromJson(
      response.data ?? <String, dynamic>{},
    );
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
