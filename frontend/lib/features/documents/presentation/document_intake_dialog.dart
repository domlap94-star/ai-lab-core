import 'dart:io' show Platform;

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../../auth/domain/auth_session.dart';
import '../../clients/presentation/searchable_client_picker.dart';
import '../../inspections/application/inspection_field_services.dart';
import '../application/documents_repository.dart';

class IntakeFile {
  IntakeFile({
    required this.name,
    this.path,
    this.bytes,
    required this.origin,
    this.capturedAt,
    this.location,
  });
  final String name;
  final String? path;
  final Uint8List? bytes;
  final String origin;
  final DateTime? capturedAt;
  final FieldLocationResult? location;
  double progress = 0;
  String? error;
  bool complete = false;
}

abstract class DocumentImagePicker {
  Future<List<IntakeFile>> pickGallery();
  Future<IntakeFile?> captureCamera();
}

class SystemDocumentImagePicker implements DocumentImagePicker {
  @override
  Future<List<IntakeFile>> pickGallery() async {
    final files = await FilePicker.pickFiles(type: FileType.image);
    final selected = <IntakeFile>[];
    for (final file in files) {
      selected.add(
        IntakeFile(
          name: file.name,
          path: file.path,
          bytes: file.path == null ? await file.readAsBytes() : null,
          origin: 'gallery_upload',
          capturedAt: DateTime.now(),
        ),
      );
    }
    return selected;
  }

  @override
  Future<IntakeFile?> captureCamera() async {
    final XFile? image = await ImagePicker().pickImage(
      source: ImageSource.camera,
      imageQuality: 100,
    );
    if (image == null) return null;
    return IntakeFile(
      name: image.name,
      path: kIsWeb ? null : image.path,
      origin: 'camera_capture',
      capturedAt: DateTime.now(),
    );
  }
}

class DocumentIntakeDialog extends StatefulWidget {
  const DocumentIntakeDialog({
    super.key,
    required this.repository,
    required this.session,
    this.clientId,
    this.projectId,
    this.inspectionId,
    this.locationService,
    this.imagePicker,
    this.onCompleted,
  });
  final DocumentsRepository repository;
  final AuthSession session;
  final int? clientId;
  final int? projectId;
  final int? inspectionId;
  final InspectionLocationService? locationService;
  final DocumentImagePicker? imagePicker;
  final VoidCallback? onCompleted;

  @override
  State<DocumentIntakeDialog> createState() => _DocumentIntakeDialogState();
}

class _DocumentIntakeDialogState extends State<DocumentIntakeDialog> {
  final List<IntakeFile> _files = <IntakeFile>[];
  final TextEditingController _comment = TextEditingController();
  int? _selectedClientId;
  bool _includeLocation = false;
  bool _uploading = false;

  InspectionLocationService get _locationService =>
      widget.locationService ?? DeviceInspectionLocationService();
  DocumentImagePicker get _imagePicker =>
      widget.imagePicker ?? SystemDocumentImagePicker();

  bool get _android =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  Future<void> _pickFiles() async {
    final files = await FilePicker.pickFiles();
    if (!mounted || files.isEmpty) return;
    final selected = <IntakeFile>[];
    for (final file in files) {
      selected.add(
        IntakeFile(
          name: file.name,
          path: file.path,
          bytes: file.path == null ? await file.readAsBytes() : null,
          origin: 'manual_upload',
        ),
      );
    }
    if (mounted) setState(() => _files.addAll(selected));
  }

  Future<void> _gallery() async {
    final List<IntakeFile> selected = await _imagePicker.pickGallery();
    if (selected.isEmpty || !mounted) return;
    final FieldLocationResult? location = widget.inspectionId == null
        ? null
        : await _locationService.currentLocation();
    if (!mounted) return;
    final FieldLocationResult? usable =
        location?.status == FieldLocationStatus.success ? location : null;
    setState(
      () => _files.addAll(
        selected.map(
          (file) => IntakeFile(
            name: file.name,
            path: file.path,
            bytes: file.bytes,
            origin: file.origin,
            capturedAt: file.capturedAt ?? DateTime.now(),
            location: usable,
          ),
        ),
      ),
    );
  }

  Future<void> _camera() async {
    final IntakeFile? image = await _imagePicker.captureCamera();
    if (image == null || !mounted) return;
    final FieldLocationResult? location = widget.inspectionId == null
        ? null
        : await _locationService.currentLocation();
    if (!mounted) return;
    setState(
      () => _files.add(
        IntakeFile(
          name: image.name,
          path: image.path,
          bytes: image.bytes,
          origin: 'camera_capture',
          capturedAt: image.capturedAt ?? DateTime.now(),
          location: location?.status == FieldLocationStatus.success
              ? location
              : null,
        ),
      ),
    );
  }

  String _deviceModel() => kIsWeb ? 'Web browser' : Platform.operatingSystem;

  Future<FieldLocationResult?> _position() async {
    if (!_includeLocation) return null;
    try {
      final result = await _locationService.currentLocation();
      return result.status == FieldLocationStatus.success ? result : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> _upload() async {
    if (_files.isEmpty) return;
    setState(() => _uploading = true);
    final FieldLocationResult? position = await _position();
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
          clientId: widget.clientId ?? _selectedClientId,
          projectId: widget.projectId,
          inspectionId: widget.inspectionId,
          origin: file.origin,
          capturedAt: file.capturedAt,
          latitude: file.location?.latitude ?? position?.latitude,
          longitude: file.location?.longitude ?? position?.longitude,
          accuracy: file.location?.accuracy ?? position?.accuracy,
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
                  onPressed: _uploading ? null : _pickFiles,
                  icon: const Icon(Icons.attach_file),
                  label: const Text('Dodaj pliki'),
                ),
                OutlinedButton.icon(
                  onPressed: _uploading ? null : _gallery,
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
              SearchableClientPicker(
                onChanged: (selection) =>
                    setState(() => _selectedClientId = selection?.id),
              ),
            if (widget.clientId == null)
              const Text(
                'Pozostaw bez wyboru, aby dokument pozostał nieprzypisany.',
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
            if (widget.inspectionId == null)
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
            if (widget.inspectionId != null)
              const Text(
                'Przy zdjęciach aplikacja spróbuje automatycznie dołączyć bieżącą lokalizację. Brak GPS nie blokuje wysyłania.',
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
