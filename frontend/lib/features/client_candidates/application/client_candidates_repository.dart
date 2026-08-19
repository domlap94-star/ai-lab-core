import '../../auth/domain/auth_session.dart';
import '../data/client_candidates_api.dart';
import '../domain/client_candidate.dart';
import '../domain/client_candidate_context.dart';

class ClientCandidatesRepository {
  const ClientCandidatesRepository(this._api);

  final ClientCandidatesApi _api;

  Future<List<ClientCandidate>> fetchCandidates({
    required AuthSession session,
    String? search,
    int skip = 0,
    int limit = 100,
  }) async {
    final responses = await _api.fetchCandidates(
      accessToken: session.accessToken,
      tokenType: session.tokenType,
      search: search,
      skip: skip,
      limit: limit,
    );

    return responses
        .map<ClientCandidate>((response) => response.toDomain())
        .toList(growable: false);
  }

  Future<ClientCandidateContext> fetchContext({
    required AuthSession session,
    required int candidateId,
  }) {
    return _api.fetchContext(
      candidateId: candidateId,
      accessToken: session.accessToken,
      tokenType: session.tokenType,
    );
  }

  Future<CandidateAcceptResult> accept({
    required AuthSession session,
    required int candidateId,
  }) {
    return _api.accept(
      candidateId: candidateId,
      accessToken: session.accessToken,
      tokenType: session.tokenType,
    );
  }

  Future<void> reject({
    required AuthSession session,
    required int candidateId,
  }) {
    return _api.reject(
      candidateId: candidateId,
      accessToken: session.accessToken,
      tokenType: session.tokenType,
    );
  }

  Future<CandidateMergePreview> fetchMergePreview({
    required AuthSession session,
    required int candidateId,
    required int targetClientId,
  }) => _api.fetchMergePreview(
    candidateId: candidateId,
    targetClientId: targetClientId,
    accessToken: session.accessToken,
    tokenType: session.tokenType,
  );

  Future<CandidateMergeResult> merge({
    required AuthSession session,
    required int candidateId,
    required int targetClientId,
    required String operationId,
    required String expectedCandidateVersion,
    required Map<String, String> fieldDecisions,
  }) => _api.merge(
    candidateId: candidateId,
    targetClientId: targetClientId,
    operationId: operationId,
    expectedCandidateVersion: expectedCandidateVersion,
    fieldDecisions: fieldDecisions,
    accessToken: session.accessToken,
    tokenType: session.tokenType,
  );

  Future<Map<String, dynamic>> bulkAccept({
    required AuthSession session,
    required List<int> candidateIds,
  }) => _api.bulkAccept(
    candidateIds: candidateIds,
    accessToken: session.accessToken,
    tokenType: session.tokenType,
  );
}
