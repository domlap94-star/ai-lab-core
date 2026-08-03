import 'package:flutter/material.dart';

class DocumentsPage extends StatelessWidget {
  const DocumentsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dokumenty')),
      body: const Center(
        child: Text('Tutaj powstanie repozytorium dokumentów.'),
      ),
    );
  }
}
