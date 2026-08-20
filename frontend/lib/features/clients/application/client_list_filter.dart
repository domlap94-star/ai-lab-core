import '../domain/client.dart';
import 'client_workflow_status.dart';

enum ClientSortOrder {
  newestFirst,
  oldestFirst;

  String get label {
    return switch (this) {
      ClientSortOrder.newestFirst => 'Data dodania: najnowsi',
      ClientSortOrder.oldestFirst => 'Data dodania: najstarsi',
    };
  }

  String get apiValue {
    return switch (this) {
      ClientSortOrder.newestFirst => 'newest',
      ClientSortOrder.oldestFirst => 'oldest',
    };
  }
}

List<Client> filterClientsForCurrentPage(
  List<Client> clients, {
  required String locationQuery,
  ClientWorkflowState? workflowStatusFilter,
}) {
  final String normalizedLocation = locationQuery.trim().toLowerCase();

  final List<Client> result = clients.where((Client client) {
    if (normalizedLocation.isNotEmpty) {
      final String locationHaystack = <String>[
        client.availableAddress ?? '',
        client.street ?? '',
        client.buildingNumber ?? '',
        client.unitNumber ?? '',
        client.postalCode ?? '',
        client.city ?? '',
        client.countryCode,
        client.addressFromNotes ?? '',
      ].join(' ').toLowerCase();

      if (!locationHaystack.contains(normalizedLocation)) {
        return false;
      }
    }

    if (workflowStatusFilter != null &&
        ClientWorkflowStatus.fromClient(client).state != workflowStatusFilter) {
      return false;
    }

    return true;
  }).toList();

  return result;
}
