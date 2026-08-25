import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:ai_lab/features/ai/data/unified_assistant_api.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'actual Flutter request JSON matches the shared backend fixture',
    () async {
      final fixture =
          jsonDecode(
                File(
                  '../backend/test/fixtures/unified_assistant_current_android_requests.json',
                ).readAsStringSync(),
              )
              as List<dynamic>;
      final adapter = _CaptureAdapter();
      final dio = Dio(BaseOptions(baseUrl: 'https://example.invalid'))
        ..httpClientAdapter = adapter;
      final api = UnifiedAssistantApi(dio);
      const session = AuthSession(
        accessToken: 'synthetic',
        tokenType: 'Bearer',
      );

      for (final dynamic item in fixture) {
        final request = Map<String, dynamic>.from(
          (item as Map<String, dynamic>)['request'] as Map,
        );
        await api.ask(
          session: session,
          question: request['question'] as String,
          conversation: (request['conversation'] as List<dynamic>)
              .map((entry) => Map<String, String>.from(entry as Map))
              .toList(growable: false),
          clientId: request['client_id'] as int?,
          candidateId: request['candidate_id'] as int?,
          documentId: request['document_id'] as int?,
          mailSourceId: request['mail_source_id'] as int?,
          inspectionId: request['inspection_id'] as int?,
          attemptId: request['attempt_id'] as String?,
        );
      }

      expect(adapter.requests, hasLength(fixture.length));
      for (var index = 0; index < fixture.length; index++) {
        final expected = Map<String, dynamic>.from(
          (fixture[index] as Map<String, dynamic>)['request'] as Map,
        );
        expect(adapter.requests[index], expected);
      }
    },
  );
}

class _CaptureAdapter implements HttpClientAdapter {
  final List<Map<String, dynamic>> requests = <Map<String, dynamic>>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    expect(options.method, 'POST');
    expect(options.path, '/api/v1/ai/assistant/ask');
    requests.add(Map<String, dynamic>.from(options.data as Map));
    return ResponseBody.fromString(
      jsonEncode(<String, dynamic>{
        'request_id': 'synthetic-request',
        'answer': 'Odpowiedź syntetyczna.',
        'status': 'accepted_local',
        'progress': 'complete',
        'target_scope': 'TARGET_01',
        'claims': <dynamic>[],
        'sources': <dynamic>[],
        'used_tools': <dynamic>[],
        'external_analysis_used': false,
        'can_cancel': false,
        'delayed': false,
      }),
      200,
      headers: <String, List<String>>{
        Headers.contentTypeHeader: <String>['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}
