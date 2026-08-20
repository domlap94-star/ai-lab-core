import 'client_list_filter.dart';
import 'client_workflow_status.dart';
import '../domain/client.dart';

class ClientListViewMemory {
  ClientListViewMemory._();

  static final ClientListViewMemory instance = ClientListViewMemory._();

  String searchQuery = '';
  String locationQuery = '';
  ClientSortOrder sortOrder = ClientSortOrder.newestFirst;
  Set<ClientWorkflowState> excludedWorkflowStatuses = <ClientWorkflowState>{};
  ClientType? clientTypeFilter;
  int? industryIdFilter;
  bool filtersExpanded = false;

  void clearSearch() {
    searchQuery = '';
  }

  void clearLocation() {
    locationQuery = '';
  }

  void reset() {
    searchQuery = '';
    locationQuery = '';
    sortOrder = ClientSortOrder.newestFirst;
    excludedWorkflowStatuses.clear();
    clientTypeFilter = null;
    industryIdFilter = null;
    filtersExpanded = false;
  }
}
