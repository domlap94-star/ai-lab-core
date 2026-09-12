import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';

import '../../auth/domain/auth_session.dart';
import '../application/documents_repository.dart';
import '../domain/document.dart';
import '../domain/vision_export_approval.dart';

class VisionExportApprovalDialog extends StatefulWidget {
  const VisionExportApprovalDialog({
    required this.document,
    required this.repository,
    required this.session,
    super.key,
  });

  final RepositoryDocument document;
  final DocumentsRepository repository;
  final AuthSession session;

  @override
  State<VisionExportApprovalDialog> createState() =>
      _VisionExportApprovalDialogState();
}

class _VisionExportApprovalDialogState
    extends State<VisionExportApprovalDialog> {
  final TextEditingController _expiryMinutes = TextEditingController();
  VisionExportApprovalCandidate? _candidate;
  List<VisionExportApprovalPreview> _previews = const [];
  String? _approvalKind;
  String? _loadError;
  String? _operationResult;
  bool _loading = true;
  bool _busy = false;
  bool _started = false;
  bool _completed = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_started) {
      _started = true;
      _expiryMinutes.addListener(_formChanged);
      _load();
    }
  }

  @override
  void dispose() {
    _expiryMinutes
      ..removeListener(_formChanged)
      ..dispose();
    super.dispose();
  }

  void _formChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _load() async {
    try {
      final VisionExportApprovalCandidate candidate = await widget.repository
          .fetchVisionExportApprovalCandidate(
            session: widget.session,
            documentId: widget.document.id,
          );
      if (candidate.sources.any(
        (VisionExportApprovalSource source) =>
            source.documentId != widget.document.id ||
            source.scope.documentId != widget.document.id ||
            source.sensitivity == 'restricted_never_external',
      )) {
        throw const FormatException(
          'Kandydat nie należy wyłącznie do wybranego dokumentu.',
        );
      }
      final List<VisionExportApprovalPreview> previews = [];
      for (final VisionExportApprovalSource source in candidate.sources) {
        final VisionExportApprovalPreview preview = await widget.repository
            .fetchVisionExportApprovalPreview(
              session: widget.session,
              documentId: widget.document.id,
              candidate: candidate,
              source: source,
            );
        _verifyPreview(candidate, source, preview);
        if (!mounted) return;
        Object? decodeError;
        await precacheImage(
          MemoryImage(preview.bytes),
          context,
          onError: (Object error, StackTrace? _) => decodeError = error,
        );
        if (decodeError != null) {
          throw const FormatException(
            'Nie można wyświetlić pełnej kopii materiału eksportowego.',
          );
        }
        previews.add(preview);
      }
      if (!mounted) return;
      setState(() {
        _candidate = candidate;
        _previews = List.unmodifiable(previews);
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _loadError = _safeMessage(error);
        _candidate = null;
        _previews = const [];
      });
    }
  }

  void _verifyPreview(
    VisionExportApprovalCandidate candidate,
    VisionExportApprovalSource source,
    VisionExportApprovalPreview preview,
  ) {
    final String actualHash = sha256.convert(preview.bytes).toString();
    if (preview.sourceRef != source.sourceRef ||
        preview.sourceSha256 != source.finalSha256 ||
        preview.packageSha256 != candidate.packageSha256 ||
        actualHash != source.finalSha256 ||
        preview.bytes.length != source.previewSize) {
      throw const FormatException(
        'Podgląd nie odpowiada zatwierdzanemu pakietowi Visual.',
      );
    }
  }

  int? get _validMinutes {
    final int? value = int.tryParse(_expiryMinutes.text.trim());
    return value != null && value > 0 ? value : null;
  }

  bool get _canApprove {
    final VisionExportApprovalCandidate? candidate = _candidate;
    return !_busy &&
        !_completed &&
        candidate != null &&
        candidate.canApprove &&
        _previews.length == candidate.sources.length &&
        _approvalKind != null &&
        _validMinutes != null;
  }

  Future<void> _approve() async {
    if (!_canApprove) return;
    final VisionExportApprovalCandidate candidate = _candidate!;
    final int minutes = _validMinutes!;
    setState(() {
      _busy = true;
      _operationResult = null;
    });
    try {
      await widget.repository.approveVisionExport(
        session: widget.session,
        documentId: widget.document.id,
        candidate: candidate,
        approvalKind: _approvalKind!,
        expiresAt: DateTime.now().toUtc().add(Duration(minutes: minutes)),
      );
      if (!mounted) return;
      setState(() {
        _busy = false;
        _completed = true;
        _operationResult =
            'Zapisano zgodę dla tego pakietu. Analiza zewnętrzna może zostać '
            'zakolejkowana przez istniejący proces.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _completed = true;
        _operationResult =
            'Nie zapisano zgody: ${_safeMessage(error)} '
            'Zamknij okno i pobierz nowy kandydat.';
      });
    }
  }

  Future<void> _revoke() async {
    final VisionExportApprovalCandidate? candidate = _candidate;
    if (_busy || _completed || candidate == null || !candidate.canRevoke) {
      return;
    }
    setState(() {
      _busy = true;
      _operationResult = null;
    });
    try {
      await widget.repository.revokeVisionExportApproval(
        session: widget.session,
        documentId: widget.document.id,
        analysisJobId: candidate.analysisJobId,
      );
      if (!mounted) return;
      setState(() {
        _busy = false;
        _completed = true;
        _operationResult = 'Cofnięto niewykorzystaną zgodę.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _completed = true;
        _operationResult =
            'Nie cofnięto zgody: ${_safeMessage(error)} '
            'Kontakt mógł już się rozpocząć; nie ponawiaj wysyłki.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Dopuszczenie zewnętrznej analizy Visual'),
      content: SizedBox(
        width: 760,
        height: 680,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _loadError != null
            ? _ErrorPanel(message: _loadError!)
            : _buildCandidate(_candidate!),
      ),
      actions: <Widget>[
        TextButton(
          key: const Key('vision-export-cancel'),
          onPressed: _busy ? null : () => Navigator.of(context).pop(),
          child: const Text('Anuluj'),
        ),
        if (_candidate?.canRevoke == true)
          TextButton(
            key: const Key('vision-export-revoke'),
            onPressed: _busy || _completed ? null : _revoke,
            child: const Text('Cofnij niewykorzystaną zgodę'),
          ),
        FilledButton.icon(
          key: const Key('vision-export-approve'),
          onPressed: _canApprove ? _approve : null,
          icon: _busy
              ? const SizedBox.square(
                  dimension: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.verified_user_outlined),
          label: const Text('Zatwierdź i zleć analizę zewnętrzną'),
        ),
      ],
    );
  }

  Widget _buildCandidate(VisionExportApprovalCandidate candidate) {
    final DateTime? proposedExpiry = _validMinutes == null
        ? null
        : DateTime.now().toUtc().add(Duration(minutes: _validMinutes!));
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Text(
            'To jest dokładna finalna kopia, która może opuścić komputer. '
            'Samo otwarcie podglądu nie udziela zgody i niczego nie wysyła.',
          ),
          const SizedBox(height: 12),
          _LabelValue('Kanał', candidate.channel),
          _LabelValue('Polityka', candidate.policyVersion),
          _LabelValue('Stan zgody', candidate.approvalState),
          _LabelValue(
            'Pokrycie',
            '${candidate.selectedSourceCount} pokazane, '
                '${candidate.omittedSourceCount} pominięte',
          ),
          if (!candidate.completeSourceCoverage)
            const Card(
              color: Color(0xFFFFF3CD),
              child: Padding(
                padding: EdgeInsets.all(12),
                child: Text(
                  'Pakiet nie obejmuje całego materiału. Zgoda dotyczy tylko '
                  'widocznych poniżej źródeł.',
                ),
              ),
            ),
          const Divider(height: 28),
          for (int index = 0; index < candidate.sources.length; index++)
            _SourcePreview(
              source: candidate.sources[index],
              preview: _previews[index],
            ),
          const Divider(height: 28),
          DropdownButtonFormField<String>(
            key: const Key('vision-export-kind'),
            initialValue: _approvalKind,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Rodzaj zgody'),
            items: const <DropdownMenuItem<String>>[
              DropdownMenuItem(
                value: 'public_safe',
                child: Text('public_safe — kopia bezpieczna publicznie'),
              ),
              DropdownMenuItem(
                value: 'locally_redacted',
                child: Text('locally_redacted — już lokalnie zredagowana'),
              ),
            ],
            onChanged: _busy || _completed
                ? null
                : (String? value) => setState(() => _approvalKind = value),
          ),
          const SizedBox(height: 8),
          const Text(
            'Opcja locally_redacted nie tworzy redakcji. Wybierz ją tylko, '
            'gdy pokazana finalna kopia została wcześniej lokalnie przygotowana.',
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('vision-export-expiry-minutes'),
            controller: _expiryMinutes,
            enabled: !_busy && !_completed,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Ważność zgody w minutach',
              hintText: 'Wpisz dodatnią liczbę',
            ),
          ),
          if (proposedExpiry != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text('Planowane wygaśnięcie UTC: $proposedExpiry'),
            ),
          const SizedBox(height: 12),
          const Text(
            'Zatwierdzenie zapisze zgodę na dokładnie ten pakiet i może '
            'zakolejkować istniejące zadanie analizy zewnętrznej.',
          ),
          if (_operationResult != null) ...<Widget>[
            const SizedBox(height: 12),
            Text(
              _operationResult!,
              key: const Key('vision-export-operation-result'),
            ),
          ],
        ],
      ),
    );
  }
}

