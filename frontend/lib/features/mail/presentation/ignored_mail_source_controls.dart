import 'package:flutter/material.dart';

import '../../../core/formatters/polish_date_time.dart';
import '../../../core/network/friendly_api_error.dart';
import '../../auth/domain/auth_session.dart';
import '../data/global_mail_api.dart';
import '../domain/global_mail.dart';

final RegExp _mailAddressPattern = RegExp(
  r'^[^@\s]+@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$',
  caseSensitive: false,
);

String? canonicalIgnoredMailAddress(String? rawValue) {
  final String raw = rawValue?.trim() ?? '';
  if (raw.isEmpty) return null;
  final Match? bracketed = RegExp(r'<([^<>]+)>\s*$').firstMatch(raw);
  final String value = (bracketed?.group(1) ?? raw).trim().toLowerCase();
  return _mailAddressPattern.hasMatch(value) ? value : null;
}

String? ignoredMailDomain(String? rawValue) {
  final String? address = canonicalIgnoredMailAddress(rawValue);
  if (address == null) return null;
  return address.substring(address.lastIndexOf('@') + 1);
}

Future<bool> showIgnoreMailSenderDialog({
  required BuildContext context,
  required GlobalMailApi api,
  required AuthSession session,
  required String sender,
}) async {
  final String? address = canonicalIgnoredMailAddress(sender);
  final String? domain = ignoredMailDomain(sender);
  if (address == null || domain == null) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Nie udało się ustalić adresu nadawcy.')),
    );
    return false;
  }

  String selectedType = 'email';
  final String? ruleType = await showDialog<String>(
    context: context,
    builder: (BuildContext dialogContext) => StatefulBuilder(
      builder: (BuildContext context, StateSetter setDialogState) => AlertDialog(
        title: const Text('Ignoruj nadawcę'),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text('Nadawca: $address'),
              const SizedBox(height: 12),
              RadioGroup<String>(
                groupValue: selectedType,
                onChanged: (String? value) =>
                    setDialogState(() => selectedType = value ?? 'email'),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    RadioListTile<String>(
                      key: const Key('ignore-mail-choice-email'),
                      value: 'email',
                      title: const Text('Ignoruj ten adres e-mail'),
                      subtitle: Text(address),
                    ),
                    RadioListTile<String>(
                      key: const Key('ignore-mail-choice-domain'),
                      value: 'domain',
                      title: Text('Ignoruj domenę $domain'),
                      subtitle: const Text(
                        'Dotyczy wszystkich nadawców z tej domeny.',
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Nowe nierozstrzygnięte wiadomości nie będą trafiać do '
                'kolejki przeglądu. Istniejąca historia pozostanie bez zmian.',
              ),
            ],
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            key: const Key('confirm-ignore-mail-rule'),
            onPressed: () => Navigator.pop(dialogContext, selectedType),
            child: const Text('Ignoruj'),
          ),
        ],
      ),
    ),
  );
  if (ruleType == null || !context.mounted) return false;

  final String value = ruleType == 'domain' ? domain : address;
  try {
    await api.ignoreSender(session, value: value, ruleType: ruleType);
  } catch (error) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            friendlyApiError(
              error,
              fallback: 'Nie udało się dodać reguły ignorowania.',
            ),
          ),
        ),
      );
    }
    return false;
  }
  if (!context.mounted) return true;
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(
        ruleType == 'domain'
            ? 'Ignorowanie domeny $domain zostało włączone.'
            : 'Nadawca $address został zignorowany.',
      ),
    ),
  );
  return true;
}

Future<void> showIgnoredMailSourcesDialog({
  required BuildContext context,
  required GlobalMailApi api,
  required AuthSession session,
}) => showDialog<void>(
  context: context,
  builder: (_) => _IgnoredMailSourcesDialog(api: api, session: session),
);

class _IgnoredMailSourcesDialog extends StatefulWidget {
  const _IgnoredMailSourcesDialog({required this.api, required this.session});

  final GlobalMailApi api;
  final AuthSession session;

  @override
  State<_IgnoredMailSourcesDialog> createState() =>
      _IgnoredMailSourcesDialogState();
}

class _IgnoredMailSourcesDialogState extends State<_IgnoredMailSourcesDialog> {
  bool _loading = true;
  String? _error;
  List<IgnoredMailSourceRule> _rules = const <IgnoredMailSourceRule>[];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final List<IgnoredMailSourceRule> rules = await widget.api.ignoredRules(
        widget.session,
      );
      if (mounted) setState(() => _rules = rules);
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = friendlyApiError(
            error,
            fallback: 'Nie udało się pobrać reguł ignorowania.',
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _remove(IgnoredMailSourceRule rule) async {
    final String kind = rule.ruleType == 'domain' ? 'domenę' : 'adres e-mail';
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) => AlertDialog(
        title: const Text('Usunąć z ignorowanych?'),
        content: Text('$kind: ${rule.normalizedValue}'),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Anuluj'),
          ),
          FilledButton(
            key: ValueKey<String>('confirm-remove-ignore-rule-${rule.id}'),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Usuń z ignorowanych'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    final String? overlappingDomain = rule.ruleType == 'email'
        ? _rules
              .where(
                (IgnoredMailSourceRule other) =>
                    other.id != rule.id &&
                    other.isActive &&
                    other.ruleType == 'domain' &&
                    other.normalizedValue ==
                        ignoredMailDomain(rule.normalizedValue),
              )
              .map((IgnoredMailSourceRule other) => other.normalizedValue)
              .firstOrNull
        : null;
    try {
      await widget.api.unignoreSender(widget.session, rule.id);
      await _load();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              friendlyApiError(
                error,
                fallback: 'Nie udało się usunąć reguły ignorowania.',
              ),
            ),
          ),
        );
      }
      return;
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          overlappingDomain == null
              ? 'Reguła została usunięta. Zmiana dotyczy przyszłego przetwarzania.'
              : 'Nadawca nadal jest ignorowany przez regułę domeny '
                    '$overlappingDomain.',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Ignorowani nadawcy'),
      content: SizedBox(
        width: 560,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
            ? Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Text(_error!),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: _load,
                    child: const Text('Spróbuj ponownie'),
                  ),
                ],
              )
            : _rules.isEmpty
            ? const Text('Brak aktywnych reguł ignorowania.')
            : ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 440),
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: _rules.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (BuildContext context, int index) {
                    final IgnoredMailSourceRule rule = _rules[index];
                    return ListTile(
                      key: ValueKey<String>('ignored-mail-rule-${rule.id}'),
                      leading: Icon(
                        rule.ruleType == 'domain'
                            ? Icons.domain_outlined
                            : Icons.alternate_email,
                      ),
                      title: Text(rule.normalizedValue),
                      subtitle: Text(
                        '${rule.ruleType == 'domain' ? 'Domena' : 'Email'} · '
                        '${formatPolishDateTime(rule.createdAt)}',
                      ),
                      trailing: TextButton(
                        key: ValueKey<String>('remove-ignore-rule-${rule.id}'),
                        onPressed: () => _remove(rule),
                        child: const Text('Usuń'),
                      ),
                    );
                  },
                ),
              ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Zamknij'),
        ),
      ],
    );
  }
}
