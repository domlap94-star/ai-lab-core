import 'package:ai_lab/features/auth/domain/auth_session.dart';
import 'package:ai_lab/features/mail/data/global_mail_api.dart';
import 'package:ai_lab/features/mail/domain/global_mail.dart';
import 'package:ai_lab/features/mail/presentation/ignored_mail_source_controls.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const AuthSession _session = AuthSession(
  accessToken: 'ignore-mail-test-token',
  tokenType: 'Bearer',
);

class _FakeApi extends GlobalMailApi {
  _FakeApi({this.failCreate = false, List<IgnoredMailSourceRule>? rules})
    : _rules = rules ?? <IgnoredMailSourceRule>[],
      super(Dio());

  final bool failCreate;
  final List<IgnoredMailSourceRule> _rules;
  final List<(String, String)> created = <(String, String)>[];
  final List<int> removed = <int>[];

  @override
  Future<IgnoredMailSourceRule> ignoreSender(
    AuthSession session, {
    required String value,
    String ruleType = 'email',
  }) async {
    if (failCreate) throw StateError('synthetic create failure');
    created.add((ruleType, value));
    return _rule(100 + created.length, ruleType, value);
  }

  @override
  Future<List<IgnoredMailSourceRule>> ignoredRules(AuthSession session) async =>
      List<IgnoredMailSourceRule>.unmodifiable(_rules);

  @override
  Future<void> unignoreSender(AuthSession session, int ruleId) async {
    removed.add(ruleId);
    _rules.removeWhere((IgnoredMailSourceRule rule) => rule.id == ruleId);
  }
}

IgnoredMailSourceRule _rule(int id, String type, String value) =>
    IgnoredMailSourceRule(
      id: id,
      ruleType: type,
      normalizedValue: value,
      isActive: true,
      createdAt: DateTime(2026, 8, 29, 10),
      updatedAt: DateTime(2026, 8, 29, 10),
    );

Future<void> _pumpLauncher(WidgetTester tester, _FakeApi api) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (BuildContext context) => Column(
            children: <Widget>[
              TextButton(
                key: const Key('launch-ignore'),
                onPressed: () => showIgnoreMailSenderDialog(
                  context: context,
                  api: api,
                  session: _session,
                  sender: 'Osoba <Sender@Example.COM>',
                ),
                child: const Text('Ignoruj'),
              ),
              TextButton(
                key: const Key('launch-manage'),
                onPressed: () => showIgnoredMailSourcesDialog(
                  context: context,
                  api: api,
                  session: _session,
                ),
                child: const Text('Zarządzaj'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

void main() {
  test(
    'sender helper normalizes exact address and domain without suffix match',
    () {
      expect(
        canonicalIgnoredMailAddress(' Osoba <Sender@Example.COM> '),
        'sender@example.com',
      );
      expect(ignoredMailDomain('sender@example.com'), 'example.com');
      expect(ignoredMailDomain('sender@notexample.com'), 'notexample.com');
      expect(canonicalIgnoredMailAddress('not-an-email'), isNull);
    },
  );

  testWidgets(
    'exact sender is the explicit default and requires confirmation',
    (WidgetTester tester) async {
      final _FakeApi api = _FakeApi();
      await _pumpLauncher(tester, api);
      await tester.tap(find.byKey(const Key('launch-ignore')));
      await tester.pumpAndSettle();
      expect(find.text('Nadawca: sender@example.com'), findsOneWidget);
      expect(api.created, isEmpty);
      await tester.tap(find.byKey(const Key('confirm-ignore-mail-rule')));
      await tester.pumpAndSettle();
      expect(api.created, <(String, String)>[('email', 'sender@example.com')]);
      expect(
        find.textContaining('sender@example.com został zignorowany'),
        findsOneWidget,
      );
    },
  );

  testWidgets('domain rule is a separate visible choice', (
    WidgetTester tester,
  ) async {
    final _FakeApi api = _FakeApi();
    await _pumpLauncher(tester, api);
    await tester.tap(find.byKey(const Key('launch-ignore')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('ignore-mail-choice-domain')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-ignore-mail-rule')));
    await tester.pumpAndSettle();
    expect(api.created, <(String, String)>[('domain', 'example.com')]);
    expect(find.textContaining('domeny example.com'), findsOneWidget);
  });

  testWidgets('create error is bounded and does not claim success', (
    WidgetTester tester,
  ) async {
    final _FakeApi api = _FakeApi(failCreate: true);
    await _pumpLauncher(tester, api);
    await tester.tap(find.byKey(const Key('launch-ignore')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-ignore-mail-rule')));
    await tester.pumpAndSettle();
    expect(api.created, isEmpty);
    expect(find.textContaining('Nie udało się dodać'), findsOneWidget);
  });

  testWidgets('removing exact rule discloses overlapping domain rule', (
    WidgetTester tester,
  ) async {
    final _FakeApi api = _FakeApi(
      rules: <IgnoredMailSourceRule>[
        _rule(1, 'email', 'sender@example.com'),
        _rule(2, 'domain', 'example.com'),
      ],
    );
    await _pumpLauncher(tester, api);
    await tester.tap(find.byKey(const Key('launch-manage')));
    await tester.pumpAndSettle();
    expect(find.text('sender@example.com'), findsOneWidget);
    expect(find.text('example.com'), findsOneWidget);
    await tester.tap(find.byKey(const Key('remove-ignore-rule-1')));
    await tester.pumpAndSettle();
    expect(api.removed, isEmpty);
    await tester.tap(find.byKey(const Key('confirm-remove-ignore-rule-1')));
    await tester.pumpAndSettle();
    expect(api.removed, <int>[1]);
    expect(
      find.textContaining(
        'Nadawca nadal jest ignorowany przez regułę domeny example.com',
      ),
      findsOneWidget,
    );
  });
}
