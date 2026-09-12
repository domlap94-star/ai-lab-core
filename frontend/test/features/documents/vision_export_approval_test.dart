import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/documents/application/documents_repository.dart';
import 'package:ai_lab/features/documents/data/document_content.dart';
import 'package:ai_lab/features/documents/data/documents_api.dart';
import 'package:ai_lab/features/documents/domain/document.dart';
import 'package:ai_lab/features/documents/domain/document_filters.dart';
import 'package:ai_lab/features/documents/domain/document_page.dart';
import 'package:ai_lab/features/documents/domain/vision_export_approval.dart';
import 'package:ai_lab/features/documents/presentation/vision_export_approval_dialog.dart';
import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const AuthSession _session = AuthSession(
  accessToken: 'synthetic-r05-a4-token',
  tokenType: 'Bearer',
);

final Uint8List _imageBytes = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
);

void main() {
  test('API binds preview bytes and approval to candidate hashes', () async {
    final String hash = sha256.convert(_imageBytes).toString();
    final _VisionAdapter adapter = _VisionAdapter(hash: hash);
    final Dio dio = Dio(BaseOptions(baseUrl: 'https://example.invalid'))
      ..httpClientAdapter = adapter;
    final DocumentsApi api = DocumentsApi(dio);

    final VisionExportApprovalCandidate candidate = await api
        .fetchVisionExportApprovalCandidate(
          documentId: 501,
          accessToken: _session.accessToken,
          tokenType: _session.tokenType,
        );
    final VisionExportApprovalPreview preview = await api
        .fetchVisionExportApprovalPreview(
          documentId: 501,
          candidate: candidate,
          source: candidate.sources.single,
          accessToken: _session.accessToken,
          tokenType: _session.tokenType,
        );
    await api.approveVisionExport(
      documentId: 501,
      candidate: candidate,
      approvalKind: 'public_safe',
      expiresAt: DateTime.utc(2026, 9, 12, 13),
      accessToken: _session.accessToken,
      tokenType: _session.tokenType,
    );

    expect(preview.bytes, _imageBytes);
    expect(adapter.previewQuery['binding_sha256'], 'b' * 64);
    expect(adapter.approvalBody['analysis_job_id'], 'synthetic-job-a4');
    expect(adapter.approvalBody['package_sha256'], 'a' * 64);
    expect(adapter.approvalBody['binding_sha256'], 'b' * 64);
    expect(adapter.approvalBody['source_sha256'], <String, String>{'S1': hash});
  });

  test(
    'API rejects preview whose response hash does not match bytes',
    () async {
      final String hash = sha256.convert(_imageBytes).toString();
      final _VisionAdapter adapter = _VisionAdapter(
        hash: hash,
        corruptPreviewHeader: true,
      );
      final DocumentsApi api = DocumentsApi(
        Dio(BaseOptions(baseUrl: 'https://example.invalid'))
          ..httpClientAdapter = adapter,
      );
      final VisionExportApprovalCandidate candidate = await api
          .fetchVisionExportApprovalCandidate(
            documentId: 501,
            accessToken: _session.accessToken,
            tokenType: _session.tokenType,
          );

      await expectLater(
        api.fetchVisionExportApprovalPreview(
          documentId: 501,
          candidate: candidate,
          source: candidate.sources.single,
          accessToken: _session.accessToken,
          tokenType: _session.tokenType,
        ),
        throwsA(isA<FormatException>()),
      );
    },
  );

  testWidgets(
    'dialog shows exact copy and requires an explicit single approval',
    (WidgetTester tester) async {
      final _Repository repository = _Repository();
      repository.approvalCompleter = Completer<VisionExportApprovalResult>();
      await _pumpDialog(tester, repository);

      if (find
          .byKey(const Key('vision-export-load-error'))
          .evaluate()
          .isNotEmpty) {
        final Text error = tester.widget(
          find.byKey(const Key('vision-export-load-error')),
        );
        fail(error.data ?? 'preview load failed');
      }

      expect(find.byKey(const Key('vision-export-preview-S1')), findsOneWidget);
      expect(repository.approvalCalls, 0);
      FilledButton approve = tester.widget(
        find.byKey(const Key('vision-export-approve')),
      );
      expect(approve.onPressed, isNull);

      await tester.ensureVisible(find.byKey(const Key('vision-export-kind')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('vision-export-kind')));
      await tester.pumpAndSettle();
      await tester.tap(
        find.text('public_safe — kopia bezpieczna publicznie').last,
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(
        find.byKey(const Key('vision-export-expiry-minutes')),
      );
      await tester.enterText(
        find.byKey(const Key('vision-export-expiry-minutes')),
        '30',
      );
      await tester.pump();
      approve = tester.widget(find.byKey(const Key('vision-export-approve')));
      expect(approve.onPressed, isNotNull);

      await tester.tap(find.byKey(const Key('vision-export-approve')));
      await tester.pump();
      expect(repository.approvalCalls, 1);
      approve = tester.widget(find.byKey(const Key('vision-export-approve')));
      expect(approve.onPressed, isNull);
      await tester.tap(find.byKey(const Key('vision-export-approve')));
      expect(repository.approvalCalls, 1);

      repository.approvalCompleter!.complete(
        const VisionExportApprovalResult(
          documentId: 501,
          analysisJobId: 'synthetic-job-a4',
          state: 'queued',
          reason: 'VISUAL_V2_QUEUED',
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Analiza zewnętrzna może zostać zakolejkowana'),
        findsOneWidget,
      );
      expect(repository.lastApprovalKind, 'public_safe');
      expect(repository.lastCandidate?.bindingSha256, 'b' * 64);
    },
  );

  testWidgets('dialog cancel performs no decision', (
    WidgetTester tester,
  ) async {
    final _Repository repository = _Repository();
    await _pumpDialog(tester, repository);
    await tester.tap(find.byKey(const Key('vision-export-cancel')));
    await tester.pumpAndSettle();
    expect(repository.approvalCalls, 0);
    expect(repository.revokeCalls, 0);
  });

  testWidgets('dialog passes through an existing locally redacted copy', (
    WidgetTester tester,
  ) async {
    final _Repository repository = _Repository();
    await _pumpDialog(tester, repository);
    await tester.ensureVisible(find.byKey(const Key('vision-export-kind')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('vision-export-kind')));
    await tester.pumpAndSettle();
    await tester.tap(
      find.text('locally_redacted — już lokalnie zredagowana').last,
    );
    await tester.pumpAndSettle();
    await tester.ensureVisible(
      find.byKey(const Key('vision-export-expiry-minutes')),
    );
    await tester.enterText(
      find.byKey(const Key('vision-export-expiry-minutes')),
      '15',
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('vision-export-approve')));
    await tester.pumpAndSettle();

    expect(repository.approvalCalls, 1);
    expect(repository.lastApprovalKind, 'locally_redacted');
    expect(
      find.textContaining('Analiza zewnętrzna może zostać zakolejkowana'),
      findsOneWidget,
    );
  });

  testWidgets('unloaded or stale preview never becomes approvable', (
    WidgetTester tester,
  ) async {
    final _Repository repository = _Repository(previewHashOverride: 'f' * 64);
    await _pumpDialog(tester, repository);
    expect(find.byKey(const Key('vision-export-load-error')), findsOneWidget);
    final FilledButton approve = tester.widget(
      find.byKey(const Key('vision-export-approve')),
    );
    expect(approve.onPressed, isNull);
    expect(repository.approvalCalls, 0);
  });

  testWidgets('approved candidate exposes revoke without a second approval', (
    WidgetTester tester,
  ) async {
    final _Repository repository = _Repository(
      candidateState: 'approved',
      canApprove: false,
      canRevoke: true,
    );
    await _pumpDialog(tester, repository);
    await tester.tap(find.byKey(const Key('vision-export-revoke')));
    await tester.pumpAndSettle();
    expect(repository.revokeCalls, 1);
    expect(repository.approvalCalls, 0);
    expect(find.text('Cofnięto niewykorzystaną zgodę.'), findsOneWidget);
  });

  testWidgets('uncertain contact response exposes neither approve nor revoke', (
    WidgetTester tester,
  ) async {
    final _Repository repository = _Repository(
      candidateError: const FormatException(
        'VISUAL_V2_APPROVAL_ALREADY_EXPORTED',
      ),
    );
    await _pumpDialog(tester, repository);

    expect(find.byKey(const Key('vision-export-load-error')), findsOneWidget);
    final FilledButton approve = tester.widget(
      find.byKey(const Key('vision-export-approve')),
    );
    expect(approve.onPressed, isNull);
    expect(find.byKey(const Key('vision-export-revoke')), findsNothing);
    expect(repository.approvalCalls, 0);
    expect(repository.revokeCalls, 0);
  });
}

Future<void> _pumpDialog(
  WidgetTester tester,
  DocumentsRepository repository,
) async {
  tester.view.physicalSize = const Size(1200, 1000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: VisionExportApprovalDialog(
          document: _document,
          repository: repository,
          session: _session,
        ),
      ),
    ),
  );
  await tester.runAsync(
    () => Future<void>.delayed(const Duration(milliseconds: 50)),
  );
  for (int attempt = 0; attempt < 40; attempt += 1) {
    await tester.pump(const Duration(milliseconds: 25));
    if (find
            .byKey(const Key('vision-export-preview-S1'))
            .evaluate()
            .isNotEmpty ||
        find
            .byKey(const Key('vision-export-load-error'))
            .evaluate()
            .isNotEmpty) {
      break;
    }
  }
}