class _SourcePreview extends StatelessWidget {
  const _SourcePreview({required this.source, required this.preview});

  final VisionExportApprovalSource source;
  final VisionExportApprovalPreview preview;

  @override
  Widget build(BuildContext context) {
    final VisionExportDocumentScope scope = source.scope;
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              '${source.sourceRef} · ${preview.bytes.length} B · '
              '${source.sensitivity}',
            ),
            Text(
              'Dokument ${scope.documentId}; klient ${scope.clientId ?? '—'}; '
              'sprawa ${scope.projectId ?? '—'}; wizja '
              '${scope.inspectionId ?? '—'}',
            ),
            const SizedBox(height: 8),
            SizedBox(
              height: 360,
              width: double.infinity,
              child: InteractiveViewer(
                minScale: 0.5,
                maxScale: 8,
                child: Center(
                  child: Image.memory(
                    Uint8List.fromList(preview.bytes),
                    key: Key('vision-export-preview-${source.sourceRef}'),
                    fit: BoxFit.contain,
                    gaplessPlayback: true,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LabelValue extends StatelessWidget {
  const _LabelValue(this.label, this.value);
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 4),
    child: Text('$label: $value'),
  );
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) => Center(
    child: Text(
      'Nie można przygotować bezpiecznego podglądu. $message',
      key: const Key('vision-export-load-error'),
      textAlign: TextAlign.center,
    ),
  );
}

String _safeMessage(Object error) {
  final String message = error
      .toString()
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
  return message.length <= 240 ? message : '${message.substring(0, 240)}…';
}
