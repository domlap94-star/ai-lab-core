import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../data/timeline_api.dart';
import '../domain/timeline.dart';

final timelineApiProvider = Provider<TimelineApi>(
  (ref) => TimelineApi(ref.watch(dioProvider)),
);
final timelinePageProvider =
    FutureProvider.family<TimelinePage, TimelineRequest>((ref, request) {
      final session = ref.watch(authControllerProvider).value?.session;
      if (session == null) throw StateError('Brak aktywnej sesji.');
      return ref.watch(timelineApiProvider).fetch(session, request);
    });
