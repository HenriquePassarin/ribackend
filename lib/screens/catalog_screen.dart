import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../widgets/fruit_form_dialog.dart';

enum _Filter { all, active, inactive }

class CatalogScreen extends StatefulWidget {
  const CatalogScreen({super.key, required this.state});

  final AppState state;

  @override
  State<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends State<CatalogScreen> {
  String _query = '';
  _Filter _filter = _Filter.all;

  AppState get _state => widget.state;

  Future<void> _create() async {
    final fruit = await showFruitFormDialog(context, _state);
    if (fruit != null && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          behavior: SnackBarBehavior.floating,
          backgroundColor: kGreenDark,
          content: Text('“${fruit.name}” cadastrada com sucesso.'),
        ),
      );
    }
  }

  List<Fruit> _filtered() {
    final q = foldText(_query.trim());
    return _state.fruits.where((f) {
      if (_filter == _Filter.active && !f.active) return false;
      if (_filter == _Filter.inactive && f.active) return false;
      if (q.isEmpty) return true;
      return foldText(f.name).contains(q) ||
          f.code.toLowerCase().contains(q) ||
          foldText(f.visionLabel ?? '').contains(q);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _state,
      builder: (context, _) {
        final items = _filtered();
        return LayoutBuilder(builder: (context, constraints) {
          final pad = constraints.maxWidth >= 980 ? 36.0 : 20.0;
          return Padding(
            padding: EdgeInsets.all(pad),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _header(),
                const SizedBox(height: 22),
                _toolbar(),
                const SizedBox(height: 20),
                Expanded(child: _body(items)),
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
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Catálogo de frutas',
                  style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800, letterSpacing: -0.5)),
              const SizedBox(height: 6),
              Text(
                '${_state.fruits.length} fruta(s) cadastrada(s). Código e preço vêm sempre deste cadastro.',
                style: const TextStyle(color: kMuted, fontSize: 15),
              ),
            ],
          ),
        ),
        IconButton(
          tooltip: 'Atualizar',
          onPressed: _state.loadingFruits ? null : _state.loadFruits,
          icon: const Icon(Icons.refresh_rounded),
        ),
        const SizedBox(width: 8),
        FilledButton.icon(
          onPressed: _state.online ? _create : null,
          icon: const Icon(Icons.add_rounded),
          label: const Text('Nova fruta'),
        ),
      ],
    );
  }

  Widget _toolbar() {
    return Wrap(
      spacing: 14,
      runSpacing: 10,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        SizedBox(
          width: 360,
          child: TextField(
            onChanged: (v) => setState(() => _query = v),
            decoration: const InputDecoration(
              hintText: 'Buscar por nome, código ou rótulo',
              prefixIcon: Icon(Icons.search_rounded),
            ),
          ),
        ),
        for (final entry in const {
          _Filter.all: 'Todas',
          _Filter.active: 'Ativas',
          _Filter.inactive: 'Inativas',
        }.entries)
          ChoiceChip(
            label: Text(entry.value),
            selected: _filter == entry.key,
            selectedColor: kGreenSoft,
            backgroundColor: Colors.white,
            side: const BorderSide(color: kBorder),
            labelStyle: TextStyle(
              fontWeight: FontWeight.w600,
              color: _filter == entry.key ? kGreenDark : kInk,
            ),
            onSelected: (_) => setState(() => _filter = entry.key),
          ),
      ],
    );
  }

  Widget _body(List<Fruit> items) {
    if (_state.loadingFruits && _state.fruits.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: kGreen));
    }
    if (!_state.online || _state.fruitsError != null) {
      return EmptyState(
        emoji: '🔌',
        title: 'Backend indisponível',
        message: _state.fruitsError?.message ??
            'Não foi possível falar com o backend em ${_state.api.baseUrl}.',
        action: OutlinedButton.icon(
          onPressed: () async {
            await _state.refreshHealth();
            if (_state.online) await _state.loadFruits();
          },
          icon: const Icon(Icons.refresh_rounded),
          label: const Text('Tentar novamente'),
        ),
      );
    }
    if (items.isEmpty) {
      return EmptyState(
        emoji: '🧺',
        title: _state.fruits.isEmpty ? 'Nenhuma fruta cadastrada' : 'Nada encontrado',
        message: _state.fruits.isEmpty
            ? 'Cadastre a primeira fruta para o reconhecimento poder sugerir nome, código e preço.'
            : 'Tente outro termo de busca ou mude o filtro.',
        action: _state.fruits.isEmpty
            ? FilledButton.icon(
                onPressed: _create,
                icon: const Icon(Icons.add_rounded),
                label: const Text('Cadastrar fruta'),
              )
            : null,
      );
    }
    return GridView.builder(
      itemCount: items.length,
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 380,
        mainAxisExtent: 168,
        crossAxisSpacing: 18,
        mainAxisSpacing: 18,
      ),
      itemBuilder: (context, i) => _FruitCard(fruit: items[i]),
    );
  }
}

class _FruitCard extends StatelessWidget {
  const _FruitCard({required this.fruit});

  final Fruit fruit;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              EmojiAvatar(emoji: fruitEmoji(fruit.name), size: 50),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(fruit.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 16.5, fontWeight: FontWeight.w800)),
                    const SizedBox(height: 2),
                    Text('Código ${fruit.code}',
                        style: const TextStyle(color: kMuted, fontSize: 13)),
                  ],
                ),
              ),
            ],
          ),
          const Spacer(),
          Row(
            children: [
              Expanded(
                child: Text(fruit.priceLabel,
                    style: const TextStyle(
                        fontSize: 17, fontWeight: FontWeight.w800, color: kGreenDark)),
              ),
              fruit.active
                  ? const Pill(text: 'Ativa', color: kGreenDark, background: kGreenSoft)
                  : const Pill(text: 'Inativa', color: kMuted, background: kBg),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            fruit.visionLabel == null ? 'Sem rótulo de visão' : 'Rótulo: ${fruit.visionLabel}',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: kMuted, fontSize: 12.5),
          ),
        ],
      ),
    );
  }
}