final RepositoryDocument _document = RepositoryDocument(
  id: 501,
  originalFilename: 'synthetic-a4.jpg',
  contentType: 'image/jpeg',
  fileSize: 128,
  sourceType: 'manual_upload',
  processingStatus: 'processed',
  metadataStatus: 'complete',
  matchStatus: 'matched',
  archiveDepth: 0,
  createdAt: _date,
  updatedAt: _date,
);

final DateTime _date = DateTime.utc(2026, 9, 12);

VisionExportApprovalCandidate _candidate({
  String state = 'not_approved',
  bool canApprove = true,
  bool canRevoke = false,
}) {
  final String hash = sha256.convert(_imageBytes).toString();
  return VisionExportApprovalCandidate(
    analysisJobId: 'synthetic-job-a4',
    policyVersion: 'visual-export-v1',
    channel: 'temporary_chat_visual',
    packageSha256: 'a' * 64,
    bindingSha256: 'b' * 64,
    selectedSourceCount: 1,
    omittedSourceCount: 0,
    completeSourceCoverage: true,
    approvalState: state,
    approvalKind: state == 'approved' ? 'public_safe' : null,
    approvalExpiresAt: state == 'approved'
        ? DateTime.utc(2026, 9, 12, 14)
        : null,
    canApprove: canApprove,
    canRevoke: canRevoke,
    sources: <VisionExportApprovalSource>[
      VisionExportApprovalSource(
        sourceRef: 'S1',
        sourceEntityType: 'DocumentPage',
        sourceEntityId: '50101',
        documentId: 501,
        scope: const VisionExportDocumentScope(
          documentId: 501,
          clientId: 7,
          projectId: 8,
        ),
        sensitivity: 'public_reference',
        originalSha256: 'c' * 64,
        finalSha256: hash,
        previewContentType: 'image/jpeg',
        previewSize: _imageBytes.length,
      ),
    ],
  );
}

