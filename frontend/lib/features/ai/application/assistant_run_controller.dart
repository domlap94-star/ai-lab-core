import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../auth/application/auth_controller.dart';
import '../data/assistant_run_repository.dart';
import '../domain/assistant_run.dart';

final assistantRunRepositoryProvider = Provider<AssistantRunRepository>(
  (Ref ref) => AssistantRunRepository(ref.watch(dioProvider)),
);

final assistantRunControllerProvider =
    AsyncNotifierProvider<AssistantRunController, List<AssistantRunSnapshot>>(
      AssistantRunController.new,
    );

class AssistantRunController extends AsyncNotifier<List<AssistantRunSnapshot>> {
  @override
  Future<List<AssistantRunSnapshot>> build() async {
    final session = (await ref.watch(authControllerProvider.future)).session;
    if (session == null) return const [];
    return ref
        .read(assistantRunRepositoryProvider)
        .listActive(session: session);
  }

  Future<AssistantRunSnapshot> refreshRun(String runId) async {
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null) throw StateError('Brak aktywnej sesji.');
    final run = await ref
        .read(assistantRunRepositoryProvider)
        .get(session: session, runId: runId);
    final current = state.value ?? const <AssistantRunSnapshot>[];
    state = AsyncData(<AssistantRunSnapshot>[
      run,
      ...current.where((item) => item.runId != run.runId),
    ]);
    return run;
  }

  Future<AssistantRunSnapshot> cancelRun(String runId) async {
    final session = (await ref.read(authControllerProvider.future)).session;
    if (session == null) throw StateError('Brak aktywnej sesji.');
    final run = await ref
        .read(assistantRunRepositoryProvider)
        .cancel(session: session, runId: runId);
    final current = state.value ?? const <AssistantRunSnapshot>[];
    state = AsyncData(<AssistantRunSnapshot>[
      run,
      ...current.where((item) => item.runId != run.runId),
    ]);
    return run;
  }
}
