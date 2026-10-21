import 'package:flutter/material.dart';

import '../core/models.dart';
import '../core/theme.dart';
import 'common.dart';

/// Diálogo para escolher manualmente uma fruta do catálogo (correção do atendente).
Future<Fruit?> showFruitPickerDialog(
  BuildContext context, {
  required List<Fruit> fruits,
  int? suggestedId,
}) {
  return showDialog<Fruit>(
    context: context,
    builder: (_) => _FruitPickerDialog(fruits: fruits, suggestedId: suggestedId),
  );
}

class _FruitPickerDialog extends StatefulWidget {
  const _FruitPickerDialog({required this.fruits, this.suggestedId});

  final List<Fruit> fruits;
  final int? suggestedId;

  @override
  State<_FruitPickerDialog> createState() => _FruitPickerDialogState();
}

class _FruitPickerDialogState extends State<_FruitPickerDialog> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final q = foldText(_query.trim());
    final items = widget.fruits.where((f) {
      if (!f.active) return false;
      if (q.isEmpty) return true;
      return foldText(f.name).contains(q) || f.code.toLowerCase().contains(q);
    }).toList();

    return Dialog(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520, maxHeight: 620),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Escolher fruta',
                  style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800)),
              const SizedBox(height: 4),
              const Text('Selecione a fruta correta no catálogo (somente frutas ativas).',
                  style: TextStyle(color: kMuted)),
              const SizedBox(height: 16),
              TextField(
                autofocus: true,
                onChanged: (v) => setState(() => _query = v),
                decoration: const InputDecoration(
                  hintText: 'Buscar por nome ou código',
                  prefixIcon: Icon(Icons.search_rounded),
                ),
              ),
              const SizedBox(height: 12),
              Flexible(
                child: items.isEmpty
                    ? const Padding(
                        padding: EdgeInsets.symmetric(vertical: 32),
                        child: Center(
                          child: Text('Nenhuma fruta encontrada.',
                              style: TextStyle(color: kMuted)),
                        ),
                      )
                    : ListView.separated(
                        shrinkWrap: true,
                        itemCount: items.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 8),
                        itemBuilder: (context, i) {
                          final f = items[i];
                          final suggested = f.id == widget.suggestedId;
                          return InkWell(
                            borderRadius: BorderRadius.circular(16),
                            onTap: () => Navigator.of(context).pop(f),
                            child: Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(color: suggested ? kGreen : kBorder),
                                color: suggested ? kGreenSoft.withAlpha(120) : Colors.white,
                              ),
                              child: Row(
                                children: [
                                  EmojiAvatar(emoji: fruitEmoji(f.name), size: 44),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(f.name,
                                            style: const TextStyle(
                                                fontWeight: FontWeight.w700, fontSize: 15)),
                                        const SizedBox(height: 2),
                                        Text('Código ${f.code} · ${f.priceLabel}',
                                            style: const TextStyle(color: kMuted, fontSize: 13)),
                                      ],
                                    ),
                                  ),
                                  if (suggested)
                                    const Pill(
                                      text: 'Sugerida',
                                      color: kGreenDark,
                                      background: kGreenSoft,
                                    ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
              ),
              const SizedBox(height: 14),
              Align(
                alignment: Alignment.centerRight,
                child: OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Cancelar'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
