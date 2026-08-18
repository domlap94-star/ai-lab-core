import 'package:flutter/material.dart';

import '../../../core/widgets/app_shell.dart';

class AiPage extends StatelessWidget {
  const AiPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: AppShell.mobileNavigationLeading(context),
        title: const Text('Asystent AI'),
        actions: <Widget>[AppShell.globalSearchAction(context)],
      ),
      body: const Center(child: Text('Tutaj powstanie przestrzeń pracy z AI.')),
    );
  }
}
