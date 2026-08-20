import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart' as permissions;
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

enum FieldLocationStatus {
  success,
  denied,
  deniedForever,
  serviceDisabled,
  failed,
}

class FieldLocationResult {
  const FieldLocationResult._(
    this.status, {
    this.latitude,
    this.longitude,
    this.accuracy,
  });

  const FieldLocationResult.success({
    required double latitude,
    required double longitude,
    required double accuracy,
  }) : this._(
         FieldLocationStatus.success,
         latitude: latitude,
         longitude: longitude,
         accuracy: accuracy,
       );

  const FieldLocationResult.status(FieldLocationStatus status) : this._(status);

  final FieldLocationStatus status;
  final double? latitude;
  final double? longitude;
  final double? accuracy;
}

abstract class InspectionLocationService {
  Future<FieldLocationResult> currentLocation();
  Future<bool> openAppSettings();
  Future<bool> openLocationSettings();
}

class DeviceInspectionLocationService implements InspectionLocationService {
  @override
  Future<FieldLocationResult> currentLocation() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        return const FieldLocationResult.status(
          FieldLocationStatus.serviceDisabled,
        );
      }
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.deniedForever) {
        return const FieldLocationResult.status(
          FieldLocationStatus.deniedForever,
        );
      }
      if (permission == LocationPermission.denied) {
        return const FieldLocationResult.status(FieldLocationStatus.denied);
      }
      final Position position = await Geolocator.getCurrentPosition();
      return FieldLocationResult.success(
        latitude: position.latitude,
        longitude: position.longitude,
        accuracy: position.accuracy,
      );
    } catch (_) {
      return const FieldLocationResult.status(FieldLocationStatus.failed);
    }
  }

  @override
  Future<bool> openAppSettings() => Geolocator.openAppSettings();

  @override
  Future<bool> openLocationSettings() => Geolocator.openLocationSettings();
}

final inspectionLocationServiceProvider = Provider<InspectionLocationService>(
  (_) => DeviceInspectionLocationService(),
);

// Shared field-intake aliases. Legacy Inspection names remain source-compatible.
typedef FieldLocationService = InspectionLocationService;
final fieldLocationServiceProvider = Provider<FieldLocationService>(
  (ref) => ref.watch(inspectionLocationServiceProvider),
);

enum SpeechStartStatus { listening, denied, deniedForever, unavailable, failed }

abstract class InspectionSpeechService {
  bool get isSupportedPlatform;
  Future<SpeechStartStatus> start({
    required ValueChanged<String> onFinalResult,
    required VoidCallback onStopped,
  });
  Future<void> stop();
  Future<void> cancel();
  Future<bool> openAppSettings();
}

class AndroidInspectionSpeechService implements InspectionSpeechService {
  final SpeechToText _speech = SpeechToText();
  VoidCallback? _onStopped;
  bool _stoppedNotified = false;

  @override
  bool get isSupportedPlatform =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  void _notifyStopped() {
    if (_stoppedNotified) return;
    _stoppedNotified = true;
    _onStopped?.call();
  }

  @override
  Future<SpeechStartStatus> start({
    required ValueChanged<String> onFinalResult,
    required VoidCallback onStopped,
  }) async {
    if (!isSupportedPlatform) return SpeechStartStatus.unavailable;
    permissions.PermissionStatus microphone =
        await permissions.Permission.microphone.status;
    if (microphone.isDenied) {
      microphone = await permissions.Permission.microphone.request();
    }
    if (microphone.isPermanentlyDenied) {
      return SpeechStartStatus.deniedForever;
    }
    if (!microphone.isGranted) return SpeechStartStatus.denied;

    _onStopped = onStopped;
    _stoppedNotified = false;
    try {
      final bool available = await _speech.initialize(
        onStatus: (String status) {
          if (status == SpeechToText.doneStatus ||
              status == SpeechToText.notListeningStatus) {
            _notifyStopped();
          }
        },
        onError: (SpeechRecognitionError _) => _notifyStopped(),
        options: <SpeechConfigOption>[SpeechToText.androidNoBluetooth],
      );
      if (!available) return SpeechStartStatus.unavailable;

      void result(SpeechRecognitionResult value) {
        if (value.finalResult && value.recognizedWords.trim().isNotEmpty) {
          onFinalResult(value.recognizedWords.trim());
        }
      }

      try {
        await _speech.listen(
          onResult: result,
          listenOptions: SpeechListenOptions(
            localeId: 'pl_PL',
            onDevice: true,
            partialResults: false,
            cancelOnError: true,
            listenMode: ListenMode.dictation,
          ),
        );
      } catch (_) {
        // Some Android devices have no on-device Polish model. Fall back to
        // the system recognizer; audio still never reaches NEXT Stabil.
        await _speech.listen(
          onResult: result,
          listenOptions: SpeechListenOptions(
            localeId: 'pl_PL',
            partialResults: false,
            cancelOnError: true,
            listenMode: ListenMode.dictation,
          ),
        );
      }
      return _speech.isListening
          ? SpeechStartStatus.listening
          : SpeechStartStatus.failed;
    } catch (_) {
      return SpeechStartStatus.failed;
    }
  }

  @override
  Future<void> stop() async {
    await _speech.stop();
    _notifyStopped();
  }

  @override
  Future<void> cancel() async {
    await _speech.cancel();
    _notifyStopped();
  }

  @override
  Future<bool> openAppSettings() => permissions.openAppSettings();
}

final inspectionSpeechServiceProvider = Provider<InspectionSpeechService>(
  (_) => AndroidInspectionSpeechService(),
);
typedef FieldSpeechService = InspectionSpeechService;
final fieldSpeechServiceProvider = Provider<FieldSpeechService>(
  (ref) => ref.watch(inspectionSpeechServiceProvider),
);
