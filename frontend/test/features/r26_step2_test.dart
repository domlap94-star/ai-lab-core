import 'package:ai_lab/features/auth/application/auth_controller.dart';
import 'package:ai_lab/features/auth/application/auth_state.dart';
import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/auth/domain/current_user.dart';
import 'package:ai_lab/features/inspections/domain/inspection.dart';
import 'package:ai_lab/features/inspections/presentation/inspection_form_dialog.dart';
import 'package:ai_lab/features/shared_clients/application/client_access_providers.dart';
import 'package:ai_lab/features/shared_clients/data/client_access_repository.dart';
import 'package:ai_lab/features/shared_clients/presentation/shared_clients_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _AuthController extends AuthController {
  _AuthController(this.role);
  final String role;

  @override
  Future<AuthState> build() async => AuthState(
    session: const AuthSession(accessToken: 'test', tokenType: 'Bearer'),
    user: CurrentUser(
      id: 1,
      username: 'r26-manager',
      email: 'r26-manager@example.invalid',
      role: role,
      isActive: true,
      mustChangePassword: false,
      passwordResetRequested: false,
    ),
  );
}

class _Repository extends ClientAccessRepository {
  _Repository() : super(Dio());
  int bulkCalls = 0;
  List<int> ids = const <int>[];

  @override
  Future<int> bulkRevoke({
    required AuthSession session,
    required List<int> grantIds,
  }) async {
    bulkCalls++;
    ids = List<int>.from(grantIds);
    return grantIds.length;
  }
}

Map<String, dynamic> _grant(int id, {bool active = true}) => <String, dynamic>{
  'id': id,
  'client_id': 100 + id,
  'external_user_id': 10,
  'active': active,
  'granted_at': '2026-09-28T10:00:00Z',
  'revoked_at': active ? null : '2026-09-28T11:00:00Z',
  'revoked_by_user_id': active ? null : 1,
};

void main() {
  test('date-only parser/formatter does not perform a UTC conversion', () {
    final value = parseInspectionDateOnly('2026-03-29');
    expect(value, DateTime(2026, 3, 29));
    expect(inspectionDateApi(value!), '2026-03-29');
    expect(inspectionDateDisplay(value), '29.03.2026');
    expect(parseInspectionDateOnly('2026-03-29T00:00:00Z'), isNull);
  });

  test('inspection response prefers canonical date and supports legacy', () {
    Map<String, dynamic> base() => <String, dynamic>{
      'id': 1,
      'project_id': null,
      'project_name': null,
      'client_id': 2,
      'client_name': 'Synthetic',
      'title': 'Wizja lokalna',
      'status': 'planned',
      'completed_at': null,
      'notes': null,
      'latitude': null,
      'longitude': null,
      'location_accuracy_m': null,
      'created_at': '2026-09-28T10:00:00Z',
      'updated_at': '2026-09-28T10:00:00Z',
      'deleted_at': null,
    };
    final canonical = Inspection.fromJson(<String, dynamic>{
      ...base(),
      'scheduled_date': '2026-09-30',
      'scheduled_at': '2026-09-29T00:00:00Z',
      'started_at': null,
    });
    expect(inspectionDateApi(canonical.scheduledDate!), '2026-09-30');
    final legacy = Inspection.fromJson(<String, dynamic>{
      ...base(),
      'scheduled_date': null,
      'scheduled_at': null,
      'started_at': '2026-09-29T10:00:00Z',
    });
    expect(inspectionDateApi(legacy.scheduledDate!), '2026-09-29');
    final midnightBoundary = Inspection.fromJson(<String, dynamic>{
      ...base(),
      'scheduled_date': null,
      'scheduled_at': '2026-03-28T23:30:00Z',
      'started_at': null,
    });
    expect(inspectionDateApi(midnightBoundary.scheduledDate!), '2026-03-29');
  });

  testWidgets('inspection form uses one required calendar date', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: InspectionFormDialog(clientId: 3, clientName: 'Synthetic'),
        ),
      ),
    );
    expect(find.text('Termin wizji *'), findsOneWidget);
    expect(find.textContaining('ISO'), findsNothing);
    expect(find.textContaining('Rozpoczęto'), findsNothing);
    await tester.tap(find.byKey(const Key('inspection-scheduled-date')));
    await tester.pumpAndSettle();
    expect(find.byType(DatePickerDialog), findsOneWidget);
  });

  testWidgets('manager sees active by default and bulk revoke is one request', (
    tester,
  ) async {
    final repository = _Repository();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(() => _AuthController('User')),
          clientAccessRepositoryProvider.overrideWithValue(repository),
          clientGrantHistoryProvider.overrideWith(
            (ref) async => <Map<String, dynamic>>[_grant(1), _grant(2)],
          ),
          clientGrantHistoryWithRevokedProvider.overrideWith(
            (ref) async => <Map<String, dynamic>>[
              _grant(1),
              _grant(2),
              _grant(3, active: false),
            ],
          ),
          clientAccessManagerOptionsProvider.overrideWith(
            (ref) async => <String, List<Map<String, dynamic>>>{
              'clients': <Map<String, dynamic>>[
                for (final id in <int>[101, 102, 103])
                  <String, dynamic>{'id': id, 'name': 'Client $id'},
              ],
              'external_users': <Map<String, dynamic>>[
                <String, dynamic>{'id': 10, 'username': 'External Alpha'},
              ],
            },
          ),
        ],
        child: const MaterialApp(home: SharedClientsPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey<String>('grant-select-3')), findsNothing);
    await tester.tap(find.byKey(const Key('show-revoked-grants')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey<String>('grant-select-3')),
      findsOneWidget,
    );
    final checkbox = tester.widget<CheckboxListTile>(
      find.byKey(const ValueKey<String>('grant-select-3')),
    );
    expect(checkbox.onChanged, isNull);
    await tester.tap(find.byKey(const Key('show-revoked-grants')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey<String>('grant-select-1')));
    await tester.tap(find.byKey(const ValueKey<String>('grant-select-2')));
    await tester.pump();
    expect(find.text('Wybrano: 2'), findsOneWidget);
    await tester.tap(find.byKey(const Key('bulk-revoke-selected')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Anuluj'));
    await tester.pumpAndSettle();
    expect(repository.bulkCalls, 0);
    await tester.tap(find.byKey(const Key('bulk-revoke-selected')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cofnij dostępy'));
    await tester.pumpAndSettle();
    expect(repository.bulkCalls, 1);
    expect(repository.ids, <int>[1, 2]);
  });

  testWidgets('External has no history or manager controls', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(
            () => _AuthController('External'),
          ),
          sharedClientsProvider.overrideWith(
            (ref) async => <Map<String, dynamic>>[
              <String, dynamic>{'id': 101, 'name': 'Client 101'},
            ],
          ),
        ],
        child: const MaterialApp(home: SharedClientsPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Pokaż cofnięte'), findsNothing);
    expect(find.byType(CheckboxListTile), findsNothing);
    expect(find.text('Client 101'), findsOneWidget);
  });
}
