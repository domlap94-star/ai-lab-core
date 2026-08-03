import 'package:flutter/material.dart';

class ClientsPage extends StatelessWidget {
  const ClientsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Klienci')),
      body: const Center(child: Text('Tutaj powstanie moduł klientów.')),
    );
  }
}
