import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../widgets/fruit_form_dialog.dart';
import '../widgets/fruit_picker_dialog.dart';

class RecognizeScreen extends StatefulWidget {
  const RecognizeScreen({super.key, required this.state});

  final AppState state;

  @override
  State<RecognizeScreen> createState() => _RecognizeScreenState();
}

class _RecognizeScreenState extends State<RecognizeScreen> {
  Uint8List? _bytes;
  String _fileName = 'fruta.jpg';
  bool _busy = false;
  bool _confirming = false;
  RecognitionResult? _result;
  ConfirmResult? _confirmed;
  ApiException? _error;

  AppState get _state => widget.state;

  Future<void> _pick() async {
    final group = XTypeGroup(
      label: 'Imagens',
      extensions: const ['jpg', 'jpeg', 'png'],
    );
    final XFile? file = await openFile(acceptedTypeGroups: [group]);
    if (file == null) return;
    final bytes = await file.readAsBytes();
    if (!mounted) return;
    setState(() {
      _bytes = bytes;
      _fileName = file.name;
      _result = null;
      _confirmed = null;
      _error = null;
    });
  }

  Future<void> _identify() async {
    final bytes = _bytes;
    if (bytes == null) return;
    setState(() {
      _busy = true;
      _error = null;
      _result = null;
      _confirmed = null;
    });
    try {
      final r = await _state.api.recognize(bytes, _fileName);
      if (!mounted) return;
      setState(() => _result = r);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _confirm(Fruit fruit) async {
    final r = _result;
    if (r == null) return;
    setState(() {
      _confirming = true;
      _error = null;
    });
    try {
      final c = await _state.api.confirm(r.recognitionId, fruit.id);
      _state.addHistory(HistoryEntry(fruit: c.fruit, status: c.status, at: c.confirmedAt));
      if (!mounted) return;
      setState(() => _confirmed = c);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _confirming = false);
    }
  }

  Future<void> _chooseOther() async {
    final r = _result;
    if (r == null) return;
    if (_state.fruits.isEmpty) await _state.loadFruits();
    if (!mounted) return;
    final picked = await showFruitPickerDialog(
      context,
      fruits: _state.fruits,
      suggestedId: r.fruit?.id,
    );
    if (picked != null) await _confirm(picked);
  }

  Future<void> _registerAndConfirm() async {
    final r = _result;
    if (r == null) return;
    final created = await showFruitFormDialog(
      context,
      _state,
      initialVisionLabel: r.prediction.label,
    );
    if (created != null && created.active) await _confirm(created);
  }

  void _reset() {
    setState(() {
      _bytes = null;
      _result = null;
      _confirmed = null;
      _error = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _state,
      builder: (context, _) {
        return LayoutBuilder(builder: (context, constraints) {
          final wide = constraints.maxWidth >= 980;
          final pad = wide ? 36.0 : 20.0;
          return SingleChildScrollView(
            padding: EdgeInsets.all(pad),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _header(),
                const SizedBox(height: 26),
                if (wide)
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(flex: 5, child: _imageCard()),
                      const SizedBox(width: 24),
                      Expanded(flex: 6, child: _rightPanel()),
                    ],
                  )
                else ...[
                  _imageCard(),
                  const SizedBox(height: 20),
                  _rightPanel(),
                ],
              ],
            ),
          );
        });
      },
    );
  }

  Widget _header() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Identificar fruta',
                  style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800, letterSpacing: -0.5)),
              SizedBox(height: 6),
              Text(
                'Envie uma foto, veja a sugestão do modelo e confirme ou corrija no cadastro.',
                style: TextStyle(color: kMuted, fontSize: 15),
              ),
            ],
          ),
        ),
        if (!_state.checking && !_state.online)
          const Pill(
            text: 'Backend offline',
            color: kRed,
            background: kRedSoft,
            icon: Icons.cloud_off_rounded,
          ),
      ],
    );
  }

  Widget _imageCard() {
    final bytes = _bytes;
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('1. Foto da fruta',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
          const SizedBox(height: 16),
          if (bytes == null)
            InkWell(
              onTap: _pick,
              borderRadius: BorderRadius.circular(18),
              child: Container(
                height: 280,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: kGreenSoft.withAlpha(110),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: kGreen.withAlpha(90), width: 1.5),
                ),
                child: const Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.add_photo_alternate_outlined, size: 52, color: kGreen),
                    SizedBox(height: 12),
                    Text('Clique para escolher uma imagem',
                        style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                    SizedBox(height: 4),
                    Text('JPG ou PNG', style: TextStyle(color: kMuted)),
                  ],
                ),
              ),
            )
          else
            ClipRRect(
              borderRadius: BorderRadius.circular(18),
              child: AspectRatio(
                aspectRatio: 4 / 3,
                child: Image.memory(bytes, fit: BoxFit.cover, width: double.infinity),
              ),
            ),
          if (bytes != null) ...[
            const SizedBox(height: 10),
            Text(_fileName,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: kMuted, fontSize: 13)),
          ],
          const SizedBox(height: 18),
          Row(
            children: [
              if (bytes != null) ...[
                OutlinedButton.icon(
                  onPressed: _busy ? null : _pick,
                  icon: const Icon(Icons.swap_horiz_rounded),
                  label: const Text('Trocar'),
                ),
                const SizedBox(width: 12),
              ],
              Expanded(
                child: FilledButton.icon(
                  onPressed: (bytes == null || _busy) ? null : _identify,
                  icon: _busy
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white),
                        )
                      : const Icon(Icons.auto_awesome_rounded),
                  label: Text(_busy ? 'Analisando…' : 'Identificar fruta'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _rightPanel() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (_error != null) ...[
          ErrorBanner(error: _error!),
          const SizedBox(height: 16),
        ],
        _resultCard(),
        if (_state.history.isNotEmpty) ...[
          const SizedBox(height: 20),
          _historyCard(),
        ],
      ],
    );
  }

  Widget _resultCard() {
    if (_busy) {
      return const SectionCard(
        padding: EdgeInsets.symmetric(vertical: 70, horizontal: 24),
        child: Column(
          children: [
            SizedBox(
              width: 44,
              height: 44,
              child: CircularProgressIndicator(strokeWidth: 4, color: kGreen),
            ),
            SizedBox(height: 18),
            Text('Analisando imagem…',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            SizedBox(height: 4),
            Text('O modelo de visão está classificando a fruta.',
                style: TextStyle(color: kMuted)),
          ],
        ),
      );
    }

    final confirmed = _confirmed;
    if (confirmed != null) return _confirmedCard(confirmed);

    final r = _result;
    if (r == null) {
      return const SectionCard(
        padding: EdgeInsets.symmetric(vertical: 60, horizontal: 24),
        child: EmptyState(
          emoji: '🍎',
          title: 'O resultado aparece aqui',
          message: 'Escolha uma foto e toque em “Identificar fruta” para ver a sugestão do modelo.',
        ),
      );
    }
    return _recognitionCard(r);
  }

  ({String label, Color color, Color bg, IconData icon}) _statusStyle(String status) {
    switch (status) {
      case 'recognized':
        return (label: 'Reconhecida', color: kGreenDark, bg: kGreenSoft, icon: Icons.check_circle_rounded);
      case 'confirmation_required':
        return (
          label: 'Requer confirmação',
          color: kOrange,
          bg: kOrangeSoft,
          icon: Icons.fact_check_rounded
        );
      case 'no_catalog_match':
        return (
          label: 'Sem correspondência no cadastro',
          color: kBlue,
          bg: kBlueSoft,
          icon: Icons.search_off_rounded
        );
      case 'unrecognized':
        return (label: 'Não reconhecida', color: kRed, bg: kRedSoft, icon: Icons.help_outline_rounded);
      case 'confirmed':
        return (label: 'Confirmada', color: kGreenDark, bg: kGreenSoft, icon: Icons.verified_rounded);
      case 'corrected':
        return (label: 'Corrigida', color: kBlue, bg: kBlueSoft, icon: Icons.edit_rounded);
      default:
        return (label: status, color: kRed, bg: kRedSoft, icon: Icons.error_outline_rounded);
    }
  }

  Widget _recognitionCard(RecognitionResult r) {
    final style = _statusStyle(r.status);
    final p = r.prediction;
    final fruit = r.fruit;
    final conf = p.confidence;
    final confColor = conf == null
        ? kMuted
        : conf >= 0.85
            ? kGreen
            : conf >= 0.5
                ? kOrange
                : kRed;

    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text('2. Resultado',
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              ),
              Pill(text: style.label, color: style.color, background: style.bg, icon: style.icon),
            ],
          ),
          if (p.isSimulated) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: kOrangeSoft,
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Row(
                children: [
                  Icon(Icons.science_outlined, color: kOrange, size: 20),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Modo simulado: o backend está usando o stub de desenvolvimento, '
                      'não um modelo real de visão.',
                      style: TextStyle(color: kOrange, fontWeight: FontWeight.w600, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 18),
          const Text('PREVISÃO DO MODELO',
              style: TextStyle(color: kMuted, fontSize: 11.5, fontWeight: FontWeight.w700, letterSpacing: 1)),
          const SizedBox(height: 6),
          Text(p.label ?? 'Nenhuma classe aceitável',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          const SizedBox(height: 12),
          if (conf != null) ...[
            Row(
              children: [
                const Text('Confiança', style: TextStyle(color: kMuted)),
                const Spacer(),
                Text(formatConfidence(conf),
                    style: TextStyle(fontWeight: FontWeight.w800, color: confColor)),
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: SizedBox(
                height: 10,
                child: LinearProgressIndicator(
                  value: conf.clamp(0.0, 1.0).toDouble(),
                  backgroundColor: kBorder,
                  valueColor: AlwaysStoppedAnimation<Color>(confColor),
                ),
              ),
            ),
          ],
          if (p.modelVersion != null) ...[
            const SizedBox(height: 8),
            Text('Modelo: ${p.modelVersion}',
                style: const TextStyle(color: kMuted, fontSize: 12.5)),
          ],
          const SizedBox(height: 20),
          if (fruit != null) _suggestedFruit(fruit) else _noMatch(r),
          const SizedBox(height: 22),
          _actions(r, fruit),
        ],
      ),
    );
  }

  Widget _suggestedFruit(Fruit fruit) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: kGreenSoft.withAlpha(120),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: kGreen.withAlpha(70)),
      ),
      child: Row(
        children: [
          EmojiAvatar(emoji: fruitEmoji(fruit.name), size: 58),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('FRUTA SUGERIDA (CADASTRO)',
                    style: TextStyle(
                        color: kGreenDark, fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 1)),
                const SizedBox(height: 4),
                Text(fruit.name,
                    style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text('Código ${fruit.code}',
                    style: const TextStyle(color: kMuted, fontSize: 13.5)),
              ],
            ),
          ),
          Text(fruit.priceLabel,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kGreenDark)),
        ],
      ),
    );
  }

  Widget _noMatch(RecognitionResult r) {
    final label = r.prediction.label;
    final text = label == null
        ? 'O modelo não devolveu uma classe aceitável. Selecione a fruta manualmente.'
        : 'O modelo previu “$label”, mas não há fruta ativa cadastrada com esse rótulo. '
            'Cadastre-a ou selecione outra fruta manualmente.';
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: kBlueSoft,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline_rounded, color: kBlue),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: const TextStyle(height: 1.4))),
        ],
      ),
    );
  }

  Widget _actions(RecognitionResult r, Fruit? fruit) {
    final disabled = _confirming;
    final spinner = const SizedBox(
      width: 18,
      height: 18,
      child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white),
    );
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        if (fruit != null)
          FilledButton.icon(
            onPressed: disabled ? null : () => _confirm(fruit),
            icon: disabled ? spinner : const Icon(Icons.check_rounded),
            label: const Text('Confirmar sugestão'),
          ),
        OutlinedButton.icon(
          onPressed: disabled ? null : _chooseOther,
          icon: const Icon(Icons.list_alt_rounded),
          label: Text(fruit != null ? 'Escolher outra fruta' : 'Selecionar fruta'),
        ),
        if (fruit == null && r.prediction.label != null)
          OutlinedButton.icon(
            onPressed: disabled ? null : _registerAndConfirm,
            icon: const Icon(Icons.add_rounded),
            label: const Text('Cadastrar e confirmar'),
          ),
      ],
    );
  }

  Widget _confirmedCard(ConfirmResult c) {
    final style = _statusStyle(c.status);
    return SectionCard(
      child: Column(
        children: [
          const SizedBox(height: 8),
          Container(
            width: 72,
            height: 72,
            decoration: const BoxDecoration(color: kGreenSoft, shape: BoxShape.circle),
            child: const Icon(Icons.check_rounded, size: 42, color: kGreen),
          ),
          const SizedBox(height: 16),
          Text(c.status == 'corrected' ? 'Correção registrada' : 'Fruta confirmada',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Pill(text: style.label, color: style.color, background: style.bg, icon: style.icon),
          const SizedBox(height: 20),
          _suggestedFruitPlain(c.fruit),
          const SizedBox(height: 10),
          Text('Registrado às ${formatTime(c.confirmedAt)}',
              style: const TextStyle(color: kMuted, fontSize: 13)),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _reset,
            icon: const Icon(Icons.add_a_photo_outlined),
            label: const Text('Nova identificação'),
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _suggestedFruitPlain(Fruit fruit) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: kBg,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        children: [
          EmojiAvatar(emoji: fruitEmoji(fruit.name), size: 56),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(fruit.name,
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                Text('Código ${fruit.code}', style: const TextStyle(color: kMuted)),
              ],
            ),
          ),
          Text(fruit.priceLabel,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kGreenDark)),
        ],
      ),
    );
  }

  Widget _historyCard() {
    final entries = _state.history.take(5).toList();
    return SectionCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Confirmações da sessão',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          for (final e in entries)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 5),
              child: Row(
                children: [
                  Text(fruitEmoji(e.fruit.name), style: const TextStyle(fontSize: 22)),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(e.fruit.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                  ),
                  Text(e.status == 'corrected' ? 'corrigida' : 'confirmada',
                      style: const TextStyle(color: kMuted, fontSize: 12.5)),
                  const SizedBox(width: 10),
                  Text(formatTime(e.at), style: const TextStyle(color: kMuted, fontSize: 12.5)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
