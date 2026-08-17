import 'dart:io' show Platform;

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';

import '../../auth/domain/auth_session.dart';
import '../application/documents_repository.dart';

class IntakeFile {
  IntakeFile({
    required this.name,
    this.path,
    this.bytes,
    required this.origin,
    this.capturedAt,
  });
  final String name;
  final String? path;
  final Uint8List? bytes;
  final String origin;
  final DateTime? capturedAt;
  double progress = 0;
  String? error;
  bool complete = false;
}

class DocumentIntakeDialog extends StatefulWidget {
  const DocumentIntakeDialog({
    super.key,
    required this.repository,
    required this.session,
    this.clientId,
    this.projectId,
    this.onCompleted,
  });
  final DocumentsRepository repository;
  final AuthSession session;
  final int? clientId;
  final int? projectId;
  final VoidCallback? onCompleted;

  @override
  State<DocumentIntakeDialog> createState() => _DocumentIntakeDialogState();
}

class _DocumentIntakeDialogState extends State<DocumentIntakeDialog> {
  final List<IntakeFile> _files = <IntakeFile>[];
  final TextEditingController _comment = TextEditingController();
  final TextEditingController _client = TextEditingController();
  bool _includeLocation = false;
  bool _uploading = false;

  bool get _android =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  @override
  void dispose() {
    _comment.dispose();
    _client.dispose();
    super.dispose();
  }

  Future<void> _pickFiles({FileType type = FileType.any}) async {
    final files = await FilePicker.pickFiles(type: type);
    if (!mounted || files.isEmpty) return;
    final selected = <IntakeFile>[];
    for (final file in files) {
      selected.add(
        IntakeFile(
          name: file.name,
          path: file.path,
          bytes: file.path == null ? await file.readAsBytes() : null,
          origin: type == FileType.image ? 'gallery_upload' : 'manual_upload',
        ),
      );
    }
    if (mounted) setState(() => _files.addAll(selected));
  }

  Future<void> _camera() async {
    final XFile? image = await ImagePicker().pickImage(
      source: ImageSource.camera,
      imageQuality: 100,
    );
    if (image == null || !mounted) return;
    setState(
      () => _files.add(
        IntakeFile(
          name: image.name,
          path: kIsWeb ? null : image.path,
          bytes: kIsWeb ? null : null,
          origin: 'camera_capture',
          capturedAt: DateTime.now(),
        ),
      ),
    );
  }

  String _deviceModel() => kIsWeb ? 'Web browser' : Platform.operatingSystem;

  Future<Position?> _position() async {
    if (!_includeLocation) return null;
    try {
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        return null;
      }
      return Geolocator.getCurrentPosition();
    } catch (_) {
      return null;
    }
  }

  Future<void> _upload() async {
    if (_files.isEmpty) return;
    setState(() => _uploading = true);
    final Position? position = await _position();
    final String device = _deviceModel();
    for (final file in _files.where((file) => !file.complete)) {
      try {
        Uint8List? bytes = file.bytes;
        if (bytes == null && file.path == null) {
          throw StateError('Brak danych pliku.');
        }
        await widget.repository.upload(
          session: widget.session,
          name: file.name,
          path: file.path,
          bytes: bytes,
          clientId: widget.clientId ?? int.tryParse(_client.text.trim()),
          projectId: widget.projectId,
          origin: file.origin,
          capturedAt: file.capturedAt,
          latitude: position?.latitude,
          longitude: position?.longitude,
          accuracy: position?.accuracy,
          deviceModel: device,
          comment: _comment.text,
          onProgress: (sent, total) {
            if (mounted) {
              setState(() => file.progress = total <= 0 ? 0 : sent / total);
            }
          },
        );
        file.complete = true;
      } catch (error) {
        file.error = error.toString();
      }
      if (mounted) setState(() {});
    }
    if (mounted) setState(() => _uploading = false);
    if (_files.any((file) => file.complete)) widget.onCompleted?.call();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Dodaj dokumenty'),
    content: SizedBox(
      width: 520,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                OutlinedButton.icon(
                  onPressed: _uploading ? null : () => _pickFiles(),
                  icon: const Icon(Icons.attach_file),
                  label: const Text('Dodaj pliki'),
                ),
                OutlinedButton.icon(
                  onPressed: _uploading
                      ? null
                      : () => _pickFiles(type: FileType.image),
                  icon: const Icon(Icons.photo_library),
                  label: const Text('Dodaj zdjęcie'),
                ),
                if (_android)
                  OutlinedButton.icon(
                    key: const Key('document-camera'),
                    onPressed: _uploading ? null : _camera,
                    icon: const Icon(Icons.camera_alt),
                    label: const Text('Zrób zdjęcie'),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            if (widget.clientId == null)
              TextField(
                controller: _client,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Klient (ID, opcjonalnie)',
                  helperText:
                      'Pozostaw puste, aby dokument pozostał nieprzypisany.',
                  border: OutlineInputBorder(),
                ),
              ),
            if (widget.clientId == null) const SizedBox(height: 12),
            TextField(
              controller: _comment,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Komentarz (opcjonalnie)',
                border: OutlineInputBorder(),
              ),
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _includeLocation,
              onChanged: _uploading
                  ? null
                  : (value) =>
                        setState(() => _includeLocation = value ?? false),
              title: const Text('Dołącz bieżącą lokalizację'),
              subtitle: const Text(
                'Opcjonalnie; odmowa nie blokuje wysyłania.',
              ),
            ),
            ..._files.map(
              (file) => ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(
                  file.complete
                      ? Icons.check_circle
                      : file.error != null
                      ? Icons.error
                      : Icons.insert_drive_file,
                ),
                title: Text(
                  file.name,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                subtitle: file.error != null
                    ? Text(file.error!, maxLines: 2)
                    : LinearProgressIndicator(
                        value: file.complete ? 1 : file.progress,
                      ),
                trailing: file.error == null
                    ? null
                    : IconButton(
                        tooltip: 'Ponów',
                        onPressed: _uploading
                            ? null
                            : () {
                                setState(() => file.error = null);
                                _upload();
                              },
                        icon: const Icon(Icons.refresh),
                      ),
              ),
            ),
          ],
        ),
      ),
    ),
    actions: <Widget>[
      TextButton(
        onPressed: _uploading ? null : () => Navigator.pop(context),
        child: const Text('Zamknij'),
      ),
      FilledButton(
        onPressed: _uploading || _files.isEmpty ? null : _upload,
        child: Text(_uploading ? 'Przesyłanie…' : 'Prześlij'),
      ),
    ],
  );
}
