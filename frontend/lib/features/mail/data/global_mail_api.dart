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
}

final globalMailApiProvider = Provider<GlobalMailApi>(
  (Ref ref) => GlobalMailApi(ref.watch(dioProvider)),
);
