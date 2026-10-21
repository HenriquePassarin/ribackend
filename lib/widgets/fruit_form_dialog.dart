import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';

/// Rótulos de frutas do modelo de referência (MobileNetV2 / ImageNet-1k).
const kModelLabelSuggestions = <String>[
  'banana',
  'orange',
  'lemon',
  'strawberry',
  'pomegranate',
  'fig',
  'pineapple',
  'Granny Smith',
  'jackfruit',
  'custard apple',
];

/// Abre o formulário de cadastro. Retorna a fruta criada ou null se cancelado.
Future<Fruit?> showFruitFormDialog(
  BuildContext context,
  AppState state, {
  String? initialVisionLabel,
}) {
  return showDialog<Fruit>(
    context: context,
    barrierDismissible: false,
    builder: (_) => _FruitFormDialog(state: state, initialVisionLabel: initialVisionLabel),
  );
}

class _FruitFormDialog extends StatefulWidget {
  const _FruitFormDialog({required this.state, this.initialVisionLabel});

  final AppState state;
  final String? initialVisionLabel;

  @override
  State<_FruitFormDialog> createState() => _FruitFormDialogState();
}

class _FruitFormDialogState extends State<_FruitFormDialog> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _code = TextEditingController();
  final _price = TextEditingController();
  final _unit = TextEditingController(text: 'kg');
  late final TextEditingController _label;
  bool _active = true;
  bool _saving = false;
  String? _serverError;

  @override
  void initState() {
    super.initState();
    _label = TextEditingController(text: widget.initialVisionLabel ?? '');
  }

  @override
  void dispose() {
    _name.dispose();
    _code.dispose();
    _price.dispose();
    _unit.dispose();
    _label.dispose();
    super.dispose();
  }

  String? _required(String? v, String what) =>
      (v == null || v.trim().isEmpty) ? 'Informe $what' : null;

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _serverError = null;
    });

    final rawPrice = _price.text.trim().replaceAll(',', '.');
    final price = rawPrice.isEmpty ? null : double.parse(rawPrice).toStringAsFixed(2);
    final label = _label.text.trim();

    try {
      final fruit = await widget.state.createFruit(
        name: _name.text.trim(),
        code: _code.text.trim(),
        pricePerKg: price,
        unit: _unit.text.trim(),
        active: _active,
        visionLabel: label.isEmpty ? null : label,
      );
      if (!mounted) return;
      Navigator.of(context).pop(fruit);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _serverError = e.message;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(28),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: kGreenSoft,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: const Icon(Icons.add_circle_outline_rounded, color: kGreen),
                    ),
                    const SizedBox(width: 14),
                    const Expanded(
                      child: Text('Cadastrar fruta',
                          style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800)),
                    ),
                  ],
                ),
                const SizedBox(height: 22),
                TextFormField(
                  controller: _name,
                  enabled: !_saving,
                  textInputAction: TextInputAction.next,
                  decoration: const InputDecoration(labelText: 'Nome *', hintText: 'Ex.: Banana Prata'),
                  validator: (v) => _required(v, 'o nome'),
                ),
                const SizedBox(height: 14),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _code,
                        enabled: !_saving,
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          labelText: 'Código comercial *',
                          hintText: '00002',
                        ),
                        validator: (v) {
                          final msg = _required(v, 'o código');
                          if (msg != null) return msg;
                          if (v!.trim().contains(RegExp(r'\s'))) return 'Sem espaços';
                          return null;
                        },
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: TextFormField(
                        controller: _price,
                        enabled: !_saving,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(
                          labelText: 'Preço por kg',
                          prefixText: 'R\$ ',
                          hintText: '0,00',
                        ),
                        validator: (v) {
                          final t = (v ?? '').trim();
                          if (t.isEmpty) return null;
                          if (!RegExp(r'^\d+([.,]\d{1,2})?$').hasMatch(t)) {
                            return 'Valor inválido';
                          }
                          return null;
                        },
                      ),
                    ),
                    const SizedBox(width: 14),
                    SizedBox(
                      width: 90,
                      child: TextFormField(
                        controller: _unit,
                        enabled: !_saving,
                        decoration: const InputDecoration(labelText: 'Unidade'),
                        validator: (v) => _required(v, 'a unidade'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _label,
                  enabled: !_saving,
                  decoration: const InputDecoration(
                    labelText: 'Rótulo do modelo (vision_label)',
                    helperText: 'Precisa ser igual à classe prevista pelo modelo de visão',
                    helperMaxLines: 2,
                  ),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    for (final s in kModelLabelSuggestions)
                      ActionChip(
                        label: Text(s, style: const TextStyle(fontSize: 12.5)),
                        backgroundColor: kGreenSoft,
                        side: BorderSide.none,
                        onPressed: _saving ? null : () => setState(() => _label.text = s),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: _active,
                  activeColor: kGreen,
                  onChanged: _saving ? null : (v) => setState(() => _active = v),
                  title: const Text('Fruta ativa', style: TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: const Text('Frutas inativas não podem ser confirmadas no reconhecimento'),
                ),
                if (_serverError != null) ...[
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: kRedSoft,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(_serverError!,
                        style: const TextStyle(color: kRed, fontWeight: FontWeight.w600)),
                  ),
                ],
                const SizedBox(height: 22),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    OutlinedButton(
                      onPressed: _saving ? null : () => Navigator.of(context).pop(),
                      child: const Text('Cancelar'),
                    ),
                    const SizedBox(width: 12),
                    FilledButton.icon(
                      onPressed: _saving ? null : _submit,
                      icon: _saving
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white),
                            )
                          : const Icon(Icons.check_rounded),
                      label: Text(_saving ? 'Salvando…' : 'Salvar fruta'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
