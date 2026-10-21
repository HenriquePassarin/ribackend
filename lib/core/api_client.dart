import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import 'models.dart';

/// Cliente HTTP do backend. Todas as falhas viram [ApiException] com mensagem em pt-BR.
class ApiClient {
  ApiClient({String baseUrl = 'http://127.0.0.1:8000'}) : _baseUrl = baseUrl;

  String _baseUrl;
  static const _timeout = Duration(seconds: 30);
  static const _prefix = '/api/v1';

  String get baseUrl => _baseUrl;
  set baseUrl(String value) => _baseUrl = value.trim().replaceAll(RegExp(r'/+$'), '');

  Uri _uri(String path, [Map<String, String>? query]) {
    final uri = Uri.parse('$_baseUrl$path');
    return query == null ? uri : uri.replace(queryParameters: query);
  }

  Future<T> _guard<T>(Future<T> Function() run) async {
    try {
      return await run();
    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw ApiException(
        code: 'TIMEOUT',
        message: 'O backend demorou demais para responder.',
      );
    } on SocketException {
      throw _connectionError();
    } on http.ClientException {
      throw _connectionError();
    } on FormatException {
      throw ApiException(
        code: 'BAD_RESPONSE',
        message: 'Resposta inesperada do backend.',
      );
    }
  }

  ApiException _connectionError() => ApiException(
        code: 'CONNECTION',
        message: 'Não foi possível conectar ao backend em $_baseUrl. '
            'Verifique se ele está em execução.',
      );

  dynamic _handle(http.Response res) {
    final text = utf8.decode(res.bodyBytes);
    dynamic body;
    try {
      body = text.isEmpty ? null : jsonDecode(text);
    } catch (_) {
      body = null;
    }
    if (res.statusCode >= 200 && res.statusCode < 300) return body;

    if (body is Map && body['error'] is Map) {
      final error = body['error'] as Map;
      throw ApiException(
        statusCode: res.statusCode,
        code: (error['code'] ?? 'ERROR').toString(),
        message: (error['message'] ?? 'Erro ao processar a requisição.').toString(),
        details: error['details'],
      );
    }
    throw ApiException(
      statusCode: res.statusCode,
      code: 'HTTP_${res.statusCode}',
      message: 'Erro inesperado do servidor (${res.statusCode}).',
    );
  }

  Future<bool> health() async {
    try {
      final res = await http.get(_uri('/health')).timeout(const Duration(seconds: 4));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<List<Fruit>> listFruits() async {
    return _guard(() async {
      final all = <Fruit>[];
      var offset = 0;
      while (true) {
        final res = await http
            .get(_uri('$_prefix/fruits', {'limit': '100', 'offset': '$offset'}))
            .timeout(_timeout);
        final body = (_handle(res) as Map).cast<String, dynamic>();
        final items = (body['items'] as List)
            .map((e) => Fruit.fromJson((e as Map).cast<String, dynamic>()))
            .toList();
        all.addAll(items);
        final total = (body['total'] as num).toInt();
        offset += items.length;
        if (items.isEmpty || offset >= total) break;
      }
      return all;
    });
  }

  Future<Fruit> createFruit({
    required String name,
    required String code,
    String? pricePerKg,
    String unit = 'kg',
    bool active = true,
    String? visionLabel,
  }) async {
    return _guard(() async {
      final payload = <String, dynamic>{
        'name': name,
        'code': code,
        'unit': unit,
        'active': active,
        if (pricePerKg != null) 'price_per_kg': pricePerKg,
        if (visionLabel != null) 'vision_label': visionLabel,
      };
      final res = await http
          .post(
            _uri('$_prefix/fruits'),
            headers: {'Content-Type': 'application/json; charset=utf-8'},
            body: jsonEncode(payload),
          )
          .timeout(_timeout);
      return Fruit.fromJson((_handle(res) as Map).cast<String, dynamic>());
    });
  }

  Future<RecognitionResult> recognize(Uint8List bytes, String filename) async {
    return _guard(() async {
      final isPng = filename.toLowerCase().endsWith('.png');
      final request = http.MultipartRequest('POST', _uri('$_prefix/recognitions'))
        ..files.add(http.MultipartFile.fromBytes(
          'file',
          bytes,
          filename: filename,
          contentType: MediaType('image', isPng ? 'png' : 'jpeg'),
        ));
      final streamed = await request.send().timeout(_timeout);
      final res = await http.Response.fromStream(streamed);
      return RecognitionResult.fromJson((_handle(res) as Map).cast<String, dynamic>());
    });
  }

  Future<ConfirmResult> confirm(String recognitionId, int fruitId) async {
    return _guard(() async {
      final res = await http
          .post(
            _uri('$_prefix/recognitions/$recognitionId/confirm'),
            headers: {'Content-Type': 'application/json; charset=utf-8'},
            body: jsonEncode({'fruit_id': fruitId}),
          )
          .timeout(_timeout);
      return ConfirmResult.fromJson((_handle(res) as Map).cast<String, dynamic>());
    });
  }
}
