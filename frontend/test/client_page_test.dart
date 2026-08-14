import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/clients/application/clients_repository.dart';
import 'package:ai_lab/features/clients/data/client_page_response.dart';
import 'package:ai_lab/features/clients/data/clients_api.dart';
import 'package:ai_lab/features/clients/domain/client.dart';
import 'package:ai_lab/features/clients/domain/client_page.dart';
import 'package:ai_lab/features/clients/presentation/clients_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeClientsApi extends ClientsApi {
  _FakeClientsApi() : super(Dio());

  String? capturedSearch;
  String? capturedClientType;
  int? capturedIndustryId;
  int? capturedSkip;
  int? capturedLimit;

  @override
  Future<ClientPageResponse> fetchClients({
    required String accessToken,
    required String tokenType,
    String? search,
    String? clientType,
    int? industryId,
    int skip = 0,
    int limit = 50,
  }) async {
    capturedSearch = search;
    capturedClientType = clientType;
    capturedIndustryId = industryId;
    capturedSkip = skip;
    capturedLimit = limit;
    return const ClientPageResponse(
      items: <Never>[],
      total: 125,
      skip: 50,
      limit: 50,
    );
  }
}

void main() {
  test('ClientsApi requests the additive paginated endpoint', () async {
    final Dio dio = Dio(BaseOptions(baseUrl: 'https://example.test'));
    RequestOptions? capturedRequest;
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (RequestOptions options, RequestInterceptorHandler handler) {
          capturedRequest = options;
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: <String, dynamic>{
                'items': <dynamic>[],
                'total': 0,
                'skip': 0,
                'limit': 50,
              },
            ),
          );
        },
      ),
    );

    await ClientsApi(
      dio,
    ).fetchClients(accessToken: 'token', tokenType: 'bearer');

    expect(capturedRequest?.path, '/api/v1/clients/page');
  });

  test('parses the paginated client API contract', () {
    final ClientPageResponse response = ClientPageResponse.fromJson(
      <String, dynamic>{
        'items': <dynamic>[],
        'total': 3194,
        'skip': 50,
        'limit': 50,
      },
    );

    expect(response.items, isEmpty);
    expect(response.total, 3194);
    expect(response.skip, 50);
    expect(response.limit, 50);
  });

  test('computes stable pagination boundaries', () {
    const ClientPage middle = ClientPage(
      items: <Never>[],
      total: 3194,
      skip: 50,
      limit: 50,
    );
    const ClientPage last = ClientPage(
      items: <Never>[],
      total: 3194,
      skip: 3150,
      limit: 50,
    );

    expect(middle.pageNumber, 2);
    expect(middle.pageCount, 64);
    expect(middle.hasPreviousPage, isTrue);
    expect(middle.hasNextPage, isTrue);
    expect(last.pageNumber, 64);
    expect(last.hasNextPage, isFalse);
  });

  test('rejects the legacy bare-list response shape', () {
    expect(
      () => ClientPageResponse.fromJson(<String, dynamic>{'items': 'invalid'}),
      throwsFormatException,
    );
  });

  test('repository forwards server filters and page metadata', () async {
    final _FakeClientsApi api = _FakeClientsApi();
    final ClientsRepository repository = ClientsRepository(api);

    final ClientPage page = await repository.fetchClients(
      session: const AuthSession(accessToken: 'token', tokenType: 'bearer'),
      search: 'Kowalski',
      clientType: ClientType.person,
      industryId: 7,
      skip: 50,
      limit: 50,
    );

    expect(api.capturedSearch, 'Kowalski');
    expect(api.capturedClientType, 'person');
    expect(api.capturedIndustryId, 7);
    expect(api.capturedSkip, 50);
    expect(api.capturedLimit, 50);
    expect(page.total, 125);
    expect(page.pageNumber, 2);
  });

  testWidgets('pagination controls expose valid page actions', (
    WidgetTester tester,
  ) async {
    int previousCalls = 0;
    int nextCalls = 0;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ClientPaginationControls(
            page: const ClientPage(
              items: <Never>[],
              total: 125,
              skip: 50,
              limit: 50,
            ),
            onPrevious: () async => previousCalls++,
            onNext: () async => nextCalls++,
          ),
        ),
      ),
    );

    expect(find.text('2 / 3'), findsOneWidget);
    await tester.tap(find.text('Poprzednia'));
    await tester.tap(find.text('Następna'));
    expect(previousCalls, 1);
    expect(nextCalls, 1);
  });
}
