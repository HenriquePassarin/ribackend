/// Modelos que espelham os contratos JSON do backend (FastAPI).

class Fruit {
  const Fruit({
    required this.id,
    required this.name,
    required this.code,
    required this.pricePerKg,
    required this.unit,
    required this.active,
    required this.visionLabel,
  });

  final int id;
  final String name;
  final String code;

  /// O backend devolve dinheiro como string ("8.99") para não perder precisão.
  final String? pricePerKg;
  final String unit;
  final bool active;
  final String? visionLabel;

  factory Fruit.fromJson(Map<String, dynamic> json) {
    return Fruit(
      id: (json['id'] as num).toInt(),
      name: json['name'] as String,
      code: json['code'] as String,
      pricePerKg: json['price_per_kg']?.toString(),
      unit: (json['unit'] as String?) ?? 'kg',
      active: (json['active'] as bool?) ?? true,
      visionLabel: json['vision_label'] as String?,
    );
  }

  String get priceLabel {
    final raw = pricePerKg;
    if (raw == null) return 'Sem preço';
    final value = double.tryParse(raw);
    if (value == null) return raw;
    return 'R\$ ${value.toStringAsFixed(2).replaceAll('.', ',')} / $unit';
  }
}

class Prediction {
  const Prediction({this.label, this.confidence, this.modelVersion});

  final String? label;
  final double? confidence;
  final String? modelVersion;

  factory Prediction.fromJson(Map<String, dynamic> json) {
    return Prediction(
      label: json['label'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble(),
      modelVersion: json['model_version'] as String?,
    );
  }

  /// O backend marca o simulador de desenvolvimento como "development-stub-v0".
  bool get isSimulated => (modelVersion ?? '').toLowerCase().contains('stub');
}

class RecognitionResult {
  const RecognitionResult({
    required this.recognitionId,
    required this.status,
    required this.prediction,
    required this.fruit,
    required this.confirmationRequired,
  });

  final String recognitionId;
  final String status;
  final Prediction prediction;
  final Fruit? fruit;
  final bool confirmationRequired;

  factory RecognitionResult.fromJson(Map<String, dynamic> json) {
    final fruitJson = json['fruit'];
    return RecognitionResult(
      recognitionId: json['recognition_id'] as String,
      status: json['status'] as String,
      prediction:
          Prediction.fromJson((json['prediction'] as Map).cast<String, dynamic>()),
      fruit: fruitJson is Map ? Fruit.fromJson(fruitJson.cast<String, dynamic>()) : null,
      confirmationRequired: (json['confirmation_required'] as bool?) ?? true,
    );
  }
}

class ConfirmResult {
  const ConfirmResult({
    required this.recognitionId,
    required this.status,
    required this.fruit,
    required this.confirmedAt,
  });

  final String recognitionId;
  final String status; // confirmed | corrected
  final Fruit fruit;
  final DateTime confirmedAt;

  factory ConfirmResult.fromJson(Map<String, dynamic> json) {
    return ConfirmResult(
      recognitionId: json['recognition_id'] as String,
      status: json['status'] as String,
      fruit: Fruit.fromJson((json['fruit'] as Map).cast<String, dynamic>()),
      confirmedAt: DateTime.tryParse(json['confirmed_at'] as String? ?? '')?.toLocal() ??
          DateTime.now(),
    );
  }
}

class ApiException implements Exception {
  ApiException({required this.code, required this.message, this.statusCode, this.details});

  final String code;
  final String message;
  final int? statusCode;
  final Object? details;

  @override
  String toString() => '$code: $message';
}