class _Repository extends DocumentsRepository {
  _Repository({
    this.previewHashOverride,
    this.candidateState = 'not_approved',
    this.canApprove = true,
    this.canRevoke = false,
    this.candidateError,
  });

  final String? previewHashOverride;
  final String candidateState;
  final bool canApprove;
  final bool canRevoke;
  final Object? candidateError;
  Completer<VisionExportApprovalResult>? approvalCompleter;
  int approvalCalls = 0;
  int revokeCalls = 0;
  String? lastApprovalKind;
  VisionExportApprovalCandidate? lastCandidate;

  @override
  Future<VisionExportApprovalCandidate> fetchVisionExportApprovalCandidate({
    required AuthSession session,
    required int documentId,
  }) async {
    if (candidateError case final Object error) throw error;
    return _candidate(
      state: candidateState,
      canApprove: canApprove,
      canRevoke: canRevoke,
    );
  }

  @override
  Future<VisionExportApprovalPreview> fetchVisionExportApprovalPreview({
    required AuthSession session,
    required int documentId,
    required VisionExportApprovalCandidate candidate,
    required VisionExportApprovalSource source,
  }) async => VisionExportApprovalPreview(
    sourceRef: source.sourceRef,
    sourceSha256: previewHashOverride ?? source.finalSha256,
    packageSha256: candidate.packageSha256,
    contentType: source.previewContentType,
    bytes: _imageBytes,
  );

