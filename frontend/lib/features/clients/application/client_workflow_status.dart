import 'package:flutter/material.dart';

import '../../../core/formatters/polish_date_time.dart';
import '../domain/client.dart';

enum ClientWorkflowState {
  obsolete,
  inProgress,
  inspection,
  completed,
  untouched,
  phoneContact;

  String get apiValue => switch (this) {
    ClientWorkflowState.obsolete => 'obsolete',
    ClientWorkflowState.inProgress => 'in_progress',
    ClientWorkflowState.inspection => 'inspection',
    ClientWorkflowState.completed => 'completed',
    ClientWorkflowState.untouched => 'untouched',
    ClientWorkflowState.phoneContact => 'phone_contact',
  };

  static ClientWorkflowState fromApi(String value) => switch (value) {
    'obsolete' => obsolete,
    'in_progress' => inProgress,
    'inspection' => inspection,
    'completed' => completed,
    'phone_contact' => phoneContact,
    _ => untouched,
  };

  String get label {
    return switch (this) {
      ClientWorkflowState.obsolete => 'Nieaktualne',
      ClientWorkflowState.inProgress => 'W trakcie',
      ClientWorkflowState.inspection => 'Oględziny',
      ClientWorkflowState.completed => 'Usługa wykonana',
      ClientWorkflowState.untouched => 'Brak modyfikacji',
      ClientWorkflowState.phoneContact => 'Kontakt telefoniczny',
    };
  }

  bool get requiresDate {
    return this == ClientWorkflowState.inspection ||
        this == ClientWorkflowState.phoneContact;
  }

  String get shortLabel {
    return switch (this) {
      ClientWorkflowState.obsolete => 'X',
      ClientWorkflowState.inProgress => 'WT',
      ClientWorkflowState.inspection => 'OG',
      ClientWorkflowState.completed => 'OK',
      ClientWorkflowState.untouched => '-',
      ClientWorkflowState.phoneContact => 'TEL',
    };
  }

  Color color(ThemeData theme) {
    return switch (this) {
      ClientWorkflowState.obsolete => const Color(0xFFD64C4C),
      ClientWorkflowState.inProgress => const Color(0xFFE0B93B),
      ClientWorkflowState.inspection => const Color(0xFF4F78FF),
      ClientWorkflowState.completed => const Color(0xFF2FA763),
      ClientWorkflowState.untouched => const Color(0xFF80859B),
      ClientWorkflowState.phoneContact => const Color(0xFFF5F7FB),
    };
  }

  Color foregroundColor(ThemeData theme) {
    return switch (this) {
      ClientWorkflowState.phoneContact => const Color(0xFF0F1422),
      ClientWorkflowState.inProgress => const Color(0xFF0F1422),
      _ => Colors.white,
    };
  }
}

class ClientWorkflowStatus {
  const ClientWorkflowStatus({
    required this.state,
    this.date,
    this.serverLabel,
  });

  final ClientWorkflowState state;
  final DateTime? date;
  final String? serverLabel;

  factory ClientWorkflowStatus.fromClient(Client client) {
    return ClientWorkflowStatus(
      state: ClientWorkflowState.fromApi(client.workflowStatus),
      date: client.workflowEffectiveDate,
      serverLabel: client.workflowStatusLabel,
    );
  }

  String get displayLabel {
    if (!state.requiresDate || date == null) {
      return serverLabel?.trim().isNotEmpty == true
          ? serverLabel!.trim()
          : state.label;
    }
    final String label = serverLabel?.trim().isNotEmpty == true
        ? serverLabel!.trim()
        : state.label;
    return '$label ${formatDate(date!)}';
  }

  static String formatDate(DateTime value) {
    return formatPolishDate(value);
  }
}
