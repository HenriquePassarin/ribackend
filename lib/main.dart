import 'package:flutter/material.dart';

import 'core/app_state.dart';
import 'core/theme.dart';
import 'screens/shell.dart';

void main() {
  runApp(const FrutaApp());
}

class FrutaApp extends StatefulWidget {
  const FrutaApp({super.key});

  @override
  State<FrutaApp> createState() => _FrutaAppState();
}

class _FrutaAppState extends State<FrutaApp> {
  final AppState _state = AppState();

  @override
  void initState() {
    super.initState();
    _state.start();
  }

  @override
  void dispose() {
    _state.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'HortiScan',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: Shell(state: _state),
    );
  }
}
