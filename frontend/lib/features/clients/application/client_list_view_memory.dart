import 'client_list_filter.dart';
import 'client_workflow_status.dart';

class ClientListViewMemory {
  ClientListViewMemory._();

  static final ClientListViewMemory instance = ClientListViewMemory._();

  String searchQuery = '';
  String locationQuery = '';
  ClientSortOrder sortOrder = ClientSortOrder.newestFirst;
  ClientWorkflowState? workflowStatusFilter;
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
    workflowStatusFilter = null;
  }
}