  @override
  Future<VisionExportApprovalResult> approveVisionExport({
    required AuthSession session,
    required int documentId,
    required VisionExportApprovalCandidate candidate,
    required String approvalKind,
    required DateTime expiresAt,
  }) {
    approvalCalls += 1;
    lastApprovalKind = approvalKind;
    lastCandidate = candidate;
    return approvalCompleter?.future ??
        Future<VisionExportApprovalResult>.value(
          const VisionExportApprovalResult(
            documentId: 501,
            analysisJobId: 'synthetic-job-a4',
            state: 'queued',
            reason: 'VISUAL_V2_QUEUED',
          ),
        );
  }

  @override
  Future<VisionExportApprovalResult> revokeVisionExportApproval({
    required AuthSession session,
    required int documentId,
    required String analysisJobId,
  }) async {
    revokeCalls += 1;
    return const VisionExportApprovalResult(
      documentId: 501,
      analysisJobId: 'synthetic-job-a4',
      state: 'awaiting_auth',
      reason: 'VISUAL_V2_EXPORT_APPROVAL_REVOKED',
    );
  }

  @override
  Future<DocumentPage> fetchDocuments({
    required AuthSession session,
    required DocumentFilters filters,
    String search = '',
    int skip = 0,
    int limit = 50,
  }) => throw UnimplementedError();

  @override
  Future<RepositoryDocument> fetchDocument({
    required AuthSession session,
    required int documentId,
  }) => throw UnimplementedError();

  @override
  Future<DocumentContent> fetchContent({
    required AuthSession session,
    required RepositoryDocument document,
    void Function(int received, int total)? onProgress,
  }) => throw UnimplementedError();
}

class _VisionAdapter implements HttpClientAdapter {
  _VisionAdapter({required this.hash, this.corruptPreviewHeader = false});

  final String hash;
  final bool corruptPreviewHeader;
  Map<String, dynamic> previewQuery = <String, dynamic>{};
  Map<String, dynamic> approvalBody = <String, dynamic>{};

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (options.path.endsWith('/vision/export-approval/candidate')) {
      return ResponseBody.fromString(
        jsonEncode(<String, dynamic>{
          'analysis_job_id': 'synthetic-job-a4',
          'policy_version': 'visual-export-v1',
          'channel': 'temporary_chat_visual',
          'package_sha256': 'a' * 64,
          'binding_sha256': 'b' * 64,
          'selected_source_count': 1,
          'omitted_source_count': 0,
          'complete_source_coverage': true,
          'approval_state': 'not_approved',
          'approval_kind': null,
          'approval_expires_at': null,
          'can_approve': true,
          'can_revoke': false,
          'sources': <Map<String, dynamic>>[
            <String, dynamic>{
              'source_ref': 'S1',
              'source_entity_type': 'DocumentPage',
              'source_entity_id': '50101',
              'document_id': 501,
              'document_scope': <String, dynamic>{
                'schema': 'VISUAL_EXPORT_DOCUMENT_SCOPE_V1',
                'document_id': 501,
                'client_id': 7,
                'project_id': 8,
                'inspection_id': null,
                'candidate_id': null,
              },
              'sensitivity': 'public_reference',
              'original_sha256': 'c' * 64,
              'final_sha256': hash,
              'preview_content_type': 'image/jpeg',
              'preview_size': _imageBytes.length,
            },
          ],
        }),
        200,
        headers: <String, List<String>>{
          Headers.contentTypeHeader: <String>['application/json'],
        },
      );
    }
    if (options.path.endsWith('/sources/S1/preview')) {
      previewQuery = Map<String, dynamic>.from(options.queryParameters);
      return ResponseBody.fromBytes(
        _imageBytes,
        200,
        headers: <String, List<String>>{
          Headers.contentTypeHeader: <String>['image/jpeg'],
          'x-source-ref': <String>['S1'],
          'x-content-sha256': <String>[corruptPreviewHeader ? 'f' * 64 : hash],
          'x-package-sha256': <String>['a' * 64],
        },
      );
    }
    if (options.path.endsWith('/vision/export-approval')) {
      approvalBody = Map<String, dynamic>.from(options.data as Map);
      return ResponseBody.fromString(
        jsonEncode(<String, dynamic>{
          'document_id': 501,
          'analysis_job_id': 'synthetic-job-a4',
          'state': 'queued',
          'reason': 'VISUAL_V2_QUEUED',
        }),
        200,
        headers: <String, List<String>>{
          Headers.contentTypeHeader: <String>['application/json'],
        },
      );
    }
    return ResponseBody.fromString('not found', 404);
  }

  @override
  void close({bool force = false}) {}
}
