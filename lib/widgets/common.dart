import 'package:flutter/material.dart';

import '../core/models.dart';
import '../core/theme.dart';

/// Cartão branco com borda suave, usado em todo o app.
class SectionCard extends StatelessWidget {
  const SectionCard({super.key, required this.child, this.padding = const EdgeInsets.all(24)});

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: kBorder),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(10),
            blurRadius: 18,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: child,
    );
  }
}

class Pill extends StatelessWidget {
  const Pill({
    super.key,
    required this.text,
    required this.color,
    required this.background,
    this.icon,
  });

  final String text;
  final Color color;
  final Color background;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 5),
          ],
          Text(
            text,
            style: TextStyle(color: color, fontSize: 12.5, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.emoji,
    required this.title,
    required this.message,
    this.action,
  });

  final String emoji;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(emoji, style: const TextStyle(fontSize: 54)),
            const SizedBox(height: 14),
            Text(title,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 380),
              child: Text(
                message,
                textAlign: TextAlign.center,
                style: const TextStyle(color: kMuted, height: 1.4),
              ),
            ),
            if (action != null) ...[const SizedBox(height: 18), action!],
          ],
        ),
      ),
    );
  }
}

class ErrorBanner extends StatelessWidget {
  const ErrorBanner({super.key, required this.error});

  final ApiException error;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: kRedSoft,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kRed.withAlpha(70)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline_rounded, color: kRed),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(error.message,
                    style: const TextStyle(color: kRed, fontWeight: FontWeight.w600, height: 1.35)),
                const SizedBox(height: 4),
                Text('Código: ${error.code}',
                    style: TextStyle(color: kRed.withAlpha(190), fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

String _fold(String input) {
  const from = 'áàâãäéèêëíìîïóòôõöúùûüçñ';
  const to = 'aaaaaeeeeiiiiooooouuuucn';
  final lower = input.toLowerCase();
  final out = StringBuffer();
  for (final rune in lower.runes) {
    final ch = String.fromCharCode(rune);
    final idx = from.indexOf(ch);
    out.write(idx >= 0 ? to[idx] : ch);
  }
  return out.toString();
}

/// Normaliza texto para busca (sem acentos e minúsculo).
String foldText(String input) => _fold(input);

/// Emoji decorativo a partir do nome da fruta.
String fruitEmoji(String name) {
  final n = _fold(name);
  const map = <String, String>{
    'maca': '🍎',
    'granny': '🍏',
    'banana': '🍌',
    'laranja': '🍊',
    'orange': '🍊',
    'limao': '🍋',
    'lemon': '🍋',
    'morango': '🍓',
    'strawberry': '🍓',
    'uva': '🍇',
    'melancia': '🍉',
    'abacaxi': '🍍',
    'pineapple': '🍍',
    'pera': '🍐',
    'manga': '🥭',
    'mamao': '🥭',
    'kiwi': '🥝',
    'pessego': '🍑',
    'cereja': '🍒',
    'coco': '🥥',
    'melao': '🍈',
    'tomate': '🍅',
    'abacate': '🥑',
  };
  for (final entry in map.entries) {
    if (n.contains(entry.key)) return entry.value;
  }
  return '🍏';
}

String formatConfidence(double value) =>
    '${(value * 100).toStringAsFixed(1).replaceAll('.', ',')}%';

String formatTime(DateTime t) {
  String two(int v) => v.toString().padLeft(2, '0');
  return '${two(t.hour)}:${two(t.minute)}';
}

class EmojiAvatar extends StatelessWidget {
  const EmojiAvatar({super.key, required this.emoji, this.size = 52});

  final String emoji;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: kGreenSoft,
        borderRadius: BorderRadius.circular(size * 0.32),
      ),
      child: Text(emoji, style: TextStyle(fontSize: size * 0.5)),
    );
  }
}
