import 'package:flutter_test/flutter_test.dart';
import 'package:ai_lab/core/widgets/app_shell.dart';

void main() {
  test('External navigation is client-scoped and default-deny', () {
    final paths = AppShell.itemsForRole(
      'External',
    ).map((item) => item.path).toSet();
    expect(paths, contains('/shared-clients'));
    expect(
      paths,
      containsAll(<String>{
        '/tasks',
        '/projects',
        '/inspections',
        '/documents',
        '/mail',
      }),
    );
    expect(paths, isNot(contains('/dashboard')));
    expect(paths, isNot(contains('/clients')));
    expect(paths, isNot(contains('/settings')));
    expect(paths, isNot(contains('/search')));
    expect(paths, isNot(contains('/ai')));
  });

  test(
    'Administrator and User retain normal navigation plus grant management',
    () {
      for (final role in <String>['Administrator', 'User']) {
        final paths = AppShell.itemsForRole(
          role,
        ).map((item) => item.path).toSet();
        expect(paths, contains('/shared-clients'));
        expect(paths, contains('/dashboard'));
        expect(paths, contains('/clients'));
        expect(paths, contains('/settings'));
      }
    },
  );
}
