import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api_client.dart';
import 'models.dart';

class HistoryEntry {
  HistoryEntry({required this.fruit, required this.status, required this.at});

  final Fruit fruit;
  final String status; // confirmed | corrected
  final DateTime at;
}

/// Estado compartilhado do app: conexão com o backend, catálogo e histórico da sessão.
class AppState extends ChangeNotifier {
  final ApiClient api = ApiClient();

  bool online = false;
  bool checking = true;

  List<Fruit> fruits = [];
  bool loadingFruits = false;
  ApiException? fruitsError;

  final List<HistoryEntry> history = [];

  Timer? _timer;

  void start() {
    refreshHealth();
    _timer = Timer.periodic(const Duration(seconds: 8), (_) => refreshHealth());
  }

  Future<void> refreshHealth() async {
    final wasOnline = online;
    final ok = await api.health();
    online = ok;
    checking = false;
    notifyListeners();
    if (ok && !wasOnline) {
      loadFruits();
    }
  }

  Future<void> setBaseUrl(String url) async {
    api.baseUrl = url;
    online = false;
    checking = true;
    notifyListeners();
    await refreshHealth();
  }

  Future<void> loadFruits() async {
    loadingFruits = true;
    fruitsError = null;
    notifyListeners();
    try {
      fruits = await api.listFruits();
    } on ApiException catch (e) {
      fruitsError = e;
    } finally {
      loadingFruits = false;
      notifyListeners();
    }
  }

  Future<Fruit> createFruit({
    required String name,
    required String code,
    String? pricePerKg,
    String unit = 'kg',
    bool active = true,
    String? visionLabel,
  }) async {
    final fruit = await api.createFruit(
      name: name,
      code: code,
      pricePerKg: pricePerKg,
      unit: unit,
      active: active,
      visionLabel: visionLabel,
    );
    await loadFruits();
    return fruit;
  }

  void addHistory(HistoryEntry entry) {
    history.insert(0, entry);
    notifyListeners();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}
