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
}

List<Client> filterAndSortClients(
  List<Client> clients, {
  required String locationQuery,
  required ClientSortOrder sortOrder,
  ClientWorkflowState? workflowStatusFilter,
}) {
  final String normalizedLocation = locationQuery.trim().toLowerCase();

  final ClientWorkflowMemory workflowMemory = ClientWorkflowMemory.instance;

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
        workflowMemory.statusFor(client).state != workflowStatusFilter) {
      return false;
    }

    return true;
  }).toList();

  result.sort((Client left, Client right) {
    final int comparison = left.createdAt.compareTo(right.createdAt);

    return switch (sortOrder) {
      ClientSortOrder.newestFirst => -comparison,
      ClientSortOrder.oldestFirst => comparison,
    };
  });

  return result;
}
